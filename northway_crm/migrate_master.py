import sqlite3
import os

# Path to database
db_path = os.path.join('instance', 'crm.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Attempting to add column is_super_admin...")
    cursor.execute("ALTER TABLE user ADD COLUMN is_super_admin BOOLEAN DEFAULT 0")
    conn.commit()
    print("Column added successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e):
        print("Column already exists. Skipping.")
    else:
        print(f"Error: {e}")
finally:
    conn.close()
