
from app import create_app, db
from models import User, Company, Client, ServiceOrder
from flask_login import login_user

app = create_app()


from sqlalchemy import text

def patch_schema(app):
    """
    Patches the SQLite database to include missing columns (GMB, ServiceOrder)
    that might be causing SQLAlchemy crashes due to migration drift.
    """
    with app.app_context():
        with db.engine.connect() as conn:
            print("🔧 Patching Schema...")
            # Patch Client Table
            for col, dtype in [
                ('gmb_link', 'VARCHAR(500)'),
                ('gmb_rating', 'FLOAT DEFAULT 0.0'),
                ('gmb_reviews', 'INTEGER DEFAULT 0'),
                ('gmb_photos', 'INTEGER DEFAULT 0'),
                ('gmb_last_sync', 'TIMESTAMP')
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE client ADD COLUMN {col} {dtype}"))
                    print(f"   -> Added {col} to Client")
                except Exception as e:
                    pass # Column likely exists
            
            # Ensure ServiceOrder table exists (Redundant if create_all works, but safe)
            db.create_all()
            conn.commit()
            print("✅ Schema Patching Complete.")

def test_service_order_flow():
    with app.app_context():
        patch_schema(app)
        
        # Setup Data
        print("🛠 Setting up test data...")
        company = Company.query.first()
        if not company:
            print("❌ No company found.")
            return

        user = User.query.filter_by(company_id=company.id).first()
        if not user:
            print("❌ No user found.")
            return
            
        client = Client.query.filter_by(company_id=company.id).first()
        if not client:
            # Create dummy client
            print("⚠️ No client found, creating dummy...")
            client = Client(name="Test Client", company_id=company.id)
            db.session.add(client)
            db.session.commit()

        print(f"✅ Using User: {user.name} (ID: {user.id})")
        print(f"✅ Using Client: {client.name} (ID: {client.id})")

        # Create Test Client
        client_app = app.test_client()
        
        # Login
        with client_app.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

        # 1. Test Creation
        print("\n🧪 Testing Creation...")
        payload = {
            "client_id": client.id,
            "title": "OS de Teste Automatizada",
            "description": "Teste de verification script",
            "value": 150.50
        }
        
        resp = client_app.post('/api/service-orders/create', json=payload)
        print(f"Response Status: {resp.status_code}")
        print(f"Response Data: {resp.json}")
        
        if resp.status_code != 200 or not resp.json.get('success'):
            print("❌ Creation Failed.")
            return
            
        os_id = resp.json['id']
        print(f"✅ OS Created with ID: {os_id}")

        # Verify DB
        os_obj = ServiceOrder.query.get(os_id)
        if os_obj and os_obj.value == 150.50:
            print("✅ Database Verification Passed.")
        else:
            print("❌ Database Verification Failed.")
            return

        # 2. Test Cancellation
        print("\n🧪 Testing Cancellation...")
        cancel_payload = {
            "reason": "Teste de cancelamento",
            "category": "OUTROS",
            "cancel_asaas": False # Avoid making real external requests if possible, or mock
        }
        
        resp = client_app.post(f'/api/service-orders/{os_id}/cancel', json=cancel_payload)
        print(f"Response Status: {resp.status_code}")
        print(f"Response Data: {resp.json}")

        if resp.status_code != 200 or not resp.json.get('success'):
            print("❌ Cancellation Failed.")
            return

        # Verify DB Cancellation
        db.session.expire(os_obj)
        os_obj = ServiceOrder.query.get(os_id)
        if os_obj.status == 'CANCELADA' and os_obj.canceled_by_user_id == user.id:
            print("✅ Cancellation Verification Passed (Status & User Check).")
        else:
            print(f"❌ Cancellation DB Check Failed. Status: {os_obj.status}")
            return
            
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY.")

if __name__ == "__main__":
    test_service_order_flow()
