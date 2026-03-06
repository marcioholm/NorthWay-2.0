import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'northway_crm')))

from app import create_app
from flask.testing import FlaskClient

os.environ.pop('ASAAS_WEBHOOK_TOKEN', None)
app = create_app()
app.config['ASAAS_WEBHOOK_TOKEN'] = None

payload = {
 "id": "evt_05b708f961d739ea7eba7e4db318f621&1225683381",
 "event": "PAYMENT_CREATED",
 "dateCreated": "2026-02-18 02:10:34",
 "account": {
  "id": "ec2b4375-159e-4203-81f4-93750c836d73",
  "ownerId": None
 },
 "payment": {
  "object": "payment",
  "id": "pay_f1iwt235litu6als",
  "dateCreated": "2026-02-18",
  "customer": "cus_000126323104",
  "subscription": "sub_gc1ez0tqwf1mueq1",
  "checkoutSession": None,
  "paymentLink": None,
  "value": 197,
  "netValue": 190.62,
  "description": "NorthWay CRM - CONECTA LTDA (pro/pro)",
  "billingType": "UNDEFINED",
  "status": "PENDING",
  "dueDate": "2026-03-29",
  "originalDueDate": "2026-03-29",
  "invoiceUrl": "https://www.asaas.com/i/f1iwt235litu6als",
  "invoiceNumber": "746494570",
  "externalReference": None,
  "deleted": False,
  "anticipated": False,
  "anticipable": False,
  "nossoNumero": "411516862",
  "bankSlipUrl": "https://www.asaas.com/b/pdf/f1iwt235litu6als"
 }
}

with app.test_client() as client:
    # Use Company ID 1
    res = client.post('/api/webhooks/asaas/1', json=payload)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.json}")
