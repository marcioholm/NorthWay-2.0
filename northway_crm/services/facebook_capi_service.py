import requests
import time
import hashlib
from flask import current_app

class FacebookCapiService:
    """
    Service to handle Facebook Conversions API (Server-Side) events.
    """
    
    API_VERSION = "v19.0"
    
    def __init__(self, pixel_id=None, access_token=None):
        self.pixel_id = pixel_id or "775641965566957" # Default from user
        self.access_token = access_token or "EAAMBmPvUms8BQhoZC3njupDzBas80v5LnPb63vY721F4JI8pT9NZAE9CQFte40VajUI4BZBw5nHnsjWnl8dX8ElFaZBCZAp8ZCgbdtzinHRCrceZB6QhJk7ZBBZB8WtnObWMjOdT3xr3WMRM2cnZBrHVStVkqgxtQk3qQvi1KjcPm4bkadaVlHpdz2MB1mF3iuqZAO1fAZDZD"
        self.base_url = f"https://graph.facebook.com/{self.API_VERSION}/{self.pixel_id}/events"

    def hash_data(self, data):
        """Hashes PII data using SHA-256."""
        if not data:
            return None
        return hashlib.sha256(data.strip().lower().encode('utf-8')).hexdigest()

    def send_event(self, event_name, user_data, custom_data=None, event_source_url=None):
        """
        Sends an event to Facebook CAPI.
        
        :param event_name: 'Purchase', 'InitiateCheckout', 'Lead', etc.
        :param user_data: Dict with PII (email, phone, etc.) - keys should be 'em', 'ph', 'fn', 'ln' (already hashed or raw)
        :param custom_data: Dict with value, currency, etc.
        """
        
        # Prepare User Data (Hash if needed)
        hashed_user_data = {}
        for key, val in user_data.items():
            if key in ['em', 'ph', 'fn', 'ln', 'ct', 'st', 'zp', 'country']:
                # If it looks like a hash (64 chars hex), leave it, otherwise hash
                if len(str(val)) == 64 and all(c in '0123456789abcdef' for c in str(val)):
                    hashed_user_data[key] = val
                else:
                    hashed_user_data[key] = self.hash_data(str(val))
            else:
                hashed_user_data[key] = val
                
        # Client IP and User Agent should not be hashed if provided
        if 'client_ip_address' in user_data:
            hashed_user_data['client_ip_address'] = user_data['client_ip_address']
        if 'client_user_agent' in user_data:
            hashed_user_data['client_user_agent'] = user_data['client_user_agent']
        if 'fbp' in user_data:
            hashed_user_data['fbp'] = user_data['fbp']
        if 'fbc' in user_data:
            hashed_user_data['fbc'] = user_data['fbc']

        payload = {
            "data": [
                {
                    "event_name": event_name,
                    "event_time": int(time.time()),
                    "action_source": "website",
                    "user_data": hashed_user_data,
                    "custom_data": custom_data or {},
                    "event_source_url": event_source_url
                }
            ],
            "access_token": self.access_token
        }
        
        try:
            response = requests.post(self.base_url, json=payload)
            if response.status_code == 200:
                print(f"✅ FACEBOOK CAPI: {event_name} sent successfully.")
                return True
            else:
                print(f"❌ FACEBOOK CAPI ERROR: {response.text}")
                return False
        except Exception as e:
            print(f"❌ FACEBOOK CAPI EXCEPTION: {str(e)}")
            return False

    def send_purchase(self, user, amount, transaction_id, url=None):
        """Helper for Purchase events"""
        user_data = {
            "em": user.email,
            "ph": user.phone if hasattr(user, 'phone') else None,
            "fn": user.name.split(" ")[0] if user.name else None
        }
        
        # Cleanup None values
        user_data = {k: v for k, v in user_data.items() if v}
        
        custom_data = {
            "currency": "BRL",
            "value": float(amount),
            "order_id": str(transaction_id)
        }
        
        return self.send_event("Purchase", user_data, custom_data, url)
