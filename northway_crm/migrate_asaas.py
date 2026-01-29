import os
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

def run_migration():
    with app.app_context():
        print("Starting Asaas Billing Migration (SQLite Compatible)...")
        
        inspector = inspect(db.engine)
        
        # 1. Update Company Table
        try:
            print("Migrating Company table...")
            columns = [c['name'] for c in inspector.get_columns('company')]
            
            # Helper to safely add column
            def add_column_safe(col_name, col_type):
                if col_name not in columns:
                    print(f"Adding column {col_name}...")
                    try:
                        db.session.execute(text(f"ALTER TABLE company ADD COLUMN {col_name} {col_type}"))
                    except Exception as e:
                        print(f"Skipping {col_name} (Error: {e})")
                else:
                    print(f"Column {col_name} already exists.")

            add_column_safe('plan_id', 'VARCHAR(50)')
            add_column_safe('asaas_customer_id', 'VARCHAR(50)')
            add_column_safe('payment_status', "VARCHAR(20) DEFAULT 'trial'")
            add_column_safe('platform_inoperante', 'BOOLEAN DEFAULT 0') # SQLite uses 0/1
            add_column_safe('overdue_since', 'TIMESTAMP')
            
            print("Company table migration checked/completed.")
            
        except Exception as e:
            print(f"Error inspecting/migrating Company table: {e}")
            db.session.rollback()

        # 2. Create BillingEvent Table
        try:
            print("Creating BillingEvent table...")
            # For SQLite, SERIAL is not supported directly in CREATE TABLE usually, usually INTEGER PRIMARY KEY AUTOINCREMENT
            # But SQLAlchemy models usually handle this if we used db.create_all(), but here we use raw SQL.
            # Postgres uses SERIAL directly. SQLite uses INTEGER PRIMARY KEY for autoinc.
            
            # Check if table exists
            if not inspector.has_table('billing_event'):
                db.session.execute(text("""
                    CREATE TABLE billing_event (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        company_id INTEGER,
                        event_type VARCHAR(50) NOT NULL,
                        payload JSON,
                        processed_at TIMESTAMP,
                        idempotency_key VARCHAR(100) UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(company_id) REFERENCES company(id)
                    );
                """))
                print("BillingEvent table created.")
            else:
                print("BillingEvent table already exists.")
            
        except Exception as e:
            print(f"Error creating BillingEvent table: {e}")
            db.session.rollback()

        # Commit changes
        try:
            db.session.commit()
            print("All changes committed successfully!")
        except Exception as e:
            print(f"Error committing changes: {e}")
            db.session.rollback()

if __name__ == "__main__":
    run_migration()
