
import os
import requests
import json

# Manual config based on DB query
INSTANCE_ID = "3ED6B3F7B03131004C739EFD83BB2141"
API_URL = "https://api.z-api.io"
CLIENT_TOKEN = "F750fd898fb0f4fc78ef850b2afb024bfS"
API_KEY = "6D48FBAC99C438D63274E71C"

# NEW VERCEL URL
WEBHOOK_BASE = "https://north-way-2-0.vercel.app/api/webhooks/zapi/14"

def update_webhooks():
    base_endpoint = f"{API_URL}/instances/{INSTANCE_ID}/token/{API_KEY}"
    headers = {'Client-Token': CLIENT_TOKEN}
    
    endpoints = [
        "update-webhook-received",
        "update-webhook-sent",
        "update-webhook-message-status",
        "update-webhook-connected",
        "update-webhook-disconnected"
    ]
    
    print(f"--- Updating Webhooks for Z-API Instance {INSTANCE_ID} ---")
    print(f"Target URL: {WEBHOOK_BASE}")
    
def test_send_message():
    base_endpoint = f"{API_URL}/instances/{INSTANCE_ID}/token/{API_KEY}"
    headers = {'Client-Token': CLIENT_TOKEN}
    
    payload = {
        "phone": "5542999896358",
        "message": "CRM TEST: Webhook Force Sync Check"
    }
    
    print("\n--- Sending Test Message ---")
    try:
        res = requests.post(f"{base_endpoint}/send-text", json=payload, headers=headers, timeout=15)
        print(f"Send Status: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Send Error: {e}")

if __name__ == "__main__":
    update_webhooks()
    test_send_message()
