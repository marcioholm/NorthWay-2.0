
import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get DB URL
db_url = os.getenv('DATABASE_URL')
if not db_url:
    # Try manual read from .env
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.strip().split('=', 1)[1].strip('"').strip("'")
                    break
    except:
        pass

if not db_url:
    print("⚠️  Warning: DATABASE_URL not found. Trying local SQLite...")
    if os.path.exists('crm.db'):
        db_url = 'sqlite:///crm.db'
    elif os.path.exists('instance/crm.db'):
        db_url = 'sqlite:///instance/crm.db'
    else:
        print("❌ Error: crm.db not found.")
        exit(1)

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

print(f"🔌 Connecting to Database...")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("🚀 Applying Global Template Schema Changes...")
    
    
    def add_column_safe(connection, table, column, col_type):
        try:
            # Try adding column efficiently
            connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type};'))
            print(f"     ✅ Added {column} to {table}")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "no such table" in str(e).lower():
                 print(f"     Matched expected error: {e}") 
            else:
                 # Check if column exists via PRAGMA if generic error
                 try:
                     result = connection.execute(text(f"PRAGMA table_info({table})"))
                     columns = [row[1] for row in result]
                     if column in columns:
                         print(f"     ℹ️  Column {column} already exists in {table}")
                         return
                 except:
                     pass
                 print(f"     ⚠️  Could not add {column}: {e}")

    # 1. Add 'enabled' to drive_folder_template
    print("   - Adding enabled column to drive_folder_template...")
    add_column_safe(conn, 'drive_folder_template', 'enabled', 'BOOLEAN DEFAULT 1')

    # 2. Add 'scope' to drive_folder_template
    print("   - Adding scope column to drive_folder_template...")
    add_column_safe(conn, 'drive_folder_template', 'scope', "VARCHAR(20) DEFAULT 'tenant'")
        
    # 4. Add 'allowed_global_template_ids' to company
    print("   - Adding allowed_global_template_ids to company...")
    # SQLite uses TEXT for JSON usually
    col_type = 'TEXT' if 'sqlite' in str(engine.url) else 'JSON'
    add_column_safe(conn, 'company', 'allowed_global_template_ids', col_type)
            
    conn.commit()
    print("\n✅ Schema Updated!")
