
import os
import requests
import json
from app import create_app
from models import db, Integration, WhatsAppMessage

app = create_app()

def run_diagnostic(company_id):
    with app.app_context():
        intg = Integration.query.filter_by(company_id=company_id, service='z_api', is_active=True).first()
        if not intg:
            print(f"ERROR: No ACTIVE Z-API integration found for company {company_id}")
            return
            
        config = json.loads(intg.config_json)
        base_url = f"{config['api_url']}/instances/{config['instance_id']}/token/{intg.api_key}"
        headers = {'Client-Token': config['client_token']} if config.get('client_token') else {}
        
        print(f"--- Z-API DIAGNOSTIC FOR COMPANY {company_id} ---")
        
        # 1. Test Connectivity
        try:
            res = requests.get(f"{base_url}/status", headers=headers, timeout=10)
            print(f"Status: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Connectivity Error: {e}")
            
        # 2. Check Instance Data (See Webhook URL)
        try:
            res = requests.get(f"{base_url}/instance-data", headers=headers, timeout=10)
            print(f"Instance Data: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Instance Data Error: {e}")

        # 3. List Last Messages in DB
        msgs = WhatsAppMessage.query.filter_by(company_id=company_id).order_by(WhatsAppMessage.id.desc()).limit(3).all()
        print(f"--- Last 3 DB Messages (Company {company_id}) ---")
        for m in msgs:
            print(f"ID {m.id}: {m.direction} | {m.status} | {m.content[:30]} | {m.created_at}")

if __name__ == "__main__":
    run_diagnostic(14)
