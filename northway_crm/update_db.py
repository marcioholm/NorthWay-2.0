from app import create_app, db
from sqlalchemy import text

def run_migration():
    print("Starting migration...")
    app = create_app()
    with app.app_context():
        try:
            # 1. Create tables (Payment, etc)
            db.create_all()
            print("Tables created/verified.")
            
            with db.engine.connect() as conn:
                # 2. Add column amount_paid to Transaction
                try:
                    conn.execute(text("ALTER TABLE transaction ADD COLUMN amount_paid FLOAT DEFAULT 0.0"))
                    print("Column amount_paid added to transaction.")
                    conn.execute(text("UPDATE transaction SET amount_paid = 0.0 WHERE amount_paid IS NULL"))
                    conn.commit()
                except Exception as e:
                    print(f"Column amount_paid skip: {e}")

                # 3. Add Termination Columns to Contract
                columns = [
                    ("termination_reason", "VARCHAR(500)"),
                    ("termination_date", "DATE"),
                    ("penalty_amount", "FLOAT DEFAULT 0.0")
                ]
                
                for col_name, col_type in columns:
                    try:
                        conn.execute(text(f"ALTER TABLE contract ADD COLUMN {col_name} {col_type}"))
                        print(f"Column {col_name} added to contract.")
                        conn.commit()
                    except Exception as e:
                        print(f"Column {col_name} skip: {e}")
                
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    run_migration()
