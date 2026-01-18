import requests
import re
from models import db, Integration, Client, Transaction, FinancialEvent
from utils import update_integration_health, retry_request
from datetime import datetime

class AsaasService:
    BASE_URL_SANDBOX = "https://sandbox.asaas.com/api/v3"
    BASE_URL_PROD = "https://api.asaas.com/v3"

    @staticmethod
    def get_base_url(env='sandbox'):
        return AsaasService.BASE_URL_PROD if env == 'production' else AsaasService.BASE_URL_SANDBOX

    @staticmethod
    def get_api_key(company_id):
        integration = Integration.query.filter_by(company_id=company_id, service='asaas', is_active=True).first()
        if not integration or not integration.api_key:
            return None, None # No active integration
        
        # Determine environment from config (JSON) or default to sandbox if missing
        env = 'sandbox'
        if integration.config_json:
            import json
            try:
                config = json.loads(integration.config_json)
                env = config.get('environment', 'sandbox')
            except:
                pass
        
        return integration.api_key, env

    @staticmethod
    def get_headers(api_key):
        return {
            "access_token": api_key,
            "Content-Type": "application/json"
        }

    @staticmethod
    def create_customer(company_id, client):
        """
        Creates or updates a customer in ASAAS.
        """
        api_key, env = AsaasService.get_api_key(company_id)
        if not api_key:
            raise Exception("ASAAS Integration not configured")

        url = f"{AsaasService.get_base_url(env)}/customers"
        
        # Clean Document (Remove non-digits)
        raw_doc = client.document
        clean_doc = None
        if raw_doc:
            clean_doc = re.sub(r'\D', '', raw_doc)

        # 1. Search by CPF/CNPJ (Priority)
        if clean_doc:
            search_params = {"cpfCnpj": clean_doc}
            try:
                @retry_request()
                def perform_search():
                    return requests.get(url, headers=AsaasService.get_headers(api_key), params=search_params, timeout=10)
                
                res_search = perform_search()
                if res_search.status_code == 200:
                    data = res_search.json().get('data', [])
                    if data:
                        return data[0]['id']
            except Exception as e:
                print(f"Error searching customer by Doc: {e}")

        # 2. Search by Email (Secondary check to avoid duplication if Doc missing)
        email = client.email or client.email_contact
        if email:
            search_params = {"email": email}
            try:
                @retry_request()
                def perform_search():
                    return requests.get(url, headers=AsaasService.get_headers(api_key), params=search_params, timeout=10)
                
                res_search = perform_search()
                if res_search.status_code == 200:
                    data = res_search.json().get('data', [])
                    if data:
                        return data[0]['id']
            except Exception as e:
                print(f"Error searching customer by Email: {e}")

        payload = {
            "name": client.name,
            "email": email,
            "cpfCnpj": clean_doc, # Send cleaned doc
            "mobilePhone": client.phone,
            "externalReference": str(client.id)
        }

        try:
            @retry_request()
            def perform_create():
                return requests.post(url, headers=AsaasService.get_headers(api_key), json=payload, timeout=15)
            
            response = perform_create()
            if response.status_code == 200:
                update_integration_health(company_id, 'asaas')
                return response.json()['id']
            elif response.status_code == 400:
                 err_json = response.json()
                 msg = "Erro Asaas: "
                 if 'errors' in err_json:
                     msg += ", ".join([e.get('description', '') for e in err_json['errors']])
                 raise Exception(msg)
            else:
                raise Exception(f"Failed to create customer: {response.status_code}")
        except Exception as e:
            update_integration_health(company_id, 'asaas', error=e)
            raise e

    @staticmethod
    def create_payment(company_id, customer_asaas_id, transaction):
        """
        Creates a payment (boleto/pix) in ASAAS.
        """
        api_key, env = AsaasService.get_api_key(company_id)
        if not api_key:
            raise Exception("ASAAS Integration not configured")

        url = f"{AsaasService.get_base_url(env)}/payments"

        payload = {
            "customer": customer_asaas_id,
            "billingType": "BOLETO", # Default, can be passed in transaction logic later
            "dueDate": transaction.due_date.strftime('%Y-%m-%d'),
            "value": transaction.amount,
            "description": transaction.description,
            "externalReference": str(transaction.id)
        }
        
        # Handling Installments logic if needed (ASAAS handles 'installmentCount' in params if creating installment object, 
        # but here we might be creating individual charges. 
        # If transaction has installment_number, it means it's part of a set generated by CRM.
        # So we just treat it as a single payment linked to the customer.)

        try:
            @retry_request()
            def perform_payment():
                return requests.post(url, headers=AsaasService.get_headers(api_key), json=payload, timeout=15)
            
            response = perform_payment()
            
            if response.status_code == 200:
                data = response.json()
                transaction.asaas_id = data['id']
                transaction.asaas_invoice_url = data.get('invoiceUrl') or data.get('bankSlipUrl')
                update_integration_health(company_id, 'asaas')
                return data
            else:
                err_json = response.json() if response.status_code == 400 else {}
                msg = ", ".join([e.get('description', '') for e in err_json.get('errors', [])]) if err_json else response.text
                raise Exception(f"Failed to create payment: {msg}")
        except Exception as e:
            update_integration_health(company_id, 'asaas', error=e)
            raise e

    @staticmethod
    def cancel_payment(company_id, payment_id):
        """
        Cancels/Deletes a payment in ASAAS.
        """
        api_key, env = AsaasService.get_api_key(company_id)
        if not api_key:
            return False # Just ignore if no integration
            
        url = f"{AsaasService.get_base_url(env)}/payments/{payment_id}"
        
        try:
            @retry_request()
            def perform_cancel():
                return requests.delete(url, headers=AsaasService.get_headers(api_key), timeout=10)
            
            response = perform_cancel()
            
            if response.status_code in [200, 204, 404]:
                update_integration_health(company_id, 'asaas')
                return True
            else:
                print(f"Failed to cancel payment {payment_id}: {response.text}")
                return False
        except Exception as e:
            print(f"Error canceling payment: {e}")
            update_integration_health(company_id, 'asaas', error=e)
            return False

    @staticmethod
    def configure_webhook(company_id, webhook_url):
        """
        Configures the ASAAS webhook programmatically.
        """
        api_key, env = AsaasService.get_api_key(company_id)
        if not api_key:
            raise Exception("ASAAS Integration not configured")

        url = f"{AsaasService.get_base_url(env)}/webhooks"
        
        payload = {
            "name": "NorthWay CRM Webhook",
            "url": webhook_url,
            "email": "suporte@northway.com.br",
            "enabled": True,
            "sendType": "SEQUENTIALLY",
            "events": [
                "PAYMENT_RECEIVED",
                "PAYMENT_CONFIRMED",
                "PAYMENT_OVERDUE",
                "PAYMENT_REFUNDED",
                "PAYMENT_REVERSED",
                "PAYMENT_DELETED"
            ]
        }
        
        try:
            @retry_request()
            def perform_config():
                return requests.post(url, headers=AsaasService.get_headers(api_key), json=payload, timeout=15)
            
            response = perform_config()
            if response.status_code in [200, 201]:
                return True
            else:
                err_json = response.json() if response.status_code == 400 else {}
                msg = ", ".join([e.get('description', '') for e in err_json.get('errors', [])]) if err_json else response.text
                if "URL already exists" in msg or "already been created" in msg:
                     # If already exists, we consider it a success for simplicity, or we could find and update
                     return True
                raise Exception(f"Failed to configure webhook: {msg}")
        except Exception as e:
            raise e
