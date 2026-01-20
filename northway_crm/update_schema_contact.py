import sqlite3
import os

DB_PATH = '/Users/Marci.Holm/Applications/NorthWay-2.0/northway_crm/crm.db'

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Updating schema...")
    
    # 1. Create Contact Table
    try:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS contact (
            id INTEGER PRIMARY KEY,
            uuid VARCHAR(36) NOT NULL UNIQUE,
            company_id INTEGER NOT NULL,
            phone VARCHAR(50) NOT NULL,
            created_at DATETIME,
            FOREIGN KEY(company_id) REFERENCES company(id)
        )
        ''')
        print("Created contact table.")
    except Exception as e:
        print(f"Error creating contact table: {e}")

    # 2. Add contact_uuid to tables
    tables = [
        'lead', 'client', 'whats_app_message', 
        'contract', 'transaction', 'interaction'
    ]
    
    for table in tables:
        try:
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if 'contact_uuid' not in columns:
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN contact_uuid VARCHAR(36) REFERENCES contact(uuid)')
                print(f"Added contact_uuid to {table}")
            else:
                print(f"contact_uuid already in {table}")
                
        except Exception as e:
            print(f"Error updating {table}: {e}")

    conn.commit()
    conn.close()
    print("Schema update complete.")

if __name__ == '__main__':
    if os.path.exists(DB_PATH):
        update_schema()
    else:
        print(f"Database not found at {DB_PATH}")
