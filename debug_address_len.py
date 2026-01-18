
import requests
import json
import os

# Mock Environment for testing (We don't need real keys if we just want to see validation logic, but for Asaas we need Auth)
# We will use the existing AsaasService logic but with hardcoded values to mimic the crash.

API_URL = "https://api.asaas.com/v3"
# We need to get the API Key for Company 4.
# Since we can't easily access the DB here without full app context, I'll ask for it or use a placeholder if I can't find it.
# Wait, I can't easily run this without the API Key.

# ALTERNATIVE: I already know it's the address.
# The address is: " LOGRADOURO R ABRAO ANTONIO nº 714 - CENTRO - Arapoti/PR CEP: 84990-000 nº 714 - CENTRO - Arapoti/PR CEP: 84990-000"
# Length: ~120 chars. Asaas Limit for address is 100? Or maybe it's the format.

def check_length():
    addr = " LOGRADOURO R ABRAO ANTONIO nº 714 - CENTRO - Arapoti/PR CEP: 84990-000 nº 714 - CENTRO - Arapoti/PR CEP: 84990-000"
    print(f"Address Length: {len(addr)}")
    # Asaas address limit is often 70 or 100 depending on field versions.
    
if __name__ == "__main__":
    check_length()
