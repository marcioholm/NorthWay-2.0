from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        # 1. Create Payment table
        try:
            # Check if table exists (SQLite specific check or just try create)
            # Simplest in SQLAlchemy is db.create_all() which only creates missing tables
            db.create_all()
            print("Created missing tables (Payment, etc).")
        except Exception as e:
            print(f"Error creating tables: {e}")

        # 2. Add column amount_paid to Transaction if missing
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE transaction ADD COLUMN amount_paid FLOAT DEFAULT 0.0"))
                conn.execute(text("UPDATE transaction SET amount_paid = 0.0 WHERE amount_paid IS NULL"))
                conn.commit()
                print("Added amount_paid to transaction.")
        except Exception as e:
            # Column likely exists
            print(f"Column amount_paid might already exist: {e}")

if __name__ == '__main__':
    migrate()
