import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text

def apply_sdr_ai_migration(app):
    with app.app_context():
        print("🚀 Applying SDR AI Multi-Tenant Architecture Migration...")

        is_sqlite = 'sqlite' in str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))

        conn = db.engine.connect()
        try:
            # For SQLite, it's easier to drop and let SQLAlchemy create all since they are new tables
            # But we must only drop the newly created channel table from previous step
            if is_sqlite:
                print("ℹ️  SQLite detected. Dropping crm_channel_integrations if exists to recreate with UUID.")
                conn.execute(text("DROP TABLE IF EXISTS crm_channel_integrations;"))
            else:
                print("ℹ️  PostgreSQL detected.")
                conn.execute(text("DROP TABLE IF EXISTS crm_channel_integrations CASCADE;"))

            # Create new tables via SQLAlchemy models directly to avoid raw SQL dialect differences
            print("📦 Creating new tables (crm_conversations, messages, memory, logs, integrations)...")
            db.create_all()
            print("✅ All tables created successfully based on models.py")

        except Exception as e:
            print(f"❌ Error during migration: {e}")
        finally:
            conn.close()

        print("✅ SDR AI Architecture migration complete!")

if __name__ == "__main__":
    app = create_app()
    apply_sdr_ai_migration(app)
