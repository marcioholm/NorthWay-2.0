import os
import requests
import json
from datetime import datetime
from flask import current_app

ASAAS_API_URL = os.environ.get('ASAAS_API_URL', 'https://www.asaas.com/api/v3') # Use 'https://sandbox.asaas.com/api/v3' for test

def get_headers(api_key=None):
    token = api_key or os.environ.get('ASAAS_API_KEY')
    return {
        'Content-Type': 'application/json',
        'access_token': token
    }

def create_customer(name, email, cpf_cnpj, phone=None, external_id=None, api_key=None):
    """
    Creates or Retrieves a customer in Asaas.
    """
    token = api_key or os.environ.get('ASAAS_API_KEY')
    if not token:
        print("❌ ERROR: ASAAS_API_KEY not found.")
        return None, "ASAAS_API_KEY Missing"

    # First, try to find existing customer by CPF/CNPJ to avoid duplicates
    try:
        search_url = f"{ASAAS_API_URL}/customers?cpfCnpj={cpf_cnpj}"
        response = requests.get(search_url, headers=get_headers(token))
        if response.status_code == 200:
            data = response.json()
            if data.get('totalCount', 0) > 0:
                print(f"✅ Customer found in Asaas: {data['data'][0]['id']}")
                return data['data'][0]['id'], None
    except Exception as e:
        print(f"⚠️ Error searching customer in Asaas: {e}")

    # If not found, create new
    payload = {
        "name": name,
        "email": email,
        "cpfCnpj": cpf_cnpj,
        "externalReference": str(external_id) if external_id else None
    }
    if phone:
        payload["mobilePhone"] = phone

    try:
        response = requests.post(f"{ASAAS_API_URL}/customers", json=payload, headers=get_headers(token))
        if response.status_code == 200:
            return response.json()['id'], None
        else:
            error_data = response.json()
            error_msg = error_data.get('errors', [{}])[0].get('description', response.text)
            print(f"❌ Error creating customer in Asaas: {error_msg}")
            return None, error_msg
    except Exception as e:
        print(f"❌ Exception creating customer: {e}")
        return None, str(e)

def get_subscription(subscription_id, api_key=None):
    """
    Retrieves subscription details to check status/validity.
    """
    try:
        response = requests.get(f"{ASAAS_API_URL}/subscriptions/{subscription_id}", headers=get_headers(api_key))
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def create_subscription(customer_id, value, next_due_date, cycle='MONTHLY', description="NorthWay CRM Subscription", api_key=None):
    """
    Creates a recurring subscription.
    """
    payload = {
        "customer": customer_id,
        "billingType": "BOLETO", # Forced BOLETO for immediate visibility in Asaas Dashboard
        "value": value,
        "nextDueDate": next_due_date, # YYYY-MM-DD
        "cycle": cycle,
        "description": description
    }
    
    try:
        response = requests.post(f"{ASAAS_API_URL}/subscriptions", json=payload, headers=get_headers(api_key))
        if response.status_code == 200:
            return response.json(), None
        else:
             print(f"❌ Error creating subscription: {response.text}")
             error_data = response.json()
             error_msg = error_data.get('errors', [{}])[0].get('description', response.text)
             return None, error_msg
    except Exception as e:
        print(f"❌ Exception creating subscription: {e}")
        return None, str(e)

def get_subscription_payments(subscription_id, api_key=None):
    """
    Get pending payments for a subscription to redirect user to payment page.
    """
    try:
        response = requests.get(f"{ASAAS_API_URL}/subscriptions/{subscription_id}/payments", headers=get_headers(api_key))
        if response.status_code == 200:
            return response.json()['data']
        return []
    except Exception as e:
        return []

def delete_subscription(subscription_id, api_key=None):
    """
    Cancels a subscription in Asaas (removes pending boletos).
    """
    try:
        response = requests.delete(f"{ASAAS_API_URL}/subscriptions/{subscription_id}", headers=get_headers(api_key))
        if response.status_code == 200:
            print(f"✅ Subscription {subscription_id} deleted.")
            return True, None
        else:
            error_data = response.json()
            error_msg = error_data.get('errors', [{}])[0].get('description', response.text)
            print(f"⚠️ Error deleting subscription: {error_msg}")
            return False, error_msg
    except Exception as e:
        return False, str(e)

def cancel_payment(payment_id, api_key=None):
    """
    Cancels a specific payment (Cobrança) in Asaas.
    """
    try:
        response = requests.delete(f"{ASAAS_API_URL}/payments/{payment_id}", headers=get_headers(api_key))
        if response.status_code == 200:
            print(f"✅ Payment {payment_id} cancelled/deleted.")
            return True, None
        else:
            error_data = response.json()
            print(f"⚠️ Error cancelling payment: {error_msg}")
            return False, error_msg
    except Exception as e:
        return False, str(e)

def create_payment(customer_id, value, due_date, description, external_ref=None, api_key=None):
    """
    Creates a single payment (cobranca avulsa) - BOLETO/PIX.
    """
    payload = {
        "customer": customer_id,
        "billingType": "BOLETO", # Defaults to Boleto/Pix
        "value": value,
        "dueDate": due_date,
        "description": description,
        "externalReference": str(external_ref) if external_ref else None
    }
    
    try:
        response = requests.post(f"{ASAAS_API_URL}/payments", json=payload, headers=get_headers(api_key))
        if response.status_code == 200:
            return response.json(), None
        else:
             error_data = response.json()
             error_msg = error_data.get('errors', [{}])[0].get('description', response.text)
             return None, error_msg
    except Exception as e:
        return None, str(e)

# --- NFS-e Logic ---

def issue_nfse(payment_id, service_code, iss_rate, description, api_key=None):
    """
    Triggers NFS-e emission for a specific payment in Asaas.
    """
    # NOTE: Asaas has specific endpoints or automations for this. 
    # Usually "POST /api/v3/invoices" linked to a payment or subscription.
    # Here we assume manual trigger linked to a payment.
    
    # Asaas API for NFS-e creation (Invoice)
    # https://docs.asaas.com/reference/criar-uma-nota-fiscal
    
    payload = {
        "payment": payment_id, # Link to the payment
        "serviceDescription": description,
        "observations": "Emitido via NorthWay CRM",
        "serviceCode": service_code, # e.g. '1.03'
        "issTax": iss_rate, # % rate
        "effectiveDate": datetime.now().strftime('%Y-%m-%d') # Emit today
    }
    
    try:
        response = requests.post(f"{ASAAS_API_URL}/invoices", json=payload, headers=get_headers(api_key))
        if response.status_code == 200:
             return response.json(), None
        else:
             error_data = response.json()
             error_msg = error_data.get('errors', [{}])[0].get('description', response.text)
             return None, error_msg
             
    except Exception as e:
        return None, str(e)

def cancel_nfse(nfse_id, api_key=None):
    """
    Cancels an existing NFS-e.
    """
    try:
        response = requests.post(f"{ASAAS_API_URL}/invoices/{nfse_id}/cancel", headers=get_headers(api_key))
        if response.status_code == 200:
             return response.json(), None
        else:
             error_data = response.json()
             error_msg = error_data.get('errors', [{}])[0].get('description', response.text)
             return None, error_msg
    except Exception as e:
        return None, str(e)

def create_webhook(webhook_url, email, api_key=None):
    """
    Configures the webhook URL in Asaas.
    """
    payload = {
        "url": webhook_url,
        "email": email,
        "enabled": True,
        "interrupted": False,
        "apiVersion": 3,
        "sendType": "SEQUENTIALLY",
        "events": [
            "PAYMENT_CREATED", "PAYMENT_RECEIVED", "PAYMENT_CONFIRMED", 
            "PAYMENT_OVERDUE", "PAYMENT_REFUNDED"
        ]
    }
    
    headers = get_headers(api_key)
    
    try:
        # 1. Try to list existing webhooks
        get_res = requests.get(f"{ASAAS_API_URL}/webhooks", headers=headers)
        existing_id = None
        
        if get_res.status_code == 200:
            webhooks = get_res.json().get('data', [])
            if webhooks:
                # Assuming single webhook or taking the first one to update
                existing_id = webhooks[0].get('id')
        
        # 2. Update or Create
        if existing_id:
             # Try PUT for update
             response = requests.put(f"{ASAAS_API_URL}/webhooks/{existing_id}", json=payload, headers=headers)
        else:
             response = requests.post(f"{ASAAS_API_URL}/webhooks", json=payload, headers=headers)
        
        if response.status_code == 200:
             return response.json(), None
        else:
             try:
                 error_data = response.json()
                 # Handle list of errors or single object
                 errors = error_data.get('errors', [])
                 if isinstance(errors, list) and errors:
                     error_msg = errors[0].get('description', response.text)
                 else:
                     error_msg = str(error_data)
             except:
                 error_msg = f"Status {response.status_code}: {response.text}"
             return None, error_msg
    except Exception as e:
        return None, str(e)
