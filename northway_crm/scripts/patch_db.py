
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def patch():
    with app.app_context():
        print("Checking table 'transaction'...")
        res = db.session.execute(text("PRAGMA table_info('transaction')")).fetchall()
        print("Columns found:", [r[1] for r in res])
        
        has_client_id = any(r[1] == 'client_id' for r in res)
        if not has_client_id:
            print("Adding client_id...")
            try:
                db.session.execute(text('ALTER TABLE "transaction" ADD COLUMN client_id INTEGER'))
                db.session.commit()
            except Exception as e: print(e)
            
        columns_to_add = [
            ('asaas_id', 'TEXT'),
            ('asaas_invoice_url', 'TEXT'),
            ('installment_number', 'INTEGER'),
            ('total_installments', 'INTEGER'),
            ('cancellation_reason', 'TEXT')
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in [r[1] for r in res]:
                print(f"Adding {col_name}...")
                try:
                    db.session.execute(text(f'ALTER TABLE "transaction" ADD COLUMN {col_name} {col_type}'))
                    db.session.commit()
                except Exception as e:
                    print(f"Error adding {col_name}: {e}")


if __name__ == "__main__":
    patch()
