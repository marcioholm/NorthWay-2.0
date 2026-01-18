
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def check_and_add_column(table, column, type_def):
    print(f"Checking table '{table}' for column '{column}'...")
    # Safe check using PRAGMA
    try:
        res = db.session.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
        existing = [r[1] for r in res]
        if column not in existing:
            print(f"Adding {column} to {table}...")
            db.session.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {type_def}'))
            db.session.commit()
            return True
        else:
            print(f"Column {column} already exists.")
    except Exception as e:
        print(f"Error checking/adding {column}: {e}")
        db.session.rollback()
    return False

def patch():
    with app.app_context():
        # Transaction Fixes
        tx_cols = [
            ('client_id', 'INTEGER'),
            ('asaas_id', 'TEXT'),
            ('asaas_invoice_url', 'TEXT'),
            ('installment_number', 'INTEGER'),
            ('total_installments', 'INTEGER'),
            ('cancellation_reason', 'TEXT')
        ]
        for col, dtype in tx_cols:
            check_and_add_column('transaction', col, dtype)
            
        # Contract Fixes
        added_code = check_and_add_column('contract', 'code', 'TEXT')
        if added_code:
            print("Backfilling Contract Codes...")
            try:
                # Attempt Key Format: CTR-YYYY-ID
                # SQLite Specific syntax
                db.session.execute(text("UPDATE contract SET code = 'CTR-' || strftime('%Y', created_at) || '-' || id WHERE code IS NULL"))
                db.session.commit()
                print("Backfill complete.")
            except Exception as e:
                print(f"Backfill failed (might need manual fix): {e}")

if __name__ == "__main__":
    patch()
