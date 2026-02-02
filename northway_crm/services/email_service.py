import os
import resend
from flask import render_template, current_app
from models import db, EmailLog, Company, User
from datetime import datetime

class EmailService:
    @staticmethod
    def send_email(to, subject, template=None, context=None, html_content=None, company_id=None, user_id=None):
        """
        Main entry point for sending emails.
        :param to: List of recipients or single email string.
        :param subject: Email subject.
        :param template: (Optional) Name of the HTML template in templates/emails/.
        :param context: (Optional) Dictionary for rendering the template.
        :param html_content: (Optional) Raw HTML if no template is used.
        :param company_id: (Optional) ID of the company for logging and branding.
        :param user_id: (Optional) ID of the user for logging.
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

        # Ensure 'to' is a list
        if isinstance(to, str):
            to = [to]

        # 1. Branding Context (Multi-company)
        company = None
        if company_id:
            company = Company.query.get(company_id)
        
        # 2. Render HTML if template provided
        if template:
            if not context:
                context = {}
            
            # Inject Global Branding into context
            context['company'] = company
            context['app_name'] = from_name
            context['now'] = datetime.now()
            
            try:
                html_content = render_template(f"emails/{template}", **context)
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
