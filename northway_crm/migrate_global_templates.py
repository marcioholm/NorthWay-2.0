from app import create_app, db
app = create_app()
from models import ContractTemplate
import sqlite3

# Context
with app.app_context():
    print("Promoting existing templates to GLOBAL...")
    
    # 1. Add Column via raw SQL (SQLite limitation dealing with migrations)
    db_path = "instance/crm.db" 
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE contract_template ADD COLUMN is_global BOOLEAN DEFAULT 0")
        conn.commit()
        print("Column 'is_global' added successfully.")
    except sqlite3.OperationalError as e:
        print(f"Column might already exist: {e}")
        
    conn.close()

    # 2. Promote Existing Templates
    # The user said "the ones currently on the main login".
    # We will assume ALL currently existing templates should be global, 
    # as the user implies they are the "Model" for everyone.
    
    templates = ContractTemplate.query.all()
    count = 0
    for t in templates:
        t.is_global = True
        count += 1
        
    db.session.commit()
    print(f"Promoted {count} templates to GLOBAL.")
