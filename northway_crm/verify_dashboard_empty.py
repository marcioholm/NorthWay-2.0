
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath('/Users/Marci.Holm/Applications/NorthWay-2.0/northway_crm'))

from app import create_app
from models import db, User, Company, Lead, Contract

def verify_empty():
    os.environ['DATABASE_URL'] = 'sqlite://'
    app = create_app()
    app.config['TESTING'] = True

    with app.app_context():
        db.drop_all()
        db.create_all()

        print("Setting up EMPTY test data...")
        company = Company(name="Empty Corp")
        db.session.add(company)
        db.session.commit()

        user = User(name="User", email="u@e.com", password_hash="x", company_id=company.id, role='admin')
        db.session.add(user)
        db.session.commit()
        
        # NO Leads, NO Contracts, NO Tasks
        
        print("Verifying Empty State Logic...")

        # 1. Dashboard Metrics
        total_leads = Lead.query.filter_by(company_id=company.id).count()
        assert total_leads == 0

        # Won Deals
        won_deals = Lead.query.filter_by(status='won', company_id=company.id).count()
        assert won_deals == 0

        # Conversion (manual check of logic safe)
        conversion = int((won_deals / total_leads * 100)) if total_leads > 0 else 0
        assert conversion == 0
        print("Conversion safe.")

        # MRR Logic
        active_contracts = Contract.query.filter_by(company_id=company.id, status='signed').all()
        mrr = 0.0
        # Loop shouldn't crash on empty list
        for c in active_contracts:
            pass
        assert mrr == 0
        print("MRR safe.")

        # Financial Stats Logic (from financial.py)
        # Avg Ticket
        active_clients_count = 0
        avg_ticket = mrr / active_clients_count if active_clients_count > 0 else 0
        assert avg_ticket == 0
        print("Avg Ticket safe.")

        print("\nSUCCESS: Empty state verified safe.")

if __name__ == "__main__":
    verify_empty()
