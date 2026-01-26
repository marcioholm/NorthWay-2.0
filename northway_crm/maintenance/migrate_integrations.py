from app import create_app, db
from models import Integration

app = create_app()

with app.app_context():
    print("Migrating Integration table...")
    try:
        db.create_all() # This creates only missing tables
        print("Integration table created (if it didn't exist).")
        
        # Verify
        count = Integration.query.count()
        print(f"Current integration count: {count}")

    except Exception as e:
        print(f"Migration error: {e}")

    print("Migration complete.")
