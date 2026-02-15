import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from app import create_app
    from models import db
    from sqlalchemy import text, inspect
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

app = create_app()
with app.app_context():
    # 1. Add missing columns to drive_folder_template
    inspector = inspect(db.engine)
    if inspector.has_table("drive_folder_template"):
        cols = [c['name'] for c in inspector.get_columns("drive_folder_template")]
        with db.engine.connect() as conn:
            modified = False
            if 'enabled' not in cols:
                print("Adding 'enabled' to drive_folder_template...")
                conn.execute(text("ALTER TABLE drive_folder_template ADD COLUMN enabled BOOLEAN DEFAULT TRUE;"))
                modified = True
            if 'scope' not in cols:
                print("Adding 'scope' to drive_folder_template...")
                conn.execute(text("ALTER TABLE drive_folder_template ADD COLUMN scope VARCHAR(20) DEFAULT 'tenant';"))
                modified = True
            
            if modified:
                conn.commit()
                print("drive_folder_template columns added.")
            else:
                print("drive_folder_template already has required columns.")
    
    # 2. Create new tables
    print("Creating all tables (including new ones if missing)...")
    db.create_all()
    print("Database sync complete.")
