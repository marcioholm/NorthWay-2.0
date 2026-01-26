import sqlite3
import os

db_path = os.path.join('instance', 'crm.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Promote first user to super admin for testing
# In production this would be specific
print("Promoting User ID 1 to Super Admin...")
cursor.execute("UPDATE user SET is_super_admin = 1 WHERE id = 1")
conn.commit()

# Verify
cursor.execute("SELECT id, name, is_super_admin FROM user WHERE id = 1")
row = cursor.fetchone()
print(f"User: {row}")

conn.close()
