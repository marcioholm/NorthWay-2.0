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
    def get_by_brasilapi(cls, cnpj):
        """
        Fallback to BrasilAPI (Free, No Auth)
        """
        clean_cnpj = "".join(filter(str.isdigit, cnpj))
        url = f"https://brasilapi.com.br/api/cnpj/v1/{clean_cnpj}"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Map BrasilAPI -> CNPJA Structure
                mapped = {
                    "taxId": data.get('cnpj'),
                    "alias": data.get('nome_fantasia'),
                    "founded": data.get('data_inicio_atividade'),
                    "company": {
                        "name": data.get('razao_social'),
                        "equity": data.get('capital_social'),
                        "size": {'text': 'N/A'}, # BrasilAPI often doesn't give simple size text
                        "members": data.get('qsa', []) # Different structure but valid list
                    },
                    "status": {
                        "text": data.get('descricao_situacao_cadastral')
                    },
                    "address": {
                        "street": data.get('logradouro'),
                        "number": data.get('numero'),
                        "district": data.get('bairro'),
                        "city": data.get('municipio'),
                        "state": data.get('uf'),
                        "zip": data.get('cep')
                    },
                    "mainActivity": {
                        "code": data.get('cnae_fiscal'),
                        "text": data.get('cnae_fiscal_descricao')
                    },
                    "emails": [{"address": "N/A"}], # BrasilAPI might not have email easily accessible in same format
                    "phones": [{"area": "", "number": data.get('ddd_telefone_1')}]
                }
                return mapped
            else:
                return {"error": f"BrasilAPI Error: {response.text}", "status": response.status_code}
        except Exception as e:
             return {"error": f"BrasilAPI Connection Error: {str(e)}"}

    @classmethod
    def get_by_cnpj(cls, cnpj, api_key=None):
        """
        Fetches detailed data for a specific CNPJ.
        Uses paid API if key is provided, otherwise uses free Open API.
        Falls back to BrasilAPI on error.
        """
        # Clean CNPJ
        clean_cnpj = "".join(filter(str.isdigit, cnpj))
        
        # 1. Try CNPJA (Paid or Open)
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
            elif response.status_code == 429: # Too Many Requests / Quota Exceeded
                current_app.logger.warning(f"CNPJA Quota Exceeded. Falling back to BrasilAPI. CNPJ: {cnpj}")
                return cls.get_by_brasilapi(clean_cnpj)
            else:
                current_app.logger.error(f"CNPJA API Error ({url}): {response.text}")
                # Optional: Fallback on any error? For now, only on specific valid failures or specific user request.
                # Let's fallback on 500s or 429s.
                if response.status_code >= 500 or response.status_code == 429:
                     return cls.get_by_brasilapi(clean_cnpj)
                
                return {"error": response.text, "status": response.status_code}
        except Exception as e:
            current_app.logger.error(f"CNPJA Connection Error: {e}. Falling back to BrasilAPI.")
            return cls.get_by_brasilapi(clean_cnpj)
