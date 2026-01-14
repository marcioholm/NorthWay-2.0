import sqlite3
import os

db_path = 'instance/crm.db'

def add_column(cursor, table, column, type_def):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
        print(f"Added {column} to {table}")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print(f"Column {column} already exists in {table}")
        else:
            print(f"Error adding {column} to {table}: {e}")

if not os.path.exists(db_path):
    print("DB not found at", db_path)
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Contract Drafts
        add_column(cursor, 'contract', 'form_data', 'TEXT')

        conn.commit()
        print("Migration V3 complete.")
    except Exception as e:
        print(f"Migration Error: {e}")
    finally:
        if conn:
            conn.close()
