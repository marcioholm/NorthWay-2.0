import os
import requests
import json
from flask import current_app

ASAAS_API_URL = os.environ.get('ASAAS_API_URL', 'https://www.asaas.com/api/v3') # Use 'https://sandbox.asaas.com/api/v3' for test
ASAAS_API_KEY = os.environ.get('ASAAS_API_KEY')

def get_headers(api_key=None):
    return {
        'Content-Type': 'application/json',
        'access_token': api_key or ASAAS_API_KEY
    }

def create_customer(name, email, cpf_cnpj, phone=None, external_id=None, api_key=None):
    """
    Creates or Retrieves a customer in Asaas.
    """
    token = api_key or ASAAS_API_KEY
    if not token:
        print("❌ ERROR: ASAAS_API_KEY not found.")
        return None

    # First, try to find existing customer by CPF/CNPJ to avoid duplicates
    try:
        search_url = f"{ASAAS_API_URL}/customers?cpfCnpj={cpf_cnpj}"
        response = requests.get(search_url, headers=get_headers(token))
        if response.status_code == 200:
            data = response.json()
            if data.get('totalCount', 0) > 0:
                print(f"✅ Customer found in Asaas: {data['data'][0]['id']}")
                return data['data'][0]['id']
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
            return response.json()['id']
        else:
            print(f"❌ Error creating customer in Asaas: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception creating customer: {e}")
        return None

def create_subscription(customer_id, value, next_due_date, cycle='MONTHLY', description="NorthWay CRM Subscription", api_key=None):
    """
    Creates a recurring subscription.
    """
    payload = {
        "customer": customer_id,
        "billingType": "UNDEFINED", # Lets user choose in the payment link (Initial Invoice) or set 'PIX'/'BOLETO' if known
        "value": value,
        "nextDueDate": next_due_date, # YYYY-MM-DD
        "cycle": cycle,
        "description": description
    }
    
    try:
        response = requests.post(f"{ASAAS_API_URL}/subscriptions", json=payload, headers=get_headers(api_key))
        if response.status_code == 200:
            return response.json()
        else:
             print(f"❌ Error creating subscription: {response.text}")
             return None
    except Exception as e:
        print(f"❌ Exception creating subscription: {e}")
        return None

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
