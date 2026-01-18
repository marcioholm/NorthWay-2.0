import requests
from models import db, Integration, Client, Transaction, FinancialEvent
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
            import re
            clean_doc = re.sub(r'\D', '', raw_doc)

        # 1. Search by CPF/CNPJ (Priority)
        if clean_doc:
            search_params = {"cpfCnpj": clean_doc}
            try:
                res_search = requests.get(url, headers=AsaasService.get_headers(api_key), params=search_params)
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
                res_search = requests.get(url, headers=AsaasService.get_headers(api_key), params=search_params)
                if res_search.status_code == 200:
                    data = res_search.json().get('data', [])
                    # If found by email, but we have a doc, we might want to update the doc?
                    # For now just return the ID found.
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

        response = requests.post(url, headers=AsaasService.get_headers(api_key), json=payload)
        if response.status_code == 200:
            return response.json()['id']
        elif response.status_code == 400:
             # Handle "Customer with this CPF/CNPJ already exists" error or similar if search failed but creation blocked
             err_json = response.json()
             if 'errors' in err_json:
                 for err in err_json['errors']:
                     if err.get('code') == 'CUSTOMER_ALREADY_EXISTS':
                         # Fallback: Try to search again? Or simpler, just fail for now as search should have caught it.
                         # But wait, sometimes search is eventually consistent?
                         pass
             raise Exception(f"Failed to create customer (Asaas Error): {response.text}")
        else:
            raise Exception(f"Failed to create customer: {response.text}")

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

        response = requests.post(url, headers=AsaasService.get_headers(api_key), json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Update Transaction
            transaction.asaas_id = data['id']
            transaction.asaas_invoice_url = data.get('invoiceUrl') or data.get('bankSlipUrl')
            # db.session.commit() - Let caller handle commit
            return data
        else:
            raise Exception(f"Failed to create payment: {response.text}")

    @staticmethod
    def cancel_payment(company_id, payment_id):
        """
        Cancels/Deletes a payment in ASAAS.
        """
        api_key, env = AsaasService.get_api_key(company_id)
        if not api_key:
            return False # Just ignore if no integration
            
        url = f"{AsaasService.get_base_url(env)}/payments/{payment_id}"
        
        response = requests.delete(url, headers=AsaasService.get_headers(api_key))
        
        # 200 OK or 204 No Content are success. 
        # 404 means already deleted (also success for us).
        if response.status_code in [200, 204, 404]:
            return True
        else:
            # Maybe it's paid or cannot be deleted? 
            # In that case we might try to 'restore' then delete, or just log error.
            print(f"Failed to cancel payment {payment_id}: {response.text}")
            return False
