import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text

def apply_smtp_migration(app):
    with app.app_context():
        print("🚀 Applying SMTP Professional Migration...")

        is_sqlite = 'sqlite' in str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))

        conn = db.engine.connect()
        try:
            # 1. Create table if not exists (agnostic)
            id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
            ts_type = "DATETIME DEFAULT CURRENT_TIMESTAMP" if is_sqlite else "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            
            print("📦 Ensuring prospecting_integrations table exists")
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS prospecting_integrations (
                    id {id_type},
                    company_id INTEGER NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    api_base_url TEXT,
                    instance_name VARCHAR(100),
                    api_key_encrypted TEXT,
                    api_key_last4 VARCHAR(4),
                    status VARCHAR(20) DEFAULT 'inactive',
                    created_at {ts_type},
                    updated_at {ts_type},
                    UNIQUE(company_id, provider)
                )
            """))
            
            # 2. Add columns
            new_fields = [
                ("smtp_host", "TEXT"),
                ("smtp_port", "INTEGER"),
                ("smtp_user", "TEXT"),
                ("sender_name", "TEXT"),
                ("sender_email", "TEXT"),
                ("ssl_tls", "BOOLEAN DEFAULT TRUE")
            ]

            if is_sqlite:
                print("ℹ️  SQLite detected")
                existing_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(prospecting_integrations)")).fetchall()]
                for col_name, col_type in new_fields:
                    if col_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE prospecting_integrations ADD COLUMN {col_name} {col_type}"))
                            print(f"✅ Added column: {col_name}")
                        except Exception as e:
                            print(f"⚠️  Column {col_name}: {e}")
            else:
                print("ℹ️  PostgreSQL detected")
                for col_name, col_type in new_fields:
                    try:
                        conn.execute(text(f"ALTER TABLE prospecting_integrations ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        print(f"✅ Executed: ALTER TABLE prospecting_integrations ADD COLUMN IF NOT EXISTS {col_name}...")
                    except Exception as e:
                        print(f"⚠️  Column {col_name}: {e}")
                conn.commit()
        finally:
            conn.close()

        print("✅ SMTP migration complete!")

if __name__ == "__main__":
    app = create_app()
    apply_smtp_migration(app)
