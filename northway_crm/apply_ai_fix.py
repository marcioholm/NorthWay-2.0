import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text


def apply_ai_fix(app):
    with app.app_context():
        print("🚀 Applying AI Module Final Fix...")

        conn = db.engine.connect()
        try:
            # 1. Fix tenant_ai_credentials
            # Check for default_model vs model
            cols = [row[0] for row in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'tenant_ai_credentials'")).fetchall()]
            
            if 'default_model' in cols and 'model' not in cols:
                print("🔄 Renaming default_model to model in tenant_ai_credentials")
                conn.execute(text("ALTER TABLE tenant_ai_credentials RENAME COLUMN default_model TO model"))
            
            if 'base_url' not in cols:
                print("➕ Adding base_url to tenant_ai_credentials")
                conn.execute(text("ALTER TABLE tenant_ai_credentials ADD COLUMN base_url TEXT"))

            # 2. Fix prospecting_integrations (ensure it has all columns)
            print("📦 Ensuring prospecting_integrations table exists and is correct")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prospecting_integrations (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    provider VARCHAR(50) NOT NULL,
                    api_base_url TEXT,
                    instance_name VARCHAR(100),
                    api_key_encrypted TEXT,
                    api_key_last4 VARCHAR(4),
                    status VARCHAR(20) DEFAULT 'inactive',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, provider)
                )
            """))
            
            conn.commit()
            print("✅ AI Module Fix complete!")
        except Exception as e:
            print(f"❌ Error during fix: {e}")
        finally:
            conn.close()


if __name__ == "__main__":
    app = create_app()
    apply_ai_fix(app)
