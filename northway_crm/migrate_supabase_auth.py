from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Checking for supabase_uid column...")
    try:
        # Check if column exists
        inspector = db.inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('user')]
        
        if 'supabase_uid' not in columns:
            print("Adding supabase_uid column...")
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE user ADD COLUMN supabase_uid VARCHAR(100)'))
                # SQLite doesn't strictly enforce UNIQUE in ALTER TABLE lightly without recreating, 
                # but we can try creating a unique index if needed or just leave it as logic constraint for now.
                # Let's try creating an index for uniqueness.
                conn.execute(text('CREATE UNIQUE INDEX idx_user_supabase_uid ON user (supabase_uid)'))
                conn.commit()
            print("Column added successfully.")
        else:
            print("Column supabase_uid already exists.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
