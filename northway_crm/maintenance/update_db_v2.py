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
        
        # Client Fields
        add_column(cursor, 'client', 'document', 'VARCHAR(20)')
        add_column(cursor, 'client', 'address', 'VARCHAR(255)')
        add_column(cursor, 'client', 'representative', 'VARCHAR(100)')
        add_column(cursor, 'client', 'representative_cpf', 'VARCHAR(20)')
        add_column(cursor, 'client', 'email_contact', 'VARCHAR(120)')
        
        # Company Fields
        add_column(cursor, 'company', 'document', 'VARCHAR(20)')
        add_column(cursor, 'company', 'address', 'VARCHAR(255)')
        add_column(cursor, 'company', 'representative', 'VARCHAR(100)')
        add_column(cursor, 'company', 'representative_cpf', 'VARCHAR(20)')
        
        # ContractTemplate Fields
        add_column(cursor, 'contract_template', 'type', "VARCHAR(20) DEFAULT 'contract'")

        conn.commit()
        print("Migration V2 complete.")
    except Exception as e:
        print(f"Migration Error: {e}")
    finally:
        if conn:
            conn.close()
