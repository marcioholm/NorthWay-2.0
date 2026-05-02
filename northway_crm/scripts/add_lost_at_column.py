import os
import sys

# Add parent directory to path to import northway_crm
sys.path.append('/Users/Marci.Holm/Applications/NorthWay-2.0')

from northway_crm.app import create_app
from northway_crm.models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Check if lost_at exists
        db.session.execute(text("SELECT lost_at FROM lead LIMIT 1"))
        print("Column lost_at already exists.")
    except Exception:
        print("Adding lost_at column to lead table...")
        try:
            db.session.execute(text("ALTER TABLE lead ADD COLUMN lost_at DATETIME"))
            db.session.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")
            db.session.rollback()
