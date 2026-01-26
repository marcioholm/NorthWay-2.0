import sys
import os

# Ensure we can import from current directory
sys.path.append(os.getcwd())

from app import create_app
from models import db, Lead, User
from sqlalchemy.orm import joinedload

def run_audit():
    app = create_app()
    with app.app_context():
        print("\n--- STARTING DATA ISOLATION AUDIT ---")
        
        # Query 1: Leads assigned to Users from DIFFERENT companies
        # We join User explicitly
        query = db.session.query(Lead, User).join(User, Lead.assigned_to_id == User.id).filter(Lead.company_id != User.company_id)
        
        results = query.all()
        
        if not results:
            print("✅ No cross-company assignments found. Data is clean.")
            return

        print(f"⚠️ FOUND {len(results)} LEADS WITH CROSS-COMPANY ASSIGNMENTS!")
        
        fixed_count = 0
        for lead, user in results:
            print(f"   [FIXING] Lead ID {lead.id} (Company {lead.company_id}) was assigned to User {user.id} ({user.name} - Company {user.company_id})")
            lead.assigned_to_id = None
            fixed_count += 1
            
        try:
            db.session.commit()
            print(f"✅ Successfully fixed {fixed_count} leads. Assigned User set to None.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error saving fixes: {e}")

if __name__ == "__main__":
    run_audit()
