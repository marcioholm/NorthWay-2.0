import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text


def apply_tenant_credentials_migration(app):
    with app.app_context():
        print("🚀 Applying Tenant Credentials Migration...")

        is_sqlite = 'sqlite' in str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))

        if is_sqlite:
            print("ℹ️  SQLite detected - using ALTER TABLE")
            conn = db.engine.connect()

            tables = [
                """
                CREATE TABLE IF NOT EXISTS tenant_ai_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    provider VARCHAR(50) NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    api_key_last4 VARCHAR(4),
                    default_model VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'active',
                    last_test_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, provider)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS tenant_integrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                );
                """
            ]

            try:
                for table_sql in tables:
                    table_name = table_sql.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
                    try:
                        conn.execute(text(table_sql))
                        print(f"✅ Created table: {table_name}")
                    except Exception as e:
                        print(f"⚠️  Table {table_name}: {e}")
            finally:
                conn.close()

        else:
            print("ℹ️  PostgreSQL detected")
            queries = [
                """
                CREATE TABLE IF NOT EXISTS tenant_ai_credentials (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    provider VARCHAR(50) NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    api_key_last4 VARCHAR(4),
                    default_model VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'active',
                    last_test_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, provider)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS tenant_integrations (
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
                );
                """
            ]

            conn = db.engine.connect()
            try:
                for q in queries:
                    try:
                        conn.execute(text(q))
                        print(f"✅ Executed: {q[:80]}...")
                    except Exception as e:
                        print(f"⚠️  Query: {e}")
                conn.commit()
            finally:
                conn.close()

        print("✅ Tenant credentials migration complete!")


if __name__ == "__main__":
    app = create_app()
    apply_tenant_credentials_migration(app)