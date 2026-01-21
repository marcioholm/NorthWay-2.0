import requests
from flask import current_app
import os

class CNPJAService:
    BASE_URL = "https://api.cnpja.com.br"
    
    @classmethod
    def get_headers(cls, api_key):
        if not api_key:
            raise ValueError("CNPJA API Key not provided")
        return {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }

    @classmethod
    def search_by_name(cls, name, api_key):
        """
        Searches for companies by name.
        """
        url = f"{cls.BASE_URL}/office"
        params = {"names.in": name}
        
        try:
            response = requests.get(url, params=params, headers=cls.get_headers(api_key), timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Commercial API often wraps results in 'data' or 'items'
                if isinstance(data, dict):
                    return data.get('data') or data.get('items') or data
                return data
            else:
                current_app.logger.error(f"CNPJA Search Error: {response.text}")
                return {"error": response.text, "status": response.status_code}
        except Exception as e:
            current_app.logger.error(f"CNPJA Connection Error: {e}")
            return {"error": str(e)}

    @classmethod
    def get_by_cnpj(cls, cnpj, api_key):
        """
        Fetches detailed data for a specific CNPJ.
        """
        # Clean CNPJ
        clean_cnpj = "".join(filter(str.isdigit, cnpj))
        url = f"{cls.BASE_URL}/office/{clean_cnpj}"
        
        try:
            response = requests.get(url, headers=cls.get_headers(api_key), timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                current_app.logger.error(f"CNPJA Details Error: {response.text}")
                return {"error": response.text, "status": response.status_code}
        except Exception as e:
            current_app.logger.error(f"CNPJA Connection Error: {e}")
            return {"error": str(e)}
