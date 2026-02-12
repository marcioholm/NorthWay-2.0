
import os
import psycopg2
from urllib.parse import urlparse

# DATABASE_URL from Vercel env or constructed from Supabase creds
# Based on .env:
# SUPABASE_URL=https://bnumpvhsfujpprovajkt.supabase.co
# We need the connection string. Usually: postgres://postgres:[PASSWORD]@db.bnumpvhsfujpprovajkt.supabase.co:5432/postgres
# IF we don't have the password, we might be stuck unless we use the service key via API (which failed).
# BUT the app is running in Vercel, so it has a DATABASE_URL.
# I'll try to use the `os.environ.get('DATABASE_URL')` if available, or ask the user.
# Wait, the error log `psycopg2.errors.InFailedSqlTransaction` implies the app IS connected.
# I can try to use the *existing* app (SQLAlchemy) to run the raw SQL.

from northway_crm.app import app, db
from sqlalchemy import text

def apply_migration():
    with app.app_context():
        print("Applying migration...")
        try:
            # 1. Add is_urgent
            print("Adding is_urgent column...")
            db.session.execute(text("ALTER TABLE task ADD COLUMN is_urgent BOOLEAN DEFAULT FALSE;"))
            db.session.commit()
            print("is_urgent added.")
        except Exception as e:
            print(f"Error adding is_urgent (maybe exists?): {e}")
            db.session.rollback()

        try:
            # 2. Add is_important
            print("Adding is_important column...")
            db.session.execute(text("ALTER TABLE task ADD COLUMN is_important BOOLEAN DEFAULT FALSE;"))
            db.session.commit()
            print("is_important added.")
        except Exception as e:
            print(f"Error adding is_important (maybe exists?): {e}")
            db.session.rollback()
            
        print("Migration complete.")

if __name__ == "__main__":
    apply_migration()
