import requests
from flask import current_app
import os

class AsaasService:
    BASE_URL = "https://www.asaas.com/api/v3" # Or sandbox: https://sandbox.asaas.com/api/v3
    
    @staticmethod
    def get_headers(api_key=None):
        # 1. Use passed key
        if api_key:
            return {"access_token": api_key, "Content-Type": "application/json"}
            
        # 2. Try Env Var
        env_key = os.environ.get('ASAAS_API_KEY')
        if env_key:
            return {"access_token": env_key, "Content-Type": "application/json"}
            
        # 3. Try Database (Integration)
        # Needs app context
        try:
            from models import Integration
            # We need a company_id, but this method is static. 
            # Usually create_customer passes 'company' object.
            # But get_headers is distinct. 
            # Ideally we should pass company_id to every call or context.
            # For now, let's try to get from current_user if available (Flask Login)
            from flask_login import current_user
            if current_user and current_user.is_authenticated and current_user.company_id:
                integration = Integration.query.filter_by(company_id=current_user.company_id, service='asaas').first()
                if integration and integration.api_key:
                    return {"access_token": integration.api_key, "Content-Type": "application/json"}
        except Exception:
            pass

        raise ValueError("ASAAS_API_KEY not configured in Env or Database")
        
    @staticmethod
    def get_base_url(env='sandbox'):
        # Allow checking DB for environment setting if not passed explicit
        if env == 'sandbox': # Default passed by methods
             # Try to resolve real env from DB if possible
             try:
                from models import Integration
                from flask_login import current_user
                import json
                if current_user and current_user.is_authenticated and current_user.company_id:
                    integration = Integration.query.filter_by(company_id=current_user.company_id, service='asaas').first()
                    if integration and integration.config_json:
                         conf = json.loads(integration.config_json)
                         env = conf.get('environment', 'sandbox')
             except:
                 pass
                 
        if env == 'production':
            return "https://www.asaas.com/api/v3"
        return "https://sandbox.asaas.com/api/v3"

    @classmethod
    def create_customer(cls, user, company):
        """
        Creates a customer in Asaas.
        """
        payload = {
            "name": company.name,
            "email": user.email,
            "mobilePhone": user.phone,
            "cpfCnpj": company.cpf_cnpj,
            "externalReference": str(company.id)
        }
        
        try:
            base_url = cls.get_base_url() # Will resolve from DB/User context
            response = requests.post(f"{base_url}/customers", json=payload, headers=cls.get_headers())
            if response.status_code == 200:
                data = response.json()
                return data.get('id')
            else:
                current_app.logger.error(f"Asaas Create Customer Error: {response.text}")
                return None
        except Exception as e:
            current_app.logger.error(f"Asaas Connection Error: {e}")
            return None

    @classmethod
    def create_subscription(cls, customer_id, plan_type):
        """
        Creates a subscription.
        plan_type: 'monthly' or 'yearly'
        """
        value = 97.00 if plan_type == 'monthly' else 924.00
        cycle = 'MONTHLY' if plan_type == 'monthly' else 'YEARLY'
        
        payload = {
            "customer": customer_id,
            "billingType": "BOLETO", # Default, can be PIX or CREDIT_CARD
            "value": value,
            "cycle": cycle,
            "description": f"Assinatura NorthWay CRM - {plan_type.title()}"
        }
        
        try:
            base_url = cls.get_base_url()
            response = requests.post(f"{base_url}/subscriptions", json=payload, headers=cls.get_headers())
            if response.status_code == 200:
                data = response.json()
                return data # Return full object to access invoiceUrl/billUrl
            else:
                current_app.logger.error(f"Asaas Create Subscription Error: {response.text}")
                return None
        except Exception as e:
            current_app.logger.error(f"Asaas Connection Error: {e}")
            return None
