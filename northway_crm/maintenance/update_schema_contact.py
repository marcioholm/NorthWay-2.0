from flask import current_app
from sqlalchemy import text
from app import db 

# This script is now designed to run INSIDE the Flask application context.
# It uses the SQLAlchemy connection from the running app.

def update_schema():
    print("Updating schema via SQLAlchemy Engine...")
    
    # 1. Create Contact Table
    # Using raw SQL for direct control, compatible with SQLite (Vercel default)
    create_contact_sql = text('''
    CREATE TABLE IF NOT EXISTS contact (
        id INTEGER PRIMARY KEY,
        uuid VARCHAR(36) NOT NULL UNIQUE,
        company_id INTEGER NOT NULL,
        phone VARCHAR(50) NOT NULL,
        created_at DATETIME,
        FOREIGN KEY(company_id) REFERENCES company(id)
    )
    ''')
    
    try:
        db.session.execute(create_contact_sql)
        print("Created contact table (if not exists).")
    except Exception as e:
         print(f"Error creating contact table: {e}")
         # Continue anyway as it might exist

    # 2. Add contact_uuid to tables
    tables = [
        'lead', 'client', 'whats_app_message', 
        'contract', 'transaction', 'interaction'
    ]
    
    # Get current columns to check if migration needed
    # Note: Reflection is better, but raw PRAGMA is SQLite specific. 
    # Since we know Vercel uses SQLite for this project (based on app.py), 
    # we can stick to SQLite-ish syntax OR use a safer add-column approach.
    
    connection = db.engine.connect()
    trans = connection.begin()
    
    for table in tables:
        try:
            # Universal "Add Column if not exists" is hard in raw SQL.
            # We'll try to add it and ignore "duplicate column" errors.
            alter_sql = text(f'ALTER TABLE "{table}" ADD COLUMN contact_uuid VARCHAR(36) REFERENCES contact(uuid)')
            connection.execute(alter_sql)
            print(f"Added contact_uuid to {table}")
        except Exception as e:
            # 90% chance this is "column already exists"
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print(f"contact_uuid already in {table}")
            else:
                 print(f"Error updating {table}: {e}")
                 
    trans.commit()
    connection.close()
    print("Schema update complete.")

if __name__ == '__main__':
    # For local manual run
    from app import app
    with app.app_context():
        update_schema()
