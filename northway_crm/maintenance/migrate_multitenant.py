from app import create_app, db
import sqlite3

def migrate():
    print("Starting Multi-Tenant Migration...")
    
    # 1. Add Columns (SQLite doesn't support easy ALTER ADD COLUMN with constraints, so allow NULL first)
    conn = sqlite3.connect('instance/crm.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE interaction ADD COLUMN company_id INTEGER REFERENCES company(id)")
        print("Added company_id to interaction")
    except Exception as e:
        print(f"Skipping interaction (maybe exists): {e}")

    try:
        cursor.execute("ALTER TABLE 'transaction' ADD COLUMN company_id INTEGER REFERENCES company(id)")
        print("Added company_id to transaction")
    except Exception as e:
        print(f"Skipping transaction (maybe exists): {e}")

    try:
        cursor.execute("ALTER TABLE client_checklist ADD COLUMN company_id INTEGER REFERENCES company(id)")
        print("Added company_id to client_checklist")
    except Exception as e:
        print(f"Skipping client_checklist (maybe exists): {e}")
        
    conn.commit()
    conn.close()
    
    # 2. Populate Data using SQLAlchemy models
    app = create_app()
    with app.app_context():
        # Interactions
        from models import Interaction, Lead, Client, User
        interactions = Interaction.query.filter(Interaction.company_id == None).all()
        print(f"Migrating {len(interactions)} interactions...")
        
        for i in interactions:
            if i.lead_id:
                lead = Lead.query.get(i.lead_id)
                if lead: i.company_id = lead.company_id
                
            elif i.client_id:
                client = Client.query.get(i.client_id)
                if client: i.company_id = client.company_id
                
            elif i.user_id:
                user = User.query.get(i.user_id)
                if user: i.company_id = user.company_id
                
        # Transactions
        from models import Transaction, Contract
        transactions = Transaction.query.filter(Transaction.company_id == None).all()
        print(f"Migrating {len(transactions)} transactions...")
        for t in transactions:
            if t.contract_id:
                contract = Contract.query.get(t.contract_id)
                if contract: t.company_id = contract.company_id

        # Checklists
        from models import ClientChecklist
        checklists = ClientChecklist.query.filter(ClientChecklist.company_id == None).all()
        print(f"Migrating {len(checklists)} checklists...")
        for c in checklists:
            if c.client_id:
                client = Client.query.get(c.client_id)
                if client: c.company_id = client.company_id
                
        db.session.commit()
        print("Migration complete!")

if __name__ == '__main__':
    migrate()
