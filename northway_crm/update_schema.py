from app import app
from models import db, WhatsappInstance, WhatsappConversation, WhatsappMessage, WhatsappGroupMember
from sqlalchemy import text

print("Initializing app context...")
with app.app_context():
    print("Creating all tables in database...")
    db.create_all()
    print("New tables created (if they didn't exist).")
    
    # Try to verify tables
    try:
        res = db.session.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';"))
        tables = [row[0] for row in res]
        print("Existing tables:", tables)
        if 'whatsapp_instances' in tables:
            print("SUCCESS: whatsapp_instances table found!")
        else:
            print("FAILURE: whatsapp_instances table NOT found!")
    except Exception as e:
        print("Error verifying tables:", e)
