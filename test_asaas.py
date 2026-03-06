import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'northway_crm')))

from app import create_app
from models import db, Integration, Contract, Transaction
from services.asaas_service import create_payment

app = create_app()

with app.app_context():
    contract = Contract.query.order_by(Contract.id.desc()).first()
    if not contract:
        print("No contracts found to test with.")
        sys.exit(0)
    
    tenant_integration = Integration.query.filter_by(
        company_id=contract.company_id, 
        service='asaas', 
        is_active=True
    ).first()
    
    if not tenant_integration or not tenant_integration.api_key:
        print(f"No active Asaas integration found for company_id {contract.company_id}.")
        sys.exit(0)

    tenant_api_key = tenant_integration.api_key
    asaas_customer_id = contract.client.asaas_customer_id

    if not asaas_customer_id:
         print(f"No Asaas customer id found for client {contract.client.id}")
         sys.exit(0)

    try:
        payment, err = create_payment(
            customer_id=asaas_customer_id,
            value=1.0,
            due_date='2026-12-31',
            description=f"Test Boleto #{contract.id}",
            external_ref=99999,
            api_key=tenant_api_key
        )
        if payment:
            print(f"✅ Created Asaas Payment {payment.get('id')}")
        else:
            print(f"❌ Failed to create Asaas Payment: {err}")
    except Exception as bill_e:
        print(f"❌ Exception generating boleto: {bill_e}")
