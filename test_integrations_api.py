import requests
import json
import sys
import os

# This script assumes the server is running on http://localhost:5000
# or you can point it to a specific URL.
BASE_URL = "http://localhost:5000"

def test_api_key_interaction(api_key):
    print(f"Testing with API Key: {api_key}")
    
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    # 1. Test List Leads
    print("\n[1] Testing GET /api/v1/leads...")
    res = requests.get(f"{BASE_URL}/api/v1/leads", headers=headers)
    print(f"Status: {res.status_code}")
    if res.status_code == 200:
        data = res.json()
        print(f"Success: Found {data['count']} leads.")
    else:
        print(f"Error: {res.text}")

    # 2. Test Create Lead
    print("\n[2] Testing POST /api/v1/leads...")
    new_lead = {
        "name": "Lead Teste n8n",
        "email": "n8n_test@example.com",
        "phone": "11999999999",
        "source": "n8n_automation",
        "description": "Criado via teste de integração segura"
    }
    res = requests.post(f"{BASE_URL}/api/v1/leads", headers=headers, json=new_lead)
    print(f"Status: {res.status_code}")
    if res.status_code == 201:
        lead_id = res.json()['data']['id']
        print(f"Success: Created Lead ID {lead_id}")
        
        # 3. Test Update Lead
        print(f"\n[3] Testing PATCH /api/v1/leads/{lead_id}...")
        res = requests.patch(f"{BASE_URL}/api/v1/leads/{lead_id}", headers=headers, json={"status": "em_negociacao"})
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            print("Success: Lead updated.")
    else:
        print(f"Error: {res.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 test_integrations_api.py <SUA_CHAVE_API>")
        sys.exit(1)
    
    test_api_key_interaction(sys.argv[1])
