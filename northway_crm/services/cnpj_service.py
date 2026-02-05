import requests
from flask import current_app
import os

class CNPJAService:
    # URL Base for Paid/Commercial API
    BASE_URL = "https://api.cnpja.com"
    OPEN_URL = "https://open.cnpja.com"
    
    @classmethod
    def get_headers(cls, api_key=None):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = api_key
        return headers

    @classmethod
    def search_by_name(cls, name, api_key):
        """
        Searches for companies by name. (Paid API)
        """
        if not api_key:
            return {"error": "API Key required for name search"}
            
        url = f"{cls.BASE_URL}/office"
        params = {"names.in": name}
        
        try:
            response = requests.get(url, params=params, headers=cls.get_headers(api_key), timeout=10)
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                
                # Normalize for frontend expectations (tax_id and name)
                normalized = []
                for r in records:
                    normalized.append({
                        'tax_id': r.get('taxId'),
                        'name': r.get('company', {}).get('name') or r.get('alias'),
                        'alias': r.get('alias'),
                        'status': r.get('status'),
                        'address': r.get('address')
                    })
                return normalized
            else:
                current_app.logger.error(f"CNPJA Search Error: {response.text}")
                return {"error": response.text, "status": response.status_code}
        except Exception as e:
            current_app.logger.error(f"CNPJA Connection Error: {e}")
            return {"error": str(e)}

    @classmethod
    def get_by_cnpj(cls, cnpj, api_key=None):
        """
        Fetches detailed data for a specific CNPJ.
        Uses paid API if key is provided, otherwise uses free Open API.
        """
        # Clean CNPJ
        clean_cnpj = "".join(filter(str.isdigit, cnpj))
        
        if api_key:
            url = f"{cls.BASE_URL}/office/{clean_cnpj}"
            headers = cls.get_headers(api_key)
        else:
            url = f"{cls.OPEN_URL}/office/{clean_cnpj}"
            headers = cls.get_headers()
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                current_app.logger.error(f"CNPJA API Error ({url}): {response.text}")
                return {"error": response.text, "status": response.status_code}
        except Exception as e:
            current_app.logger.error(f"CNPJA Connection Error: {e}")
            return {"error": str(e)}
