from models import db
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
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Check columns
                cursor.execute("PRAGMA table_info(email_log)")
                columns = [info[1] for info in cursor.fetchall()]
                
                if 'template' not in columns:
                    print("🔄 Adding template column to email_log...")
                    cursor.execute("ALTER TABLE email_log ADD COLUMN template TEXT")
                    print("✅ Column added.")
                else:
                    print("ℹ️ Column template already exists.")
                    
        except Exception as e:
            print(f"❌ Error altering table: {e}")

if __name__ == "__main__":
    migrate()
