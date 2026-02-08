import os
try:
    from dotenv import load_dotenv
    load_dotenv() # Load env vars before anything else
except ImportError:
    pass # In production (Vercel), env vars are usually injected directly, so this is fine.

from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Blueprint
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from models import db, User, Task, Role
import json
# Blueprint imports moved to create_app to prevent global import crashes
from services.supabase_service import init_supabase
from flask_cors import CORS

def create_app():
    # EMERGENCY WRAPPER
    try:
        app = Flask(__name__, instance_path='/tmp')
        app.instance_path = '/tmp' # FORCE override for Vercel
        
        # Allow Chrome Extensions (Defensive)
        try:
             CORS(app, resources={r"/api/ext/*": {"origins": "*"}})
        except:
             print("⚠️ CORS/Flask-Cors not available. Skipping.")

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        
        print("🚀 APP STARTUP: VERSION VERCEL-FIX-V6 (Auto-Migrate Contract)")
        
        # --- CONFIGURATION ---
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'northway-crm-secure-key')
        
        # Database Setup with Resilience
        database_url = os.environ.get('DATABASE_URL')
        
        def test_db_connection(url):
            if not url: return False
            try:
                # Short timeout (5s) to avoid hanging startup
                engine = create_engine(url, connect_args={'connect_timeout': 5})
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            except Exception as conn_e:
                print(f"📡 DB CONNECTION TEST FAILED: {conn_e}")
                return False

        try:
            # 1. Normalize Postgres URL
            if database_url and database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            # 2. Check if we should use Postgres and if it's reachable
            is_postgres = database_url and 'postgresql' in database_url
            connection_ok = False
            
            if is_postgres:
                try:
                    import psycopg2
                    print("🐘 DATABASE: Testing PostgreSQL connection...")
                    connection_ok = test_db_connection(database_url)
                except ImportError:
                    print("⚠️ Postgres configured but 'psycopg2' missing.")
            
            # 3. Decision Logic & Fallbacks
            if is_postgres and connection_ok:
                print("✅ DATABASE: Connection to PostgreSQL successful.")
            else:
                if is_postgres:
                    print("⚠️ DATABASE: PostgreSQL unreachable or driver error. Falling back to SQLite.")
                
                # Vercel/Local SQLite Choice
                src_db = os.path.join(app.root_path, 'crm.db')
                tmp_db = '/tmp/crm.db'
                
                if os.path.exists(src_db):
                    # If we are on Vercel (read-only), we might need to copy to /tmp
                    # On local mac, we can just use crm.db directly
                    if os.access(app.root_path, os.W_OK):
                        database_url = f'sqlite:///{src_db}'
                        print(f"🏠 DATABASE: Using local SQLite at {src_db}")
                    else:
                        import shutil
                        try:
                            shutil.copy2(src_db, tmp_db)
                            database_url = f'sqlite:///{tmp_db}'
                            print(f"📦 DATABASE: Using copied SQLite at {tmp_db} (Vercel Mode)")
                        except:
                            database_url = 'sqlite:///:memory:'
                            print("💾 DATABASE: Read-only FS and copy failed. Using In-Memory.")
                else:
                    print("⚠️ DATABASE: No 'crm.db' found. Using /tmp/crm.db (Fresh).")
                    database_url = 'sqlite:////tmp/crm.db'

        except Exception as e:
            print(f"🔥 CRITICAL DB SETUP ERROR: {e}")
            database_url = 'sqlite:///:memory:' 

        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Folders
        app.config['UPLOAD_FOLDER'] = 'static/uploads/profiles'
        app.config['COMPANY_UPLOAD_FOLDER'] = 'static/uploads/company'
        
        # Check for read-only filesystem (Vercel)
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            os.makedirs(app.config['COMPANY_UPLOAD_FOLDER'], exist_ok=True)
        except OSError:
            app.config['UPLOAD_FOLDER'] = '/tmp/uploads/profiles'
            app.config['COMPANY_UPLOAD_FOLDER'] = '/tmp/uploads/company'
            try:
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                os.makedirs(app.config['COMPANY_UPLOAD_FOLDER'], exist_ok=True)
            except: pass

        # Supabase Setup
        app.config['SUPABASE_URL'] = os.environ.get('SUPABASE_URL')
        app.config['SUPABASE_KEY'] = os.environ.get('SUPABASE_KEY')
        app.config['SUPABASE_SERVICE_ROLE_KEY'] = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        try:
            app.supabase = init_supabase(app)
        except Exception as supabase_e:
            print(f"Supabase Init Error: {supabase_e}")
            app.supabase = None

        # --- INITIALIZE EXTENSIONS ---
        db.init_app(app)
        migrate = Migrate(app, db)
        
        login_manager = LoginManager()
        login_manager.login_view = 'auth.login'
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        @app.context_processor
        def inject_globals():
            # Brasília Time (UTC-3)
            now_br = datetime.utcnow() - timedelta(hours=3)
            
            # FAST FAIL: If DB isn't ready or schema is updating, don't crash
            try:
                if current_user and current_user.is_authenticated:
                     from models import Task
                     try:
                         pending_count = Task.query.filter_by(assigned_to_id=current_user.id, status='pendente').count()
                         return dict(pending_tasks_count=pending_count, now=now_br, dict=dict)
                     except:
                         return dict(pending_tasks_count=0, now=now_br, dict=dict)
            except:
                 pass

            return dict(pending_tasks_count=0, now=now_br, dict=dict)

        # --- BLOCKING LOGIC ---
        @app.before_request
        def check_company_status():
            # Exclude statics and non-blocking routes
            if not request.endpoint: return
            
            allowed_routes = ['static', 'auth.login', 'auth.logout', 'auth.blocked_account', 'master.dashboard', 'master.system_reset', 'master.test_email', 'master.sync_schema', 'docs.ebook_institutional']
            if request.endpoint in allowed_routes:
                return

            if current_user and current_user.is_authenticated:
                # Super Admins are NEVER blocked
                if getattr(current_user, 'is_super_admin', False):
                    return
                
                company = current_user.company
                if not company:
                    return

                # 1. Manual Block (MASTER SWITCH)
                if company.platform_inoperante:
                    return redirect(url_for('auth.blocked_account', reason='manual'))

                # 2. Automated Block (30 Days Inadimplência)
                if company.payment_status == 'overdue' and company.overdue_since:
                    days_overdue = (datetime.utcnow() - company.overdue_since).days
                    if days_overdue >= 30:
                        return redirect(url_for('auth.blocked_account', reason='overdue'))
                
                # 3. Trial Expired
                if company.payment_status == 'trial' and company.trial_ends_at:
                    if datetime.utcnow() > company.trial_ends_at:
                        return redirect(url_for('auth.blocked_account', reason='trial_expired'))

        @app.template_filter('from_json')
        def from_json_filter(s):
            if not s: return {}
            try:
                return json.loads(s)
            except:
                return {}

        # --- ERROR HANDLERS ---
        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('404.html'), 404

        @app.errorhandler(500)
        def internal_error(error):
            # Fail-safe rollback
            try: db.session.rollback()
            except: pass
            
            import traceback
            tb = traceback.format_exc()
            return render_template('500.html', error=str(error), traceback=tb), 500

        @app.route('/debug_schema')
        def debug_schema():
            debug_info = {}
            try:
                # 1. Env Var Check
                url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                masked_url = url.replace(url.split('@')[0], '***') if '@' in url else '***'
                debug_info['masked_url'] = masked_url
                
                # 2. Connection Test
                from sqlalchemy import text, inspect
                with db.engine.connect() as conn:
                    result = conn.execute(text("SELECT 1")).scalar()
                    debug_info['connection_status'] = "OK" if result == 1 else "FAILED"
                
                # 3. Schema Inspect
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                schema_info = {}
                for table in tables:
                     cols = [c['name'] for c in inspector.get_columns(table)]
                     schema_info[table] = cols
                
                return jsonify({'status': 'ok', 'debug_info': debug_info, 'tables': tables, 'schema': schema_info})
            except Exception as e:
                import traceback
                return jsonify({'error': str(e), 'traceback': traceback.format_exc(), 'partial_info': debug_info}), 500

        # --- REGISTER BLUEPRINTS ---
            # --- REGISTER BLUEPRINTS ---
        try:
            from auth import auth as auth_blueprint
            from master import master as master_blueprint
            from routes.financial import financial_bp
            from routes.docs import docs_bp
            from routes.goals import goals_bp
            from routes.prospecting import prospecting_bp
            from routes.integrations import integrations_bp
            from routes.admin import admin_bp
            from routes.api_debug import api_debug_bp
            
            app.register_blueprint(auth_blueprint)
            app.register_blueprint(master_blueprint)
            app.register_blueprint(financial_bp)
            app.register_blueprint(docs_bp)
            app.register_blueprint(goals_bp)
            app.register_blueprint(prospecting_bp)
            app.register_blueprint(integrations_bp)
            app.register_blueprint(admin_bp)
            app.register_blueprint(api_debug_bp)
            
            # Safe Register for complex blueprints that might break on schema
            from routes.api_extension import api_ext
            from routes.whatsapp import whatsapp_bp
            from routes.clients import clients_bp
            from routes.leads import leads_bp
            from routes.leads_enrichment import enrichment_bp
            from routes.contracts import contracts_bp
            from routes.dashboard import dashboard_bp
            from routes.tasks import tasks_bp
            from routes.templates import templates_bp
            from routes.checklists import checklists_bp
            from routes.notifications import notifications_bp
            from routes.roles import roles_bp
            from routes.billing import billing_bp
            from routes.service_orders import service_orders_bp

            app.register_blueprint(api_ext)
            app.register_blueprint(whatsapp_bp)
            app.register_blueprint(clients_bp)
            app.register_blueprint(leads_bp)
            app.register_blueprint(enrichment_bp)
            app.register_blueprint(contracts_bp)
            app.register_blueprint(dashboard_bp)
            app.register_blueprint(tasks_bp)
            app.register_blueprint(templates_bp)
            app.register_blueprint(checklists_bp)
            app.register_blueprint(notifications_bp)
            app.register_blueprint(roles_bp)
            app.register_blueprint(billing_bp)
            app.register_blueprint(service_orders_bp)
            
        except Exception as bp_e:
            print(f"Blueprint Registration/Import Error: {bp_e}")
            import traceback
            traceback.print_exc()
            # We continue so the app launches and sys_admin works (or emergency mode catches if critical)
            # Actually, if master fails, we might want to let it bubble up to the factory_e handler?
            # Let's re-raise to see the error page!
            raise bp_e

        # --- BILLING MIDDLEWARE ---
        @app.before_request
        def check_platform_access():
            # Open Routes (Webhooks, Static, Auth)
            if not request.endpoint: return
            if request.endpoint.startswith('static'): return
            
            # FORCE IGNORE SYS_ADMIN ROUTES (Fix DB Crash)
            if request.path.startswith('/sys_admin'): return

            if request.endpoint in ['auth.login', 'auth.register', 'auth.logout', 
                                  'billing.asaas_webhook', 'billing.payment_pending',
                                  'auth.suspended_account', 'master.revert_access',
                                  'master.sync_schema']: # Allow sync!
                return

            # Check Login & Inoperability
            if current_user.is_authenticated and current_user.company:
                company = current_user.company
                
                # 1. STRICT SUSPENSION CHECK (Overrides everything)
                # If status is suspended or cancelled, BLOCK ACCESS immediately.
                # Except for Super Admin (real one, not impersonating) - actually, if impersonating we might want to see it?
                # Let's block everyone including impersonators, BUT allow revert_access (added above).
                if getattr(company, 'status', 'active') in ['suspended', 'cancelled']:
                    # If it's a super admin viewing, maybe we show a flash? 
                    # For now, strict block to ensure security.
                    return render_template('suspended.html', company_name=company.name, company_id=company.id)

                # --- LAZY BLOCK ENGINE (D+30) ---
                # If Overdue > 30 days, force block immediately on next request
                # EXEMPTION: 'courtesy' status is immune to blocks
                if company.payment_status == 'overdue' and company.overdue_since and company.payment_status != 'courtesy':
                    days_late = (datetime.utcnow() - company.overdue_since).days
                    if days_late >= 30 and not company.platform_inoperante:
                        print(f"🚫 BLOCKING COMPANY {company.name} due to {days_late} days overdue.")
                        company.platform_inoperante = True
                        company.payment_status = 'blocked'
                        # Ideally we would send email here, but for laziness we skip or trigger async
                        db.session.commit()

                # --- ACCESS CONTROL ---
                if getattr(company, 'platform_inoperante', False):
                    # Allow access to specific routes needed for billing
                    if request.endpoint.startswith('billing.'):
                        return
                    # Redirect everything else to payment pending
                    return redirect(url_for('billing.payment_pending'))
            
        # --- AUTO-MIGRATION / TABLE CREATION ---
        # Critical for Vercel/Ephemeral environments
        with app.app_context():
            try:
                # 1. Simple Table Creation
                db.create_all()
                print("✅ Tables created (if missing).")
                
                # 2. Seed Admin (Safe Check)
                try:
                    if not User.query.first():
                         print("🌱 Seeding default Admin...")
                         from models import Company
                         from werkzeug.security import generate_password_hash
                         # ... (seeding logic simplified for brevity or robustness)
                         if not Company.query.first():
                             c = Company(name="NorthWay Default", plan="pro", status="active", payment_status="trial") # FIX: Ensure defaults
                             db.session.add(c)
                             db.session.commit()
                             r = Role(name="Administrador", company_id=c.id, permissions=["admin_view"])
                             db.session.add(r)
                             db.session.commit()
                             u = User(name="Admin", email="admin@northway.com", password_hash=generate_password_hash("123456"), company_id=c.id, role="admin", role_id=r.id)
                             db.session.add(u)
                             db.session.commit()
                except Exception as seed_err:
                     print(f"⚠️ Seeding Error: {seed_err}")

                # 3. Add Columns (Critical for Billing) - GUARDED
                try:
                    from sqlalchemy import inspect
                    inspector = inspect(db.engine)
                    
                    if inspector.has_table("company"):
                        with db.engine.connect() as conn:
                            columns = [c['name'] for c in inspector.get_columns("company")]
                            
                            # Safely add columns
                            for col, dtype in [('next_due_date', 'DATE'), ('trial_start_date', 'DATETIME'), ('trial_end_date', 'DATETIME')]:
                                if col not in columns:
                                    try:
                                        print(f"📦 MIGRATION: Adding {col}...")
                                        conn.execute(text(f"ALTER TABLE company ADD COLUMN {col} {dtype}"))
                                    except Exception as alt_e:
                                        print(f"FAILED TO ADD {col}: {alt_e}")
                            
                            conn.commit()
                            print("✅ MIGRATION: Schema checks completed.")
                            
                    # 4. TRANSACTION MIGRATION (Fix Missing Columns)
                    if inspector.has_table("transaction"):
                        with db.engine.connect() as conn:
                            # Note: inspector.get_columns("transaction") might fail if reserved word isn't quoted, but usually sqlalchemy handles it.
                            # Just be safe and catch errors.
                            try:
                                t_columns = [c['name'] for c in inspector.get_columns("transaction")]
                                
                                # Setup columns to add
                                tx_cols = [
                                    ('nfse_status', 'VARCHAR(20) DEFAULT \'pending\''),
                                    ('nfse_number', 'VARCHAR(50)'),
                                    ('nfse_id', 'VARCHAR(50)'),
                                    ('nfse_pdf_url', 'VARCHAR(500)'),
                                    ('nfse_xml_url', 'VARCHAR(500)'),
                                    ('nfse_issued_at', 'TIMESTAMP')
                                ]
                                
                                for col, dtype in tx_cols:
                                    if col not in t_columns:
                                        try:
                                            print(f"📦 MIGRATION: Adding transaction.{col}...")
                                            conn.execute(text(f"ALTER TABLE \"transaction\" ADD COLUMN {col} {dtype}"))
                                        except Exception as tx_e:
                                            print(f"FAILED TO ADD transaction.{col}: {tx_e}")
                                
                                conn.commit()
                                print("✅ MIGRATION: Transaction schema checks completed.")
                            except Exception as insp_e:
                                print(f"⚠️ Transaction Inspection Error: {insp_e}")

                    # 5. CONTRACT MIGRATION (Fix Missing Columns)
                    if inspector.has_table("contract"):
                        with db.engine.connect() as conn:
                            try:
                                c_columns = [c['name'] for c in inspector.get_columns("contract")]
                                
                                # Setup columns to add
                                ctr_cols = [
                                    ('amount', 'FLOAT DEFAULT 0.0'),
                                    ('billing_type', 'VARCHAR(20) DEFAULT \'BOLETO\''),
                                    ('total_installments', 'INTEGER DEFAULT 12'),
                                    ('emit_nfse', 'BOOLEAN DEFAULT TRUE'),
                                    ('nfse_service_code', 'VARCHAR(20)'),
                                    ('nfse_iss_rate', 'FLOAT'),
                                    ('nfse_desc', 'VARCHAR(255)')
                                ]
                                
                                for col, dtype in ctr_cols:
                                    if col not in c_columns:
                                        try:
                                            print(f"📦 MIGRATION: Adding contract.{col}...")
                                            conn.execute(text(f"ALTER TABLE contract ADD COLUMN {col} {dtype}"))
                                        except Exception as ctr_e:
                                            print(f"FAILED TO ADD contract.{col}: {ctr_e}")
                                
                                conn.commit()
                                print("✅ MIGRATION: Contract schema checks completed.")
                            except Exception as insp_e:
                                print(f"⚠️ Contract Inspection Error: {insp_e}")
                                
                except Exception as mig_e:
                    print(f"⚠️ Migration/Inspect Error: {mig_e}")

            except Exception as context_e:
                print(f"❌ Startup Context Error: {context_e}")

        # --- GLOBAL CONTEXT PROCESSOR ---
        @app.context_processor
        def inject_saas_metrics():
            try:
                # SKIP FOR ADMIN ROUTES to avoid schema crashes during fix
                if request.path.startswith('/sys_admin'):
                    return {}

                if not current_user.is_authenticated or not current_user.company_id:
                    return {}
                
                # Days Remaining Calculation
                days_remaining = None
                # Use getattr safe access incase model validation fails
                company = current_user.company
                if company and getattr(company, 'next_due_date', None):
                    from datetime import date
                    delta = company.next_due_date - date.today()
                    days_remaining = delta.days
                
                return dict(subscription_days_remaining=days_remaining)
            except:
                return {}

        return app

        return app
    except Exception as factory_e:
        import traceback
        traceback.print_exc()
        # Capture error for closure
        error_msg = str(factory_e)
        print(f"🔥 FATAL FACTORY EXPLOSION: {error_msg}")
        
        
        # EMERGENCY APP
        # from flask import Flask, render_template (Already imported globally)
        fallback = Flask(__name__)
        @fallback.route('/')
        @fallback.route('/<path:path>')
        def emergency_catch_all(path=''):
            return f"<h1>EMERGENCY MODE</h1><p>The app failed to start.</p><pre>{error_msg}</pre>", 503
            
        @fallback.route('/ping')
        def ping(): return "pong_emergency"
        
        return fallback

app = create_app()

# --- TEMPORARY MIGRATION ROUTE ---
# Triggers the schema update and data migration when accessed.
# Security: Basic check or relying on admin login (if active) or just obscurity for this quick fix.
# Ideally would be a CLI command.
@app.route('/sys_admin/migrate_contacts_fix')
def sys_migrate_contacts():
    # ... existing ...
    return jsonify({"status": "ignored"})

@app.route('/sys_admin/force_trial_migration')
def force_trial_migration():
    try:
        with db.engine.connect() as conn:
            # Force add columns ignoring errors if they exist
            try: conn.execute(text("ALTER TABLE company ADD COLUMN trial_start_date TIMESTAMP"))
            except Exception as e: print(e)
            
            try: conn.execute(text("ALTER TABLE company ADD COLUMN trial_end_date TIMESTAMP"))
            except Exception as e: print(e)
            
            conn.commit()
        return "Migration Forced. Restart app."
    except Exception as e:
        return str(e)

@app.route('/sys_admin/migrate_gmb')
def sys_migrate_gmb():
    try:
        results = []
        with db.engine.connect() as conn:
            # 1. LEADS
            for col, dtype in [
                ('gmb_link', 'VARCHAR(500)'),
                ('gmb_rating', 'FLOAT DEFAULT 0.0'),
                ('gmb_reviews', 'INTEGER DEFAULT 0'),
                ('gmb_photos', 'INTEGER DEFAULT 0'),
                ('gmb_last_sync', 'TIMESTAMP')
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE lead ADD COLUMN IF NOT EXISTS {col} {dtype}"))
                    results.append(f"Added {col} to LEAD")
                except Exception as e:
                    results.append(f"Skipped {col} in LEAD (Exists?)")

            # 2. CLIENTS
            for col, dtype in [
                ('gmb_link', 'VARCHAR(500)'),
                ('gmb_rating', 'FLOAT DEFAULT 0.0'),
                ('gmb_reviews', 'INTEGER DEFAULT 0'),
                ('gmb_photos', 'INTEGER DEFAULT 0'),
                ('gmb_last_sync', 'TIMESTAMP')
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE client ADD COLUMN {col} {dtype}"))
                    results.append(f"Added {col} to CLIENT")
                except Exception as e:
                    results.append(f"Skipped {col} in CLIENT (Exists?)")
            
            conn.commit()
            
        return jsonify({"status": "success", "log": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/sys_admin/fix_transaction_schema')
def sys_fix_transaction_schema():
    try:
        results = []
        with db.engine.connect() as conn:
            # Transaction Columns
            columns_to_add = [
                ('nfse_status', 'VARCHAR(20) DEFAULT \'pending\''),
                ('nfse_number', 'VARCHAR(50)'),
                ('nfse_id', 'VARCHAR(50)'),
                ('nfse_pdf_url', 'VARCHAR(500)'),
                ('nfse_xml_url', 'VARCHAR(500)'),
                ('nfse_issued_at', 'TIMESTAMP')
            ]
            
            for col, dtype in columns_to_add:
                try:
                    # Generic SQL (Postgres supports IF NOT EXISTS, SQLite might not in old versions, but we assume PG forprod)
                    # We use a try/catch block for safety across DBs
                    # QUOTE "transaction" because it is a reserved keyword!
                    conn.execute(text(f"ALTER TABLE \"transaction\" ADD COLUMN {col} {dtype}"))
                    results.append(f"✅ Added {col}")
                except Exception as e:
                    # Check if error is because column exists
                    err_msg = str(e).lower()
                    if 'duplicate column' in err_msg or 'already exists' in err_msg:
                        results.append(f"⚠️ Skipped {col} (Already exists)")
                    else:
                        results.append(f"❌ Failed {col}: {err_msg}")
            
            conn.commit()
        return jsonify({"status": "completed", "log": results})
    except Exception as e:
        return jsonify({"status": "critical_error", "error": str(e)}), 500

@app.route('/sys_admin/fix_task_schema')
def fix_task_schema():
    """
    Emergency route to fix Task table schema and create TaskEvent table.
    Adds: source_type, auto_generated, contract_id, service_order_id, created_by_user_id
    Creates: task_event table
    """
    try:
        results = []
        conn = db.engine.connect()
        
        # 1. Add Columns to Task
        cols = [
            ("source_type", "VARCHAR(50)"),
            ("auto_generated", "BOOLEAN DEFAULT FALSE"),
            ("contract_id", "INTEGER REFERENCES contract(id)"),
            ("service_order_id", "INTEGER REFERENCES service_order(id)"),
            ("created_by_user_id", "INTEGER REFERENCES \"user\"(id)")
        ]
        
        for col, dtype in cols:
            try:
                # Generic SQL (Postgres supports IF NOT EXISTS for columns in newer versions, else try/catch)
                # QUOTE "source_type" just in case, but "user" MUST be quoted in FK above
                conn.execute(text(f"ALTER TABLE task ADD COLUMN {col} {dtype}"))
                results.append(f"✅ Added task.{col}")
                conn.commit()
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    results.append(f"⚠️ task.{col} already exists")
                else:
                    results.append(f"❌ Failed task.{col}: {str(e)}")
        
        # 2. Create TaskEvent Table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS task_event (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL REFERENCES task(id),
                    actor_id INTEGER REFERENCES "user"(id),
                    actor_type VARCHAR(20) DEFAULT 'USER',
                    event_type VARCHAR(50) NOT NULL,
                    payload JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            results.append("✅ Created/Verified table task_event")
            conn.commit()
        except Exception as e:
            # SQLite fallback for SERIAL
            if "syntax error" in str(e).lower() and "SERIAL" in str(e):
                    results.append("⚠️ Retrying task_event for SQLite...")
                    conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS task_event (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id INTEGER NOT NULL REFERENCES task(id),
                        actor_id INTEGER REFERENCES "user"(id),
                        actor_type VARCHAR(20) DEFAULT 'USER',
                        event_type VARCHAR(50) NOT NULL,
                        payload JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                    results.append("✅ Created table task_event (SQLite)")
                    conn.commit()
            else:
                results.append(f"❌ Failed create task_event: {str(e)}")

        conn.close()
        return jsonify({"status": "completed", "log": results})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/checkout')
def checkout_fallback():
    return render_template('checkout_page.html')

# Health Check - Visible in Production (Moved to create_app)
# @app.route('/ping')
# def ping(): return "pong"

@app.route('/sys_admin/seed_library')
def sys_seed_library():
    try:
        from models import db, LibraryBook, Company, User
        
        # 1. Admin Company
        company = Company.query.get(6)
        if not company:
            admin = User.query.filter_by(is_super_admin=True).first()
            if admin and admin.company: company = admin.company
            else: return "No Admin Company Found", 404
            
        print(f"Seed Library Context: {company.name}")
        
        # 2. Add 'O Custo da Inação'
        book = LibraryBook.query.filter_by(title="O Custo da Inação").first()
        if not book:
            book = LibraryBook(
                title="O Custo da Inação",
                description="Apresentação estratégica para leads: como a falta de direção custa R$ 120k/ano.",
                category="Apresentação",
                cover_image="cover_inaction.jpg",
                route_name="docs.presentation_cost_of_inaction",
                active=True
            )
            db.session.add(book)
        else:
            book.cover_image = "cover_inaction.jpg"
            book.route_name = "docs.presentation_cost_of_inaction"
            
        # 2a. Add 'Diagnóstico do Mercado Óptico Local'
        diag_book = LibraryBook.query.filter_by(title="Diagnóstico do Mercado Óptico Local").first()
        if not diag_book:
            diag_book = LibraryBook(
                title="Diagnóstico do Mercado Óptico Local",
                description="Uma análise exclusiva e completa sobre o mercado óptico local, gargalos e oportunidades.",
                category="Apresentação",
                cover_image="cover_diagnostic.jpg",
                route_name="docs.presentation_diagnostic",
                active=True
            )
            db.session.add(diag_book)
        else:
            diag_book.cover_image = "cover_diagnostic.jpg"
            diag_book.route_name = "docs.presentation_diagnostic"
        
        db.session.commit()
        
        if company not in book.allowed_companies: book.allowed_companies.append(company)
        if company not in diag_book.allowed_companies: diag_book.allowed_companies.append(company)

        # 2b. Add 'Diagnóstico Completo (Novo)'
        # FIX: Ensure category is 'Apresentação' (singular) for template filter.
        combined_book = LibraryBook.query.filter_by(title="Diagnóstico Completo (Novo)").first()
        if not combined_book:
            combined_book = LibraryBook(
                title="Diagnóstico Completo (Novo)",
                description="Apresentação unificada com diagnóstico de mercado e insights estratégicos.",
                category="Apresentação", 
                cover_image="cover_diagnostic_combined.jpg",
                route_name="docs.presentation_diagnostic_combined",
                active=True
            )
            db.session.add(combined_book)
        else:
            combined_book.category = "Apresentação"
            combined_book.route_name = "docs.presentation_diagnostic_combined"
        
        db.session.commit()
        if company not in combined_book.allowed_companies: combined_book.allowed_companies.append(company)

        # 2c. Add 'Northway Growth Framework'
        growth_book = LibraryBook.query.filter_by(title="Northway Growth Framework").first()
        if not growth_book:
            growth_book = LibraryBook(
                title="Northway Growth Framework",
                description="The premium standard for visualizing the journey from high-intent acquisition to predictable retention.",
                category="Ebook",
                cover_image="cover_growth_framework.jpg",
                route_name="docs.presentation_growth_framework",
                active=True
            )
            db.session.add(growth_book)
        else:
            growth_book.category = "Ebook"
            growth_book.route_name = "docs.presentation_growth_framework"
        
        db.session.commit()
        if company not in growth_book.allowed_companies: growth_book.allowed_companies.append(company)

        # 2d. Add 'Northway Institucional (Completo)'
        inst_book = LibraryBook.query.filter_by(title="Northway Institucional (Completo)").first()
        if not inst_book:
            inst_book = LibraryBook(
                title="Northway Institucional (Completo)",
                description="Marketing que gera crescimento não é sorte. É processo. Guia completo.",
                category="Ebook",
                cover_image="cover_institutional_ebook.jpg",
                route_name="docs.ebook_institutional",
                active=True
            )
            db.session.add(inst_book)
        else:
            inst_book.category = "Ebook"
            inst_book.route_name = "docs.ebook_institutional"

        db.session.commit()
        if company not in inst_book.allowed_companies: inst_book.allowed_companies.append(company)

        # 3. Update Covers for All
        cover_map = {
            "Diagnóstico do Mercado Óptico Local": "north_compass.png",
            "Diagnóstico Completo (Novo)": "compass_banner.png",
            "Northway Growth Framework": "north_growth.png",
            "Northway Institucional (Completo)": "north_structure.png",
            "Diagnóstico Estratégico": "north_compass.png", 
            "Playbook Comercial": "north_growth.png",
            "Playbook de Processos": "north_structure.png",
            "Playbook de Treinamento": "north_meeting.png",
            "Onboarding Institucional": "north_meeting.png",
            "Manual do Usuário": "north_structure.png",
            "Apresentação Institucional": "north_structure.png",
            "Playbook BDR": "sdr-bg.png",
            "Oferta Principal": "north_growth.png",
            "Oferta Downsell": "north_growth.png",
            "Consultoria": "north_meeting.png",
            "Plano Essencial": "north_growth.png",
            "Manual de Onboarding": "north_structure.png",
            "Scripts": "north_growth.png",
            "Objeções": "north_growth.png",
            "Academia": "north_meeting.png"
        }
        
        for b in LibraryBook.query.all():
            updated = False
            for k, v in cover_map.items():
                if k in b.title: 
                    b.cover_image = v
                    updated = True
                    break
            if not updated:
                if not b.cover_image or 'default' in b.cover_image:
                     b.cover_image = "cover_general_playbook.jpg" if "playbook" in b.title.lower() else "cover_default.jpg"
        
        db.session.commit()
        return f"Library Seeded. 'O Custo da Inação' ID: {book.id}, Covers Updated."
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
