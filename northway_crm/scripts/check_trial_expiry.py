
import sys
import os

# Add parent directory to path to import app and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Company, User, EMAIL_TEMPLATES
from services.email_service import EmailService
from datetime import datetime

app = create_app()

def check_expired_trials():
    with app.app_context():
        print(f"🔎 Checking for expired trials at {datetime.now()}...")
        
        # logic: status is trial AND end_date < now
        expired_companies = Company.query.filter(
            Company.payment_status == 'trial',
            Company.trial_end_date < datetime.utcnow()
        ).all()
        
        print(f"Found {len(expired_companies)} companies to expire.")
        
        for company in expired_companies:
            print(f"Processing {company.name} (ID: {company.id})...")
            
            # 1. Update Status
            company.payment_status = 'expired'
            company.subscription_status = 'inactive'
            company.platform_inoperante = True # Block access?
            
            # 2. Find Admin to notify
            admin = User.query.filter_by(company_id=company.id).first()
            
            if admin:
                print(f"   -> Sending email to {admin.email}")
                EmailService.send_email(
                    to=admin.email,
                    subject="Seu período de teste acabou - NorthWay",
                    template=EMAIL_TEMPLATES.trial_expired,
                    context={
                        'user': admin,
                        'plans_url': 'https://crm.northwaycompany.com.br/payment-plan' 
                    },
                    company_id=company.id,
                    user_id=admin.id
                )
            else:
                print("   -> No user found to notify.")
                
            db.session.commit()
            
        print("Done.")

if __name__ == "__main__":
    check_expired_trials()
