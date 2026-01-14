import sqlite3

def migrate():
    conn = sqlite3.connect('instance/crm.db')
    cursor = conn.cursor()
    
    columns = [
        ('bant_budget', 'VARCHAR(100)'),
        ('bant_authority', 'VARCHAR(100)'),
        ('bant_need', 'TEXT'),
        ('bant_timeline', 'VARCHAR(100)')
    ]
    
    for col_name, col_type in columns:
        try:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE lead ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            print(f"Column {col_name} already exists or error: {e}")
            
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
