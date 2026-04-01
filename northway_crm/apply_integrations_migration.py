import sys
import os
# Add project root AND northway_crm to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text

def apply_migrations(app):
    with app.app_context():
        print(f"🚀 Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        print("🚀 Applying Integrations Migration...")
        
        # Check if we are using SQLite
        is_sqlite = 'sqlite' in str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))
        
        if not is_sqlite:
            queries = [
                # 1. API Keys Table
                """
                CREATE TABLE IF NOT EXISTS integration_api_keys (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    key_prefix VARCHAR(10) NOT NULL,
                    key_hash VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    scopes JSONB DEFAULT '[]'::jsonb,
                    last_used_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # 2. Webhooks Table
                """
                CREATE TABLE IF NOT EXISTS integration_webhooks (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    url TEXT NOT NULL,
                    events JSONB DEFAULT '[]'::jsonb,
                    status VARCHAR(20) DEFAULT 'active',
                    secret TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # 3. Logs Table
                """
                CREATE TABLE IF NOT EXISTS integration_logs (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    type VARCHAR(20) NOT NULL,
                    endpoint VARCHAR(255) NOT NULL,
                    method VARCHAR(10) NOT NULL,
                    status_code INTEGER,
                    request_payload JSONB,
                    response_payload JSONB,
                    error_message TEXT,
                    request_id VARCHAR(50),
                    execution_time_ms INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # Indexes for Multitenancy
                "CREATE INDEX IF NOT EXISTS idx_api_keys_company ON integration_api_keys(company_id);",
                "CREATE INDEX IF NOT EXISTS idx_webhooks_company ON integration_webhooks(company_id);",
                "CREATE INDEX IF NOT EXISTS idx_logs_company ON integration_logs(company_id);",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON integration_api_keys(key_hash);"
            ]
        else:
            queries = [
                # SQLite doesn't support JSONB or SERIAL quite the same way, but SQLAlchemy handles abstraction
                # For raw SQL, we use TEXT and AUTOINCREMENT
                """
                CREATE TABLE IF NOT EXISTS integration_api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    scopes TEXT DEFAULT '[]',
                    last_used_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS integration_webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    events TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'active',
                    secret TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS integration_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    status_code INTEGER,
                    request_payload TEXT,
                    response_payload TEXT,
                    error_message TEXT,
                    request_id TEXT,
                    execution_time_ms INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                "CREATE INDEX IF NOT EXISTS idx_api_keys_company ON integration_api_keys(company_id);",
                "CREATE INDEX IF NOT EXISTS idx_webhooks_company ON integration_webhooks(company_id);",
                "CREATE INDEX IF NOT EXISTS idx_logs_company ON integration_logs(company_id);",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON integration_api_keys(key_hash);"
            ]

        for query in queries:
            try:
                db.session.execute(text(query))
                db.session.commit()
                print(f"✅ Executed: {query[:50]}...")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error: {e}")
                
        print("🏁 Integrations Migration Finished.")

if __name__ == "__main__":
    import sys
    import os
    # Add project root to path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from northway_crm.app import create_app
    app = create_app()
    apply_migrations(app)
