import sqlite3

def migrate():
    conn = sqlite3.connect('instance/crm.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE task ADD COLUMN description TEXT")
        print("Added description column to task table")
    except sqlite3.OperationalError:
        print("description column already exists")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
