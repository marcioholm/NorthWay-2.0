from app import app, db
from sqlalchemy import text

def add_columns():
    with app.app_context():
        # 1. Add columns to LEADS table
        print("Checking 'lead' table...")
        with db.engine.connect() as conn:
            # Check/Add gmb_link
            try:
                conn.execute(text("ALTER TABLE lead ADD COLUMN gmb_link VARCHAR(500)"))
                print("Added gmb_link to lead")
            except Exception as e:
                print(f"Skipped gmb_link (probably exists): {e}")

            # Check/Add gmb_rating
            try:
                conn.execute(text("ALTER TABLE lead ADD COLUMN gmb_rating FLOAT DEFAULT 0.0"))
                print("Added gmb_rating to lead")
            except Exception:
                pass

            # Check/Add gmb_reviews
            try:
                conn.execute(text("ALTER TABLE lead ADD COLUMN gmb_reviews INTEGER DEFAULT 0"))
                print("Added gmb_reviews to lead")
            except Exception:
                pass
                
            # Check/Add gmb_photos
            try:
                conn.execute(text("ALTER TABLE lead ADD COLUMN gmb_photos INTEGER DEFAULT 0"))
                print("Added gmb_photos to lead")
            except Exception:
                pass

            # Check/Add gmb_last_sync
            try:
                conn.execute(text("ALTER TABLE lead ADD COLUMN gmb_last_sync DATETIME"))
                print("Added gmb_last_sync to lead")
            except Exception:
                pass

        # 2. Add columns to CLIENTS table
        print("\nChecking 'client' table...")
        with db.engine.connect() as conn:
            # Check/Add gmb_link
            try:
                conn.execute(text("ALTER TABLE client ADD COLUMN gmb_link VARCHAR(500)"))
                print("Added gmb_link to client")
            except Exception:
                pass

            # Check/Add gmb_rating
            try:
                conn.execute(text("ALTER TABLE client ADD COLUMN gmb_rating FLOAT DEFAULT 0.0"))
                print("Added gmb_rating to client")
            except Exception:
                pass

            # Check/Add gmb_reviews
            try:
                conn.execute(text("ALTER TABLE client ADD COLUMN gmb_reviews INTEGER DEFAULT 0"))
                print("Added gmb_reviews to client")
            except Exception:
                pass
                
            # Check/Add gmb_photos
            try:
                conn.execute(text("ALTER TABLE client ADD COLUMN gmb_photos INTEGER DEFAULT 0"))
                print("Added gmb_photos to client")
            except Exception:
                pass

            # Check/Add gmb_last_sync
            try:
                conn.execute(text("ALTER TABLE client ADD COLUMN gmb_last_sync DATETIME"))
                print("Added gmb_last_sync to client")
            except Exception:
                pass
        
        print("\nDone! Database updated.")

if __name__ == "__main__":
    add_columns()
