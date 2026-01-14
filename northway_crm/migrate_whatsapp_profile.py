from app import create_app
from models import db
import sqlite3

def run_migration():
    app = create_app()
    
    with app.app_context():
        # Using raw SQL for SQLite ALTER TABLE ADD COLUMN simplicity 
        # (Assuming SQLite as per context)
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        
        print(f"Migrating database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Lead
        try:
            cursor.execute("ALTER TABLE lead ADD COLUMN profile_pic_url VARCHAR(500)")
            print("Added profile_pic_url to Lead table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Column profile_pic_url already exists in Lead.")
            else:
                print(f"Error migrating Lead: {e}")
                
        # 2. Client
        try:
            cursor.execute("ALTER TABLE client ADD COLUMN profile_pic_url VARCHAR(500)")
            print("Added profile_pic_url to Client table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Column profile_pic_url already exists in Client.")
            else:
                print(f"Error migrating Client: {e}")
                
        conn.commit()
        conn.close()
        print("Migration complete.")

if __name__ == '__main__':
    run_migration()
