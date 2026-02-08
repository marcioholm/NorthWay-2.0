
import sqlite3
import os

DB_PATH = '/Users/Marci.Holm/Applications/NorthWay-2.0/northway_crm/instance/crm.db'

def add_column(cursor, table, column, type_def):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
        print(f"Added {column} to {table}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"Column {column} already exists in {table}")
        else:
            print(f"Error adding {column} to {table}: {e}")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Columns to add
    columns = [
        ('diagnostic_status', 'VARCHAR(20) DEFAULT "pending"'),
        ('diagnostic_score', 'FLOAT'),
        ('diagnostic_stars', 'FLOAT'),
        ('diagnostic_classification', 'VARCHAR(50)'),
        ('diagnostic_date', 'DATETIME'),
        ('diagnostic_pillars', 'JSON')
    ]

    for col, type_def in columns:
        add_column(cursor, 'lead', col, type_def)
        add_column(cursor, 'client', col, type_def)

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
