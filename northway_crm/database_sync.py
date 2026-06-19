import os
import time
from sqlalchemy import text, inspect
from flask import jsonify, current_app
from models import db, User, Company, Role, PipelineStageTaskTemplate, SwotAnalise, SwotItem, CREPIDiagnostico, CREPIPremissa, AudienceMatrix, CommercialPresentation, LibraryBook, Pipeline, PipelineStage, LibraryTemplate, CommissionRule, CommercialRole, CommissionSnapshot, AccountsPayable, ServiceOrder, FinancialCategory

def sync_database():
    """Consolidated migration and sync logic originally from app.py."""
    results = []
    
    try:
        # 1. Base Table Creation
        db.create_all()
        results.append("✅ Base tables created/verified via db.create_all().")

        with db.engine.connect() as conn:
            is_postgres = 'postgresql' in str(db.engine.url)
            inspector = inspect(db.engine)
            
            def add_column_if_missing(table_name, col_name, dtype):
                if is_postgres:
                    try:
                        conn.execute(text(f"ALTER TABLE \"{table_name}\" ADD COLUMN IF NOT EXISTS {col_name} {dtype}"))
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        results.append(f"⚠️ Failed {table_name}.{col_name}: {e}")
                    return

                # SQLite fallback
                results.append(f"🔍 Checking table '{table_name}' for column '{col_name}'...")
                if inspector.has_table(table_name):
                    columns = [c['name'] for c in inspector.get_columns(table_name)]
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE \"{table_name}\" ADD COLUMN {col_name} {dtype}"))
                            conn.commit()
                            results.append(f"✅ Added {table_name}.{col_name}")
                        except Exception as e:
                            conn.rollback()
                            results.append(f"⚠️ Failed {table_name}.{col_name}: {e}")

            # 2. Table Creation (Postgres/SQLite aware)
            def create_table_if_missing(table_name, psql_ddl, sqlite_ddl=None):
                if not inspector.has_table(table_name):
                    try:
                        ddl = psql_ddl if is_postgres else (sqlite_ddl or psql_ddl.replace('SERIAL', 'INTEGER PRIMARY KEY AUTOINCREMENT').replace('JSONB', 'TEXT'))
                        conn.execute(text(ddl))
                        conn.commit()
                        results.append(f"✅ Created table {table_name}")
                    except Exception as e:
                        conn.rollback()
                        results.append(f"❌ Failed to create {table_name}: {e}")

            # Define Tables
            create_table_if_missing("papeis_comerciais", """
                CREATE TABLE papeis_comerciais (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES company(id),
                    nome VARCHAR(100) NOT NULL,
                    descricao TEXT,
                    tipo_vinculo VARCHAR(20) NOT NULL,
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            create_table_if_missing("regras_comissao", """
                CREATE TABLE regras_comissao (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES company(id),
                    papel_comercial_id VARCHAR(36) NOT NULL REFERENCES papeis_comerciais(id),
                    modelo VARCHAR(50) NOT NULL,
                    parametros JSONB NOT NULL,
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            create_table_if_missing("comissao_snapshots", """
                CREATE TABLE comissao_snapshots (
                    id VARCHAR(36) PRIMARY KEY,
                    contract_id INTEGER REFERENCES contract(id),
                    service_order_id INTEGER REFERENCES service_order(id),
                    beneficiario_id INTEGER NOT NULL REFERENCES "user"(id),
                    papel_comercial_id VARCHAR(36) NOT NULL REFERENCES papeis_comerciais(id),
                    regra_id VARCHAR(36) NOT NULL REFERENCES regras_comissao(id),
                    modelo VARCHAR(50) NOT NULL,
                    percentual_provisorio FLOAT NOT NULL,
                    percentual_definitivo FLOAT,
                    data_fechamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    competencia_fechamento VARCHAR(7) NOT NULL,
                    valor_base_contratual NUMERIC(12, 2) DEFAULT 0.00,
                    base_calculo VARCHAR(20) DEFAULT 'valor_pago',
                    recorrente BOOLEAN DEFAULT TRUE
                )
            """)

            create_table_if_missing("contas_a_pagar", """
                CREATE TABLE contas_a_pagar (
                    id VARCHAR(36) PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES company(id),
                    tipo VARCHAR(20) NOT NULL,
                    beneficiario_id INTEGER REFERENCES "user"(id),
                    contract_id INTEGER REFERENCES contract(id),
                    service_order_id INTEGER REFERENCES service_order(id),
                    cliente_id INTEGER REFERENCES client(id),
                    asaas_payment_id VARCHAR(50),
                    competencia VARCHAR(7) NOT NULL,
                    valor_base_contratual NUMERIC(12, 2) NOT NULL,
                    valor_pago_cliente_total NUMERIC(12, 2) NOT NULL,
                    juros_cliente NUMERIC(12, 2) DEFAULT 0.00,
                    multa_cliente NUMERIC(12, 2) DEFAULT 0.00,
                    percentual_aplicado FLOAT NOT NULL,
                    valor_comissao_calculado NUMERIC(12, 2) NOT NULL,
                    valor_final_pago_colaborador NUMERIC(12, 2),
                    juros_pago_colaborador NUMERIC(12, 2) DEFAULT 0.00,
                    eh_ajuste BOOLEAN DEFAULT FALSE,
                    referencia_comissao_id VARCHAR(36) REFERENCES contas_a_pagar(id),
                    status VARCHAR(20) DEFAULT 'A_PAGAR',
                    data_pagamento TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            create_table_if_missing("tenant_integration", """
                CREATE TABLE tenant_integration (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id),
                    provider VARCHAR(50) NOT NULL,
                    status VARCHAR(20) DEFAULT 'disconnected',
                    google_account_email VARCHAR(120),
                    google_account_id VARCHAR(100),
                    refresh_token_encrypted TEXT,
                    access_token TEXT,
                    token_expiry_at TIMESTAMP,
                    root_folder_id VARCHAR(100),
                    root_folder_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_error TEXT
                )
            """)

            create_table_if_missing("integration_api_keys", """
                CREATE TABLE integration_api_keys (
                    id VARCHAR(36) PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id),
                    name VARCHAR(100) NOT NULL,
                    key_prefix VARCHAR(10) NOT NULL,
                    key_hash VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    last_used_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by_id INTEGER REFERENCES "user"(id)
                )
            """)

            create_table_if_missing("integration_webhooks", """
                CREATE TABLE integration_webhooks (
                    id VARCHAR(36) PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id),
                    name VARCHAR(100) NOT NULL,
                    url TEXT NOT NULL,
                    event_types TEXT NOT NULL,
                    secret_token VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'active',
                    last_triggered_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by_id INTEGER REFERENCES "user"(id)
                )
            """)

            create_table_if_missing("integration_logs", """
                CREATE TABLE integration_logs (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id),
                    api_key_id VARCHAR(36) REFERENCES integration_api_keys(id),
                    webhook_id VARCHAR(36) REFERENCES integration_webhooks(id),
                    type VARCHAR(20) NOT NULL,
                    event VARCHAR(100) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    request_method VARCHAR(10),
                    request_url TEXT,
                    payload JSONB,
                    response_code INTEGER,
                    response_body TEXT,
                    error_message TEXT,
                    duration_ms INTEGER,
                    ip_address VARCHAR(45),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            create_table_if_missing("drive_file_event", """
                CREATE TABLE drive_file_event (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id),
                    lead_id INTEGER REFERENCES lead(id),
                    client_id INTEGER REFERENCES client(id),
                    file_id VARCHAR(100) NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    mime_type VARCHAR(100),
                    web_view_link VARCHAR(500),
                    created_time TIMESTAMP,
                    modified_time TIMESTAMP,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            create_table_if_missing("task_event", """
                CREATE TABLE task_event (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL REFERENCES task(id),
                    actor_id INTEGER REFERENCES "user"(id),
                    actor_type VARCHAR(20) DEFAULT 'USER',
                    event_type VARCHAR(50) NOT NULL,
                    payload JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. Column Repairs
            # Lead & Client
            shared_cols = [
                ('diagnostic_status', "VARCHAR(20) DEFAULT 'pending'"),
                ('diagnostic_score', "FLOAT"),
                ('diagnostic_stars', "FLOAT"),
                ('diagnostic_classification', "VARCHAR(50)"),
                ('diagnostic_date', "TIMESTAMP"),
                ('diagnostic_pillars', "JSONB" if is_postgres else "TEXT"),
                ('diagnostic_answers', "JSONB" if is_postgres else "TEXT"),
                ('drive_folder_id', "VARCHAR(100)"),
                ('drive_folder_url', "VARCHAR(500)"),
                ('drive_folder_name', "VARCHAR(255)"),
                ('drive_last_scan_at', "TIMESTAMP"),
                ('drive_unread_files_count', "INTEGER DEFAULT 0"),
                ('gmb_link', "VARCHAR(500)"),
                ('gmb_rating', "FLOAT DEFAULT 0.0"),
                ('gmb_reviews', "INTEGER DEFAULT 0"),
                ('gmb_photos', "INTEGER DEFAULT 0"),
                ('gmb_last_sync', "TIMESTAMP"),
                ('profile_pic_url', "VARCHAR(500)"),
                ('lost_at', "TIMESTAMP"),
                ('lost_reason', "VARCHAR(500)"),
                ('lost_at_stage_name', "VARCHAR(100)"),
                # Prospecting Module Columns
                ('prospecting_status', "VARCHAR(50) DEFAULT 'novo'"),
                ('preferred_channel', "VARCHAR(20) DEFAULT 'whatsapp'"),
                ('wa_attempts', "INTEGER DEFAULT 0"),
                ('email_attempts', "INTEGER DEFAULT 0"),
                ('last_contact_at', "TIMESTAMP"),
                ('next_action_at', "TIMESTAMP"),
                ('last_angle', "VARCHAR(100)"),
                ('in_execution', "BOOLEAN DEFAULT FALSE"),
                ('prospecting_campaign_id', "INTEGER REFERENCES prospecting_campaigns(id)"),
                ('lead_score', "INTEGER DEFAULT 0")
            ]
            for t in ['lead', 'client']:
                for c, d in shared_cols: add_column_if_missing(t, c, d)

            # Prospecting Integrations (SMTP)
            for c, d in [
                ('smtp_host', "TEXT"),
                ('smtp_port', "INTEGER"),
                ('smtp_user', "TEXT"),
                ('sender_name', "TEXT"),
                ('sender_email', "TEXT"),
                ('ssl_tls', "BOOLEAN DEFAULT TRUE")
            ]: add_column_if_missing("prospecting_integrations", c, d)

            # Transaction & Expense
            nfse_cols = [
                ('nfse_status', "VARCHAR(20) DEFAULT 'pending'"),
                ('nfse_number', "VARCHAR(50)"),
                ('nfse_id', "VARCHAR(50)"),
                ('nfse_pdf_url', "VARCHAR(500)"),
                ('nfse_xml_url', "VARCHAR(500)"),
                ('nfse_issued_at', "TIMESTAMP")
            ]
            for c, d in nfse_cols: add_column_if_missing("transaction", c, d)
            add_column_if_missing("expense", "fixed_cost_id", "VARCHAR(36) REFERENCES custos_fixos_globais(id)")

            # Fixed Costs
            add_column_if_missing("custos_fixos_globais", "is_variable", "BOOLEAN DEFAULT FALSE")
            add_column_if_missing("custos_fixos_globais", "linked_user_id", "INTEGER REFERENCES \"user\"(id)")

            # Task
            for c, d in [
                ('source_type', "VARCHAR(50)"),
                ('auto_generated', "BOOLEAN DEFAULT FALSE"),
                ('is_urgent', "BOOLEAN DEFAULT FALSE"),
                ('is_important', "BOOLEAN DEFAULT FALSE"),
                ('completed_at', "TIMESTAMP"),
                ('created_by_user_id', "INTEGER REFERENCES \"user\"(id)")
            ]: add_column_if_missing("task", c, d)

            for c, d in [
                ('avg_ticket', "VARCHAR(50)"),
                ('margin', "VARCHAR(50)"),
                ('filled_by', "VARCHAR(100)")
            ]: add_column_if_missing("audience_matrices", c, d)

            # Commission Snapshots repair
            add_column_if_missing("comissao_snapshots", "valor_base_contratual", "NUMERIC(12, 2) DEFAULT 0.00")

            # DRE Extension Repairs
            add_column_if_missing("company", "tax_rate", "FLOAT DEFAULT 0.0")
            add_column_if_missing("financial_category", "is_deduction", "BOOLEAN DEFAULT FALSE")
            add_column_if_missing("transaction", "revenue_type", "VARCHAR(20) DEFAULT 'recorrente'")

            # WhatsApp Repairs
            for c, d in [
                ('company_id', "INTEGER"),
                ('instance_id', "INTEGER"),
                ('remote_jid', "VARCHAR(100)"),
                ('name', "VARCHAR(255)"),
                ('profile_pic_url', "TEXT"),
                ('unread_count', "INTEGER DEFAULT 0"),
                ('last_message_at', "TIMESTAMP"),
                ('last_message_preview', "TEXT"),
                ('last_message_dir', "VARCHAR(10) DEFAULT 'in'"),
                ('last_message_status', "VARCHAR(20) DEFAULT 'sent'"),
                ('created_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ('updated_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ]: add_column_if_missing("whatsapp_conversations", c, d)

            for c, d in [
                ('company_id', "INTEGER"),
                ('conversation_id', "INTEGER"),
                ('message_id', "VARCHAR(100)"),
                ('direction', "VARCHAR(10)"),
                ('type', "VARCHAR(20)"),
                ('content', "TEXT"),
                ('media_url', "TEXT"),
                ('status', "VARCHAR(20)"),
                ('sender_name', "VARCHAR(255)"),
                ('participant_jid', "VARCHAR(100)"),
                ('created_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ('updated_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ]: add_column_if_missing("whatsapp_messages", c, d)

            # 4. Data Seeding
            # Admin Seed
            admin_user = User.query.filter_by(email="admin@northway.com").first()
            if not admin_user:
                from werkzeug.security import generate_password_hash
                c = Company(name="NorthWay Default", plan="pro", status="active", payment_status="trial")
                db.session.add(c)
                db.session.commit()
                r = Role(name="Administrador", company_id=c.id, permissions=["admin_view"])
                db.session.add(r)
                db.session.commit()
                u = User(name="Admin", email="admin@northway.com", password_hash=generate_password_hash("123456"), 
                         company_id=c.id, role="admin", role_id=r.id, is_super_admin=True)
                db.session.add(u)
                db.session.commit()
                results.append("🌱 Seeded default admin user.")

            # Library Books Seed
            # ... (omitted for brevity)
            db.session.commit()

            # 5. Financial Deduction Categories Seed
            deduction_cats = [
                "Taxas Asaas", 
                "Taxas de cartão/gateway", 
                "Impostos s/ faturamento", 
                "Estornos/Inadimplência"
            ]
            companies = Company.query.all()
            for comp in companies:
                for cat_name in deduction_cats:
                    exists = FinancialCategory.query.filter_by(company_id=comp.id, name=cat_name).first()
                    if not exists:
                        new_cat = FinancialCategory(
                            name=cat_name,
                            type='expense',
                            is_deduction=True,
                            is_default=True,
                            company_id=comp.id
                        )
                        db.session.add(new_cat)
                        results.append(f"📑 Seeded category '{cat_name}' for company {comp.id}")
            db.session.commit()

        return results
    except Exception as e:
        db.session.rollback()
        raise e
