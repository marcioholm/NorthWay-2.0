
import os
import sys
from sqlalchemy import create_engine, text

# Get DB URL from environment or args
db_url = os.getenv('DATABASE_URL')
if len(sys.argv) > 1:
    db_url = sys.argv[1]

if not db_url:
    print("❌ DATABASE_URL not found.")
    sys.exit(1)

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

print(f"🔌 Connecting to {db_url.split('@')[-1]}...")

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("🚀 Force Adding 'enabled' column...")
        
        # 1. Drive Folder Template - Enabled
        try:
            conn.execute(text("ALTER TABLE drive_folder_template ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE;"))
            print("   ✅ drive_folder_template.enabled added (IF NOT EXISTS).")
        except Exception as e:
            print(f"   ⚠️ Error adding enabled: {e}")
            # Fallback
            try:
                 conn.execute(text("ALTER TABLE drive_folder_template ADD COLUMN enabled BOOLEAN DEFAULT TRUE;"))
                 print("   ✅ drive_folder_template.enabled added (Fallback).")
            except Exception as e2:
                 print(f"   ❌ Final Error: {e2}")

        conn.commit()
        print("\n✅ Done.")

except Exception as e:
    print(f"\n❌ Critical Error: {str(e)}")
    sys.exit(1)
