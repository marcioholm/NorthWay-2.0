# Migration script to add assigned_to_id to client_checklist
import sqlite3
import os

DB_PATH = 'northway_crm/crm.db'

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(client_checklist)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'assigned_to_id' not in columns:
            print("Adding assigned_to_id column to client_checklist...")
            cursor.execute("ALTER TABLE client_checklist ADD COLUMN assigned_to_id INTEGER REFERENCES user(id)")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column assigned_to_id already exists.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    run_migration()
