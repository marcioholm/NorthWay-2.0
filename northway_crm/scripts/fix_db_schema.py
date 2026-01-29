import sqlite3
import os

DB_PATH = 'northway_crm/crm.db'

def fix_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Checking Company table schema...")
    cursor.execute("PRAGMA table_info(company)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # helper to add column
    def add_col(table, col_name, col_type):
        try:
            print(f"Adding {col_name} to {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            print(f"✅ Added {col_name}")
        except Exception as e:
            print(f"⚠️ Could not add {col_name}: {e}")

    # Company Columns
    if 'asaas_customer_id' not in columns: add_col('company', 'asaas_customer_id', 'VARCHAR(50)')
    if 'subscription_id' not in columns: add_col('company', 'subscription_id', 'VARCHAR(50)')
    if 'plan_type' not in columns: add_col('company', 'plan_type', 'VARCHAR(20)')
    if 'cpf_cnpj' not in columns: add_col('company', 'cpf_cnpj', 'VARCHAR(20)')
    if 'payment_status' not in columns: add_col('company', 'payment_status', 'VARCHAR(20)')
    if 'platform_inoperante' not in columns: add_col('company', 'platform_inoperante', 'BOOLEAN')
    if 'overdue_since' not in columns: add_col('company', 'overdue_since', 'DATETIME')
    if 'representative' not in columns: add_col('company', 'representative', 'VARCHAR(100)')
    
    # Transaction Columns (for completeness, though contracts might have created them)
    print("Checking Transaction table schema...")
    cursor.execute("PRAGMA table_info('transaction')") # transaction is reserved word sometimes, quote it
    t_columns = [row[1] for row in cursor.fetchall()]

    if 'asaas_id' not in t_columns: add_col('transaction', 'asaas_id', 'VARCHAR(50)')
    if 'asaas_invoice_url' not in t_columns: add_col('transaction', 'asaas_invoice_url', 'VARCHAR(500)')
    
    # Integration table?
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='integration'")
    if not cursor.fetchone():
        print("Creating Integration table...")
        # We rely on SQLAlchemy to create new tables, but we can double check app startup does it.
        # This script only fixes ALTER TABLE issues.
    
    conn.commit()
    conn.close()
    print("Schema check complete.")

if __name__ == "__main__":
    fix_schema()
