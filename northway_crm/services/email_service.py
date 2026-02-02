import os
import resend
from flask import render_template, current_app
from models import db, EmailLog, Company, User
from datetime import datetime

from models import Company, EmailLog, EMAIL_TEMPLATES

class EmailService:
    
    # Mapping Enum -> Filename
    TEMPLATE_FILES = {
        EMAIL_TEMPLATES.welcome: "welcome_trial.html",
        EMAIL_TEMPLATES.reset_password: "reset_password.html",
        EMAIL_TEMPLATES.verify_email: "verify_email.html", 
        EMAIL_TEMPLATES.password_changed: "password_changed.html",
        EMAIL_TEMPLATES.invite_user: "invite_user.html", 
        EMAIL_TEMPLATES.new_login: "new_login.html", 
        EMAIL_TEMPLATES.subscription_active: "subscription_active.html",
        EMAIL_TEMPLATES.trial_expired: "trial_expired.html",
    }

    @staticmethod
    def send_email(to, subject, template=None, context=None, html_content=None, company_id=None, user_id=None):
        """
        Main entry point for sending emails.
        :param to: List of recipients or single email string.
        :param subject: Email subject.
        :param template: (Optional) EMAIL_TEMPLATES Enum member.
        """
        api_key = os.getenv('RESEND_API_KEY')
        if not api_key:
            print("⚠️ RESEND Error: Missing RESEND_API_KEY.")
            return False, "Missing API Key"

        resend.api_key = api_key
        
        # Default sender from environment
        from_name = os.getenv('EMAIL_NAME', 'NorthWay CRM')
        from_email_addr = os.getenv('EMAIL_FROM', 'no-reply@northwaycompany.com.br')
        from_full = f"{from_name} <{from_email_addr}>"

        if isinstance(to, str):
            to = [to]

        # 1. Branding Context (Multi-company)
        company = None
        if company_id:
            company = Company.query.get(company_id)
        
        # 2. Resolve Template
        if template:
            # Enforce Enum usage
            if not isinstance(template, EMAIL_TEMPLATES):
                print(f"❌ Email Error: Invalid template type {type(template)}. Expected EMAIL_TEMPLATES Enum.")
                return False, "Invalid template type"
                
            filename = EmailService.TEMPLATE_FILES.get(template)
            if not filename:
                 return False, f"No file mapped for template {template.name}"

            if not context:
                context = {}
            
            # Inject Global Branding into context
            context['company'] = company
            context['app_name'] = from_name
            context['now'] = datetime.now()
            
            try:
                html_content = render_template(f"emails/{filename}", **context)
            except Exception as e:
                print(f"❌ Template Render Error: {e}")
                return False, f"Template error: {e}"

        # 3. Disparo via Resend
        try:
            params = {
                "from": from_full,
                "to": to,
                "subject": subject,
                "html": html_content,
            }
            
            response = resend.Emails.send(params)
            
            # Extract Resend Message ID
            # Resend SDK returns a dict like {'id': '...'} or an object
            provider_id = None
            if isinstance(response, dict):
                 provider_id = response.get('id')
            elif hasattr(response, 'id'):
                 provider_id = response.id

            # 4. Log the success in Database
            EmailLog.create_log(
                company_id=company_id,
                user_id=user_id,
                email_to=to[0] if to else "N/A",
                subject=subject,
                status='sent',
                provider='resend',
                provider_message_id=provider_id
            )
            
            return True, response
        except Exception as e:
            error_msg = str(e)
            print(f"❌ RESEND Error: {error_msg}")
            
            # Log the failure
            EmailLog.create_log(
                company_id=company_id,
                user_id=user_id,
                email_to=to[0] if to else "N/A",
                subject=subject,
                status='failed',
                provider='resend',
                error_message=error_msg
            )
            
            return False, error_msg
