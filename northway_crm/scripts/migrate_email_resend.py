from models import db, PasswordResetToken, EmailLog
from flask import Flask
import os
import sqlite3

# Initialize minimal app context
app = Flask(__name__)
# Assuming standard SQLite path or env
db_path = os.path.join(os.getcwd(), 'instance', 'northway_crm.sqlite')
if not os.path.exists(db_path):
    # Try finding it in northway_crm/instance if current wd is parent
    db_path = os.path.join(os.getcwd(), 'northway_crm', 'instance', 'northway_crm.sqlite')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def migrate():
    with app.app_context():
        print(f"Migrating Database at: {db_path}")
        
        # 1. Create PasswordResetToken table
        try:
            # Check if table exists manually to be safe or just let create_all handle it
            # create_all only creates MISSING tables
            db.create_all() 
            print("✅ PasswordResetToken table created (if didn't exist).")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")

        # 2. Add column provider_message_id to EmailLog if missing
        # SQLAlchemy doesn't auto-add columns in `create_all`, need SQL
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Check columns
                cursor.execute("PRAGMA table_info(email_log)")
                columns = [info[1] for info in cursor.fetchall()]
                
                if 'provider_message_id' not in columns:
                    print("🔄 Adding provider_message_id column to email_log...")
                    cursor.execute("ALTER TABLE email_log ADD COLUMN provider_message_id TEXT")
                    print("✅ Column added.")
                else:
                    print("ℹ️ Column provider_message_id already exists.")
                    
        except Exception as e:
            print(f"❌ Error altering table: {e}")

if __name__ == "__main__":
    migrate()
