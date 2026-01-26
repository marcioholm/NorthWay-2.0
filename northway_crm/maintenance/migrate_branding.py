import sqlite3

def migrate():
    conn = sqlite3.connect('instance/crm.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE company ADD COLUMN logo_filename VARCHAR(150)")
        print("Added logo_filename column")
    except sqlite3.OperationalError:
        print("logo_filename column already exists")

    try:
        cursor.execute("ALTER TABLE company ADD COLUMN primary_color VARCHAR(7) DEFAULT '#fa0102'")
        print("Added primary_color column")
    except sqlite3.OperationalError:
        print("primary_color column already exists")
        
    try:
        cursor.execute("ALTER TABLE company ADD COLUMN secondary_color VARCHAR(7) DEFAULT '#111827'")
        print("Added secondary_color column")
    except sqlite3.OperationalError:
        print("secondary_color column already exists")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
