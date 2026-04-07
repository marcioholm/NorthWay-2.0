from app import app
from models import db
from sqlalchemy import text

with app.app_context():
    db.create_all()
    print("New tables created.")
    
    # Try to migrate data from old table
    try:
        # Check if old table exists
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='whats_app_message';")).fetchall()
        if result:
            print("Found old whats_app_message table.")
        else:
            print("Old whats_app_message table not found.")
    except Exception as e:
        print("Error checking old table:", e)
