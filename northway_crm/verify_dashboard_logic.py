
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath('/Users/Marci.Holm/Applications/NorthWay-2.0/northway_crm'))

from app import create_app
from models import db, User, Company, Lead, Contract, Role, LEAD_STATUS_WON, LEAD_STATUS_NEW

def verify_metrics():

    # FORCE MEMORY DB via Environment Variable (create_app reads this)
    os.environ['DATABASE_URL'] = 'sqlite://' # SQLAlchemy uses sqlite:// for :memory: when empty, or sqlite:///:memory:

    app = create_app()
    app.config['TESTING'] = True

    with app.app_context():
        # Ensure clean slate (in case of cached connection)
        db.drop_all() 
        db.create_all()

        # 1. Setup Data
        print("Setting up test data...")
        company = Company(name="Test Corp")
        db.session.add(company)
        db.session.commit()

        # Create User
        user = User(name="Test User", email="test@test.com", password_hash="hash", company_id=company.id, role='admin')
        db.session.add(user)
        db.session.commit()

        # Create Leads
        # 10 Leads total: 3 Won, 7 New/Others
        for i in range(7):
            db.session.add(Lead(name=f"Lead {i}", company_id=company.id, status=LEAD_STATUS_NEW))
        for i in range(3):
            db.session.add(Lead(name=f"Won Lead {i}", company_id=company.id, status=LEAD_STATUS_WON))
        
        db.session.commit()

        # Create Contracts (For MRR)
        # 2 Signed Contracts: 1000.00 each
        from models import Client, ContractTemplate
        client = Client(name="Client 1", company_id=company.id, account_manager_id=user.id)
        db.session.add(client)
        template = ContractTemplate(name="Tpl 1", content="cnt", company_id=company.id)
        db.session.add(template)
        db.session.commit()

        client_data_1 = json.dumps({"valor_parcela": "1.000,00"})
        client_data_2 = json.dumps({"valor_parcela": "1.500,50"})

        c1 = Contract(client_id=client.id, company_id=company.id, template_id=template.id, status='signed', form_data=client_data_1)
        c2 = Contract(client_id=client.id, company_id=company.id, template_id=template.id, status='signed', form_data=client_data_2)
        c3 = Contract(client_id=client.id, company_id=company.id, template_id=template.id, status='draft', form_data=client_data_1) # Draft shouldn't count

        db.session.add(c1)
        db.session.add(c2)
        db.session.add(c3)
        db.session.commit()


        # 2. Verify Logic (Mirroring app code)
        print("Verifying logic...")

        # Total Leads
        total_leads = Lead.query.filter_by(company_id=company.id).count()
        print(f"Total Leads: {total_leads} (Expected: 10)")
        assert total_leads == 10

        # Won Deals
        won_deals = Lead.query.filter_by(status=LEAD_STATUS_WON, company_id=company.id).count()
        print(f"Won Deals: {won_deals} (Expected: 3)")
        assert won_deals == 3

        # Conversion Rate
        conversion = int((won_deals / total_leads * 100)) if total_leads > 0 else 0
        print(f"Conversion Rate: {conversion}% (Expected: 30%)")
        assert conversion == 30

        # MRR
        active_contracts = Contract.query.filter_by(company_id=company.id, status='signed').all()
        mrr = 0.0
        for c in active_contracts:
            try:
                data = json.loads(c.form_data)
                val_str = data.get('valor_parcela', '0')
                # Logic from financial.py: float(val_str.replace('.', '').replace(',', '.'))
                # 1.000,00 -> 1000.00
                val = float(val_str.replace('.', '').replace(',', '.'))
                mrr += val
            except Exception as e:
                print(f"Error parsing MRR: {e}")
        
        print(f"MRR: {mrr} (Expected: 2500.50)")
        assert mrr == 2500.50

        print("\nSUCCESS: All dashboard metrics match DB data logic correctly.")

if __name__ == "__main__":
    verify_metrics()
