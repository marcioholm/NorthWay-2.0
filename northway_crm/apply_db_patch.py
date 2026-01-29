
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
try:
    load_dotenv()
except:
    pass

# Get DB URL
db_url = os.getenv('DATABASE_URL')
if not db_url:
    # Try manual read
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.strip().split('=', 1)[1].strip('"').strip("'")
                    break
    except:
        pass

if not db_url:
    # Try parent dir
    try:
        with open('../.env', 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.strip().split('=', 1)[1].strip('"').strip("'")
                    break
    except:
        pass

if not db_url:
    print("❌ Error: DATABASE_URL not found in .env or via os.getenv")
    # Hardcode check? No.
    exit(1)

# Ensure it's a valid sqlalchemy url (fix postgres:// if needed)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

print(f"🔌 Connecting to Database...")

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("🚀 Running Migrations...")
        
        # 1. User.last_login
        print("   - Adding user.last_login...")
        try:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;'))
            print("     ✅ Success")
        except Exception as e:
            print(f"     ⚠️  Note: {e}")

        # 2. Company.last_active_at
        print("   - Adding company.last_active_at...")
        try:
            conn.execute(text('ALTER TABLE company ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP;'))
            print("     ✅ Success")
        except Exception as e:
            print(f"     ⚠️  Note: {e}")
            
        conn.commit()
        print("\n✅ Migration Completed Successfully!")
        
except Exception as e:
    print(f"\n❌ Critical Error: {str(e)}")
