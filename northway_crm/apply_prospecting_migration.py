import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db
from sqlalchemy import text


def apply_prospecting_migration(app):
    with app.app_context():
        print("🚀 Applying Prospection Migration...")

        is_sqlite = 'sqlite' in str(app.config.get('SQLALCHEMY_DATABASE_URI', ''))

        if is_sqlite:
            print("ℹ️  SQLite detected - using ALTER TABLE")
            conn = db.engine.connect()

            try:
                existing_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(lead)")).fetchall()]

                new_fields = [
                    ("prospecting_status", "VARCHAR(50)"),
                    ("preferred_channel", "VARCHAR(20)"),
                    ("wa_attempts", "INTEGER DEFAULT 0"),
                    ("email_attempts", "INTEGER DEFAULT 0"),
                    ("last_contact_at", "TIMESTAMP"),
                    ("next_action_at", "TIMESTAMP"),
                    ("last_angle", "VARCHAR(100)"),
                    ("in_execution", "BOOLEAN DEFAULT 0"),
                    ("prospecting_campaign_id", "INTEGER"),
                    ("lead_score", "INTEGER")
                ]

                for col_name, col_type in new_fields:
                    if col_name not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE lead ADD COLUMN {col_name} {col_type}"))
                            print(f"✅ Added column: {col_name}")
                        except Exception as e:
                            print(f"⚠️  Column {col_name}: {e}")

            finally:
                conn.close()

            tables = [
                """
                CREATE TABLE IF NOT EXISTS prospecting_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    target_segment VARCHAR(100),
                    objective TEXT,
                    tone_of_voice VARCHAR(100),
                    offer TEXT,
                    main_angle VARCHAR(100),
                    default_cta VARCHAR(255),
                    restrictions TEXT,
                    max_attempts INTEGER DEFAULT 3,
                    followup_interval_days INTEGER DEFAULT 3,
                    status VARCHAR(20) DEFAULT 'rascunho',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS prospecting_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    lead_id INTEGER NOT NULL REFERENCES lead(id) ON DELETE CASCADE,
                    campaign_id INTEGER REFERENCES prospecting_campaigns(id) ON DELETE SET NULL,
                    channel VARCHAR(20) NOT NULL,
                    type VARCHAR(20) DEFAULT 'outbound',
                    status VARCHAR(30) DEFAULT 'pendente',
                    content TEXT,
                    ai_model VARCHAR(50),
                    ai_prompt TEXT,
                    approved_by INTEGER REFERENCES user(id),
                    approved_at TIMESTAMP,
                    sent_at TIMESTAMP,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS prospecting_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE UNIQUE,
                    generate_message_webhook_url TEXT,
                    send_whatsapp_webhook_url TEXT,
                    send_email_webhook_url TEXT,
                    daily_send_limit INTEGER DEFAULT 50,
                    sending_start_time VARCHAR(5) DEFAULT '09:00',
                    sending_end_time VARCHAR(5) DEFAULT '18:00',
                    manual_approval_required BOOLEAN DEFAULT 1,
                    default_ai_model VARCHAR(50) DEFAULT 'gpt-4.1-mini',
                    default_tone VARCHAR(50) DEFAULT 'profissional',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            ]

            conn = db.engine.connect()
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
            print("ℹ️  PostgreSQL detected - using SQLAlchemy models")
            queries = [
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS prospecting_status VARCHAR(50);
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS preferred_channel VARCHAR(20);
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS wa_attempts INTEGER DEFAULT 0;
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS email_attempts INTEGER DEFAULT 0;
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS last_contact_at TIMESTAMP;
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS next_action_at TIMESTAMP;
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS last_angle VARCHAR(100);
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS in_execution BOOLEAN DEFAULT FALSE;
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS prospecting_campaign_id INTEGER REFERENCES prospecting_campaigns(id);
                """,
                """
                ALTER TABLE lead ADD COLUMN IF NOT EXISTS lead_score INTEGER;
                """,
                """
                CREATE TABLE IF NOT EXISTS prospecting_campaigns (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    target_segment VARCHAR(100),
                    objective TEXT,
                    tone_of_voice VARCHAR(100),
                    offer TEXT,
                    main_angle VARCHAR(100),
                    default_cta VARCHAR(255),
                    restrictions TEXT,
                    max_attempts INTEGER DEFAULT 3,
                    followup_interval_days INTEGER DEFAULT 3,
                    status VARCHAR(20) DEFAULT 'rascunho',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS prospecting_messages (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
                    lead_id INTEGER NOT NULL REFERENCES lead(id) ON DELETE CASCADE,
                    campaign_id INTEGER REFERENCES prospecting_campaigns(id) ON DELETE SET NULL,
                    channel VARCHAR(20) NOT NULL,
                    type VARCHAR(20) DEFAULT 'outbound',
                    status VARCHAR(30) DEFAULT 'pendente',
                    content TEXT,
                    ai_model VARCHAR(50),
                    ai_prompt TEXT,
                    approved_by INTEGER REFERENCES user(id),
                    approved_at TIMESTAMP,
                    sent_at TIMESTAMP,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS prospecting_settings (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE UNIQUE,
                    generate_message_webhook_url TEXT,
                    send_whatsapp_webhook_url TEXT,
                    send_email_webhook_url TEXT,
                    daily_send_limit INTEGER DEFAULT 50,
                    sending_start_time VARCHAR(5) DEFAULT '09:00',
                    sending_end_time VARCHAR(5) DEFAULT '18:00',
                    manual_approval_required BOOLEAN DEFAULT TRUE,
                    default_ai_model VARCHAR(50) DEFAULT 'gpt-4.1-mini',
                    default_tone VARCHAR(50) DEFAULT 'profissional',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        print("✅ Prospection migration complete!")


if __name__ == "__main__":
    app = create_app()
    apply_prospecting_migration(app)