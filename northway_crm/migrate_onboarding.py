import sqlite3
import os

DATABASE_PATH = 'instance/crm.db'

def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"Connecting to database at {DATABASE_PATH}")
    
    # Check existing columns in user table
    cursor.execute("PRAGMA table_info(user)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns: {columns}")
    
    # Add onboarding_dismissed
    if 'onboarding_dismissed' not in columns:
        print("Adding 'onboarding_dismissed' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN onboarding_dismissed BOOLEAN DEFAULT 0")
    else:
        print("'onboarding_dismissed' column already exists.")
        
    # Add phone (if missing)
    if 'phone' not in columns:
        print("Adding 'phone' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN phone VARCHAR(20)")
    else:
        print("'phone' column already exists.")

    # Add profile_image (if missing)
    if 'profile_image' not in columns:
        print("Adding 'profile_image' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN profile_image VARCHAR(150)")
    else:
        print("'profile_image' column already exists.")
        
    # Add status_message (if missing, might as well)
    if 'status_message' not in columns:
        print("Adding 'status_message' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN status_message VARCHAR(100)")
    else:
        print("'status_message' column already exists.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    if os.path.exists(DATABASE_PATH):
        migrate()
    else:
        print(f"Database not found at {DATABASE_PATH}")
