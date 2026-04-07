from northway_crm.app import create_app
from northway_crm.models import db
from sqlalchemy import inspect
import sys

app = create_app()
with app.app_context():
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Existing tables: {tables}")
        
        target_tables = ['whatsapp_instances', 'whatsapp_conversations', 'whatsapp_messages']
        for table in target_tables:
            if table in tables:
                columns = [c['name'] for c in inspector.get_columns(table)]
                print(f"Columns in {table}: {columns}")
            else:
                print(f"Table {table} NOT FOUND!")
    except Exception as e:
        print(f"Error inspecting DB: {e}")
        sys.exit(1)
