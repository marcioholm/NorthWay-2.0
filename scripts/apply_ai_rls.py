import os
import sys
from sqlalchemy import create_engine, text

def apply_fix():
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        try:
            from dotenv import load_dotenv
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

    sql_path = 'migrations/ai_rls_policies.sql'
    if not os.path.exists(sql_path):
        print(f"❌ ERROR: SQL file not found at {sql_path}")
        sys.exit(1)

    with open(sql_path, 'r') as f:
        sql_content = f.read()

    print(f"🔌 Connecting to database...")
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            print("🚀 Executing AI RLS migration...")
            conn.execute(text(sql_content))
            conn.commit()
            print("✅ AI RLS Migration applied successfully!")

    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_fix()
