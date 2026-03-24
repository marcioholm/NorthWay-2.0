import os
import sys
from sqlalchemy import create_engine, text

def apply_fix():
    # 1. Get DATABASE_URL from .env.production or environment
    db_url = os.getenv('DATABASE_URL')
    
    # If not in env, try to load from .env.production
    if not db_url:
        try:
            from dotenv import load_dotenv
            # Check current dir and parent dir
            env_path = 'northway_crm/.env.production'
            if not os.path.exists(env_path):
                env_path = '.env.production'
            
            if os.path.exists(env_path):
                print(f"Loading env from {env_path}")
                load_dotenv(env_path)
                db_url = os.getenv('DATABASE_URL')
        except ImportError:
            pass

    if not db_url:
        print("❌ ERROR: DATABASE_URL not found.")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # 2. Read the SQL file
    sql_path = 'migrations/fix_supabase_rls.sql'
    if not os.path.exists(sql_path):
        # try relative to project root
        sql_path = 'NorthWay-2.0/migrations/fix_supabase_rls.sql'
        if not os.path.exists(sql_path):
            print(f"❌ ERROR: SQL file not found at {sql_path}")
            sys.exit(1)

    with open(sql_path, 'r') as f:
        sql_content = f.read()

    print(f"🔌 Connecting to database...")
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            print("🚀 Executing RLS migration...")
            # We split by semicolon to run multiple statements if needed, 
            # though sqlalchemy.text can often handle blocks.
            # However, for RLS and policies, it's safer to run the whole block or statement by statement.
            
            # Execute the entire script as one block
            conn.execute(text(sql_content))
            conn.commit()
            print("✅ Migration applied successfully!")

    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_fix()
