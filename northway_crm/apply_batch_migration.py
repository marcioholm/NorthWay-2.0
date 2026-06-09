import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text


def apply_batch_migration(app):
    with app.app_context():
        print("🚀 Applying Batch Migration...")

        is_sqlite = 'sqlite' in str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))

        if is_sqlite:
            print("ℹ️  SQLite detected - using ALTER TABLE / CREATE TABLE")
            conn = db.engine.connect()

            try:
                # 1. Create prospecting_batches table
                batch_table_sql = """
                CREATE TABLE IF NOT EXISTS prospecting_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    status VARCHAR(20) DEFAULT 'pending',
                    total_count INTEGER DEFAULT 0,
                    processed_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_by INTEGER REFERENCES "user"(id) ON DELETE SET NULL
                );
                """
                conn.execute(text(batch_table_sql))
                print("✅ Created/verified table: prospecting_batches")

                # 2. Add batch_id column to prospecting_messages if not exists
                existing_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(prospecting_messages)")).fetchall()]
                if "batch_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE prospecting_messages ADD COLUMN batch_id INTEGER REFERENCES prospecting_batches(id) ON DELETE SET NULL"))
                    print("✅ Added column: batch_id to prospecting_messages")
                else:
                    print("ℹ️  Column batch_id already exists in prospecting_messages")
                
                conn.commit()

            except Exception as e:
                print(f"⚠️  SQLite error: {e}")
            finally:
                conn.close()

        else:
            print("ℹ️  PostgreSQL detected - using raw queries")
            queries = [
                """
                CREATE TABLE IF NOT EXISTS prospecting_batches (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    status VARCHAR(20) DEFAULT 'pending',
                    total_count INTEGER DEFAULT 0,
                    processed_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_by INTEGER REFERENCES "user"(id) ON DELETE SET NULL
                );
                """,
                """
                ALTER TABLE prospecting_messages ADD COLUMN IF NOT EXISTS batch_id INTEGER REFERENCES prospecting_batches(id) ON DELETE SET NULL;
                """
            ]

            conn = db.engine.connect()
            try:
                for q in queries:
                    try:
                        conn.execute(text(q))
                        print(f"✅ Executed PG migration: {q[:80]}...")
                    except Exception as e:
                        print(f"⚠️  PG Query Error: {e}")
                conn.commit()
            finally:
                conn.close()

        print("✅ Batch migration complete!")


if __name__ == "__main__":
    app = create_app()
    apply_batch_migration(app)
