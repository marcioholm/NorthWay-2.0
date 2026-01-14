from app import create_app, db
from models import WhatsAppMessage

app = create_app()

with app.app_context():
    print("Migrating WhatsAppMessage table...")
    try:
        db.create_all() # Creates missing tables
        print("WhatsAppMessage table created (if it didn't exist).")
        
        # Verify
        count = WhatsAppMessage.query.count()
        print(f"Current message count: {count}")

    except Exception as e:
        print(f"Migration error: {e}")

    print("Migration complete.")
