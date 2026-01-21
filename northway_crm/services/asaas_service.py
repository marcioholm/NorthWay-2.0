import requests
from flask import current_app
import os

class AsaasService:
    BASE_URL = "https://www.asaas.com/api/v3" # Or sandbox: https://sandbox.asaas.com/api/v3
    
    @staticmethod
    def get_headers():
        api_key = os.environ.get('ASAAS_API_KEY')
        if not api_key:
            raise ValueError("ASAAS_API_KEY not configured")
        return {
            "access_token": api_key,
            "Content-Type": "application/json"
        }

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
            response = requests.post(f"{cls.BASE_URL}/customers", json=payload, headers=cls.get_headers())
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
            response = requests.post(f"{cls.BASE_URL}/subscriptions", json=payload, headers=cls.get_headers())
            if response.status_code == 200:
                data = response.json()
                return data.get('id')
            else:
                current_app.logger.error(f"Asaas Create Subscription Error: {response.text}")
                return None
        except Exception as e:
            current_app.logger.error(f"Asaas Connection Error: {e}")
            return None
