import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text

def apply_channel_migration(app):
    with app.app_context():
        print("🚀 Applying CRM Channel Integrations Migration...")

        is_sqlite = 'sqlite' in str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))

        conn = db.engine.connect()
        try:
            id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
            ts_type = "DATETIME DEFAULT CURRENT_TIMESTAMP" if is_sqlite else "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            
            # 1. Add columns to Lead table
            print("📦 Ensuring whatsapp and mobile_phone columns exist in Lead table")
            new_lead_fields = [
                ("whatsapp", "VARCHAR(50)"),
                ("mobile_phone", "VARCHAR(50)")
            ]
            
            if is_sqlite:
                print("ℹ️  SQLite detected for Lead update")
                existing_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(lead)")).fetchall()]
                for col_name, col_type in new_lead_fields:
                    if col_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE lead ADD COLUMN {col_name} {col_type}"))
                            print(f"✅ Added column to lead: {col_name}")
                        except Exception as e:
                            print(f"⚠️  Column {col_name} on lead: {e}")
            else:
                print("ℹ️  PostgreSQL detected for Lead update")
                for col_name, col_type in new_lead_fields:
                    try:
                        conn.execute(text(f"ALTER TABLE lead ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        print(f"✅ Executed: ALTER TABLE lead ADD COLUMN IF NOT EXISTS {col_name}...")
                    except Exception as e:
                        print(f"⚠️  Column {col_name} on lead: {e}")
                conn.commit()

            # 2. Create crm_channel_integrations table
            print("📦 Ensuring crm_channel_integrations table exists")
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS crm_channel_integrations (
                    id {id_type},
                    tenant_id INTEGER NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    instance_name VARCHAR(100) NOT NULL,
                    api_url VARCHAR(255),
                    api_key VARCHAR(255),
                    active BOOLEAN DEFAULT TRUE,
                    created_at {ts_type},
                    updated_at {ts_type},
                    FOREIGN KEY (tenant_id) REFERENCES company(id) ON DELETE CASCADE,
                    UNIQUE(provider, instance_name)
                )
            """))
            print("✅ crm_channel_integrations table ensured")

            # Try to create index if it's Postgres
            if not is_sqlite:
                try:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_provider_instance ON crm_channel_integrations (provider, instance_name);"))
                    conn.commit()
                except Exception as e:
                    print(f"⚠️  Index creation: {e}")
                    
        finally:
            conn.close()

        print("✅ CRM Channel Integrations migration complete!")

if __name__ == "__main__":
    app = create_app()
    apply_channel_migration(app)
