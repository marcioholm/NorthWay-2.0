import sqlite3
import os

DATABASE_PATH = 'instance/crm.db'

def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"Connecting to database at {DATABASE_PATH}")
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification'")
    if cursor.fetchone():
        print("Table 'notification' already exists.")
    else:
        print("Creating table 'notification'...")
        cursor.execute('''
            CREATE TABLE notification (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                type VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                message VARCHAR(500),
                read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES user(id),
                FOREIGN KEY(company_id) REFERENCES company(id)
            )
        ''')
        print("Table 'notification' created.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    if os.path.exists(DATABASE_PATH):
        migrate()
    else:
        print(f"Database not found at {DATABASE_PATH}")
