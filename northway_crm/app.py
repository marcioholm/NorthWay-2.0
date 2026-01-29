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

def create_app():
    # EMERGENCY WRAPPER
    try:
        app = Flask(__name__, instance_path='/tmp')
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        
        print("🚀 APP STARTUP: VERSION VERCEL-FIX-V3")
        
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
                    print("⚠️ DATABASE: No 'crm.db' found. Using In-Memory.")
                    database_url = 'sqlite:///:memory:'

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
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            os.makedirs(app.config['COMPANY_UPLOAD_FOLDER'], exist_ok=True)

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

        # --- CONTEXT PROCESSORS ---
        @app.context_processor
        def inject_globals():
            # FAST FAIL: If DB isn't ready or schema is updating, don't crash
            # This is critical for the migration route to work
            try:
                 # Only try this if user object is fully loaded and valid
                 if current_user and current_user.is_authenticated:
                     # Minimal check, avoid complex joins
                     from models import Task
                     # Use a separate protected block for the query
                     try:
                         pending_count = Task.query.filter_by(assigned_to_id=current_user.id, status='pendente').count()
                         return dict(pending_tasks_count=pending_count, now=datetime.now())
                     except:
                         # If table doesn't exist or connection failed, return 0
                         return dict(pending_tasks_count=0, now=datetime.now())
            except:
                 # Absolute fallback
                 pass

            return dict(pending_tasks_count=0, now=datetime.now())

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
            db.session.rollback()
            import traceback
            return render_template('500.html', error=str(error), traceback=traceback.format_exc()), 500

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
            
            app.register_blueprint(auth_blueprint)
            app.register_blueprint(master_blueprint)
            app.register_blueprint(financial_bp)
            app.register_blueprint(docs_bp)
            app.register_blueprint(goals_bp)
            app.register_blueprint(prospecting_bp)
            app.register_blueprint(integrations_bp)
            app.register_blueprint(admin_bp)
            
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
            if request.endpoint in ['auth.login', 'auth.register', 'auth.logout', 
                                  'billing.asaas_webhook', 'billing.payment_pending',
                                  'auth.suspended_account', 'master.revert_access']: # Allow revert!
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
        # --- AUTO-MIGRATION / TABLE CREATION ---
        # Critical for Vercel/Ephemeral environments
        # DISABLED FOR STABILITY DIAGNOSIS
        # with app.app_context():
        #     pass 
            # try:
            #     # Check if critical tables exist
            #     from sqlalchemy import inspect
            #     inspector = inspect(db.engine)
            #     if not inspector.has_table("user"):
            #         print("⚠️ Tables missing! Running db.create_all()...")
            #         db.create_all()
            #         print("✅ Tables created.")
            #     else:
            #         # MIGRATE: Add Enrichment Columns if missing
            #         print("🐘 DATABASE: Checking for missing CNPJ enrichment columns...")
            #         # ... (Rest of migration logic commented out implicitly by not running the block)
            # except Exception as seed_e:
            #     print(f"❌ Auto-migration failed: {seed_e}")
                    columns_to_add = [
                        ("legal_name", "VARCHAR(200)"),
                        ("cnpj", "VARCHAR(20)"),
                        ("registration_status", "VARCHAR(50)"),
                        ("company_size", "VARCHAR(50)"),
                        ("equity", "FLOAT"),
                        ("foundation_date", "VARCHAR(20)"),
                        ("legal_email", "VARCHAR(120)"),
                        ("legal_phone", "VARCHAR(50)"),
                        ("cnae", "VARCHAR(200)"),
                        ("partners_json", "TEXT"),
                        ("enrichment_history", "TEXT")
                    ]
                    
                    for col_name, col_type in columns_to_add:
                        try:
                            # Check if column exists
                            has_col = any(c['name'] == col_name for c in inspector.get_columns("lead"))
                            if not has_col:
                                print(f"📦 MIGRATION: Adding {col_name} to lead table...")
                                db.session.execute(text(f"ALTER TABLE lead ADD COLUMN {col_name} {col_type}"))
                                db.session.commit()
                                print(f"✅ MIGRATION: {col_name} added.")
                        except Exception as migration_e:
                            db.session.rollback()
                            print(f"❌ MIGRATION ERROR on {col_name}: {migration_e}")
                    
                    # Update inspector for subsequent checks
                    inspector = inspect(db.engine)

                    # MIGRATE: Add assigned_to_id to client_checklist if missing
                    if inspector.has_table("client_checklist"):
                        try:
                            has_col = any(c['name'] == 'assigned_to_id' for c in inspector.get_columns("client_checklist"))
                            if not has_col:
                                print("📦 MIGRATION: Adding assigned_to_id to client_checklist...")
                                with db.engine.connect() as conn:
                                    conn.execute(text("ALTER TABLE client_checklist ADD COLUMN assigned_to_id INTEGER REFERENCES \"user\"(id)"))
                                    conn.commit()
                                print("✅ MIGRATION: assigned_to_id added to client_checklist.")
                        except Exception as cl_migration_e:
                            print(f"❌ MIGRATION ERROR on client_checklist: {cl_migration_e}")

                    # MIGRATE: Add logo_base64 to company if missing
                    if inspector.has_table("company"):
                        try:
                            has_col = any(c['name'] == 'logo_base64' for c in inspector.get_columns("company"))
                            if not has_col:
                                print("📦 MIGRATION: Adding logo_base64 to company...")
                                with db.engine.connect() as conn:
                                    conn.execute(text("ALTER TABLE company ADD COLUMN logo_base64 TEXT"))
                                    conn.commit()
                                print("✅ MIGRATION: logo_base64 added to company.")
                        except Exception as co_migration_e:
                            print(f"❌ MIGRATION ERROR on company: {co_migration_e}")

                    # MIGRATE: Add Asaas Billing columns to company if missing
                    if inspector.has_table("company"):
                        try:
                            billing_cols = [
                                ("plan_id", "VARCHAR(50)"),
                                ("asaas_customer_id", "VARCHAR(50)"),
                                ("payment_status", "VARCHAR(20) DEFAULT 'trial'"),
                                ("platform_inoperante", "BOOLEAN DEFAULT FALSE"),
                                ("overdue_since", "TIMESTAMP")
                            ]
                            existing_cols = [c['name'] for c in inspector.get_columns("company")]
                            
                            # for col_name, col_type in billing_cols:
                            #     if col_name not in existing_cols:
                            #         print(f"📦 MIGRATION: Adding {col_name} to company...")
                            #         with db.engine.connect() as conn:
                            #             # Use safe DDL
                            #             conn.execute(text(f"ALTER TABLE company ADD COLUMN {col_name} {col_type}"))
                            #             conn.commit()
                            #         print(f"✅ MIGRATION: {col_name} added to company.")
                            pass # Validating stability first
                            
                        except Exception as bill_migration_e:
                             print(f"❌ MIGRATION ERROR on Billing Columns: {bill_migration_e}")
                        
                        # MIGRATE: Add next_due_date (Date type) - REMOVED FOR STABILITY
                        # Will be handled via manual route

                    # MIGRATE: Create BillingEvent table if missing

                    # MIGRATE: Create BillingEvent table if missing
                    if not inspector.has_table("billing_event"):
                        print("📦 MIGRATION: Creating BillingEvent table...")
                        try:
                            with db.engine.connect() as conn:
                                # Use cross-compatible SQL (works on PG and mostly SQLite)
                                conn.execute(text("""
                                    CREATE TABLE billing_event (
                                        id SERIAL PRIMARY KEY,
                                        company_id INTEGER REFERENCES company(id),
                                        event_type VARCHAR(50) NOT NULL,
                                        payload JSON,
                                        processed_at TIMESTAMP,
                                        idempotency_key VARCHAR(100) UNIQUE,
                                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                    );
                                """))
                                conn.commit()
                            print("✅ MIGRATION: BillingEvent table created.")
                        except Exception as be_migration_e:
                            # Fallback for SQLite locally if SERIAL fails
                            if 'syntax error' in str(be_migration_e) and 'sqlite' in str(db.engine.url):
                                 print("⚠️ SQLite fallback for BillingEvent...")
                                 db.create_all() # Let SQLAlchemy handle it
                            else:
                                 print(f"❌ MIGRATION ERROR on BillingEvent: {be_migration_e}")
                    
                # Seed minimal data if empty (prevent lockout)
                if not User.query.first():
                    print("🌱 Seeding default Admin...")
                    # Create default company and user if needed
                    from models import Company
                    from werkzeug.security import generate_password_hash
                    
                    if not Company.query.first():
                        c = Company(name="NorthWay Default", plan="pro", status="active")
                        db.session.add(c)
                        db.session.commit()
                        
                        r = Role(name="Administrador", company_id=c.id, permissions=["admin_view"]) # Simplified
                        db.session.add(r)
                        db.session.commit()
                        
                        u = User(
                            name="Admin", 
                            email="admin@northway.com", 
                            password_hash=generate_password_hash("123456"),
                            company_id=c.id,
                            role="admin",
                            role_id=r.id
                        )
                        db.session.add(u)
                        db.session.commit()
                        print("✅ Default Admin created: admin@northway.com / 123456")
                    # ...
                    pass

        return app
    except Exception as factory_e:
        import traceback
                    ("legal_email", "VARCHAR(120)"),
                    ("legal_phone", "VARCHAR(50)"),
                    ("cnae", "VARCHAR(200)"),
                    ("partners_json", "TEXT"),
                    ("enrichment_history", "TEXT")
                ]
                
                for col_name, col_type in columns_to_add:
                    try:
                        # Check if column exists
                        has_col = any(c['name'] == col_name for c in inspector.get_columns("lead"))
                        if not has_col:
                            print(f"📦 MIGRATION: Adding {col_name} to lead table...")
                            db.session.execute(text(f"ALTER TABLE lead ADD COLUMN {col_name} {col_type}"))
                            db.session.commit()
                            print(f"✅ MIGRATION: {col_name} added.")
                    except Exception as migration_e:
                        db.session.rollback()
                        print(f"❌ MIGRATION ERROR on {col_name}: {migration_e}")
                
                # Update inspector for subsequent checks
                inspector = inspect(db.engine)

                # MIGRATE: Add assigned_to_id to client_checklist if missing
                if inspector.has_table("client_checklist"):
                    try:
                        has_col = any(c['name'] == 'assigned_to_id' for c in inspector.get_columns("client_checklist"))
                        if not has_col:
                            print("📦 MIGRATION: Adding assigned_to_id to client_checklist...")
                            with db.engine.connect() as conn:
                                conn.execute(text("ALTER TABLE client_checklist ADD COLUMN assigned_to_id INTEGER REFERENCES \"user\"(id)"))
                                conn.commit()
                            print("✅ MIGRATION: assigned_to_id added to client_checklist.")
                    except Exception as cl_migration_e:
                        print(f"❌ MIGRATION ERROR on client_checklist: {cl_migration_e}")

                # MIGRATE: Add logo_base64 to company if missing
                if inspector.has_table("company"):
                    try:
                        has_col = any(c['name'] == 'logo_base64' for c in inspector.get_columns("company"))
                        if not has_col:
                            print("📦 MIGRATION: Adding logo_base64 to company...")
                            with db.engine.connect() as conn:
                                conn.execute(text("ALTER TABLE company ADD COLUMN logo_base64 TEXT"))
                                conn.commit()
                            print("✅ MIGRATION: logo_base64 added to company.")
                    except Exception as co_migration_e:
                        print(f"❌ MIGRATION ERROR on company: {co_migration_e}")

                # MIGRATE: Add Asaas Billing columns to company if missing
                if inspector.has_table("company"):
                    try:
                        billing_cols = [
                            ("plan_id", "VARCHAR(50)"),
                            ("asaas_customer_id", "VARCHAR(50)"),
                            ("payment_status", "VARCHAR(20) DEFAULT 'trial'"),
                            ("platform_inoperante", "BOOLEAN DEFAULT FALSE"),
                            ("overdue_since", "TIMESTAMP")
                        ]
                        existing_cols = [c['name'] for c in inspector.get_columns("company")]
                        
                        # for col_name, col_type in billing_cols:
                        #     if col_name not in existing_cols:
                        #         print(f"📦 MIGRATION: Adding {col_name} to company...")
                        #         with db.engine.connect() as conn:
                        #             # Use safe DDL
                        #             conn.execute(text(f"ALTER TABLE company ADD COLUMN {col_name} {col_type}"))
                        #             conn.commit()
                        #         print(f"✅ MIGRATION: {col_name} added to company.")
                        pass # Validating stability first
                        
                    except Exception as bill_migration_e:
                         print(f"❌ MIGRATION ERROR on Billing Columns: {bill_migration_e}")
                    
                    # MIGRATE: Add next_due_date (Date type) - REMOVED FOR STABILITY
                    # Will be handled via manual route

                # MIGRATE: Create BillingEvent table if missing

                # MIGRATE: Create BillingEvent table if missing
                if not inspector.has_table("billing_event"):
                    print("📦 MIGRATION: Creating BillingEvent table...")
                    try:
                        with db.engine.connect() as conn:
                            # Use cross-compatible SQL (works on PG and mostly SQLite)
                            conn.execute(text("""
                                CREATE TABLE billing_event (
                                    id SERIAL PRIMARY KEY,
                                    company_id INTEGER REFERENCES company(id),
                                    event_type VARCHAR(50) NOT NULL,
                                    payload JSON,
                                    processed_at TIMESTAMP,
                                    idempotency_key VARCHAR(100) UNIQUE,
                                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                            """))
                            conn.commit()
                        print("✅ MIGRATION: BillingEvent table created.")
                    except Exception as be_migration_e:
                        # Fallback for SQLite locally if SERIAL fails
                        if 'syntax error' in str(be_migration_e) and 'sqlite' in str(db.engine.url):
                             print("⚠️ SQLite fallback for BillingEvent...")
                             db.create_all() # Let SQLAlchemy handle it
                        else:
                             print(f"❌ MIGRATION ERROR on BillingEvent: {be_migration_e}")
                
            # Seed minimal data if empty (prevent lockout)
            if not User.query.first():
                print("🌱 Seeding default Admin...")
                # Create default company and user if needed
                from models import Company
                from werkzeug.security import generate_password_hash
                
                if not Company.query.first():
                    c = Company(name="NorthWay Default", plan="pro", status="active")
                    db.session.add(c)
                    db.session.commit()
                    
                    r = Role(name="Administrador", company_id=c.id, permissions=["admin_view"]) # Simplified
                    db.session.add(r)
                    db.session.commit()
                    
                    u = User(
                        name="Admin", 
                        email="admin@northway.com", 
                        password_hash=generate_password_hash("123456"),
                        company_id=c.id,
                        role="admin",
                        role_id=r.id
                    )
                    db.session.add(u)
                    db.session.commit()
                    print("✅ Default Admin created: admin@northway.com / 123456")
                # ...
                pass

    return app



app = create_app()

# --- TEMPORARY MIGRATION ROUTE ---
# Triggers the schema update and data migration when accessed.
# Security: Basic check or relying on admin login (if active) or just obscurity for this quick fix.
# Ideally would be a CLI command.
@app.route('/sys_admin/migrate_contacts_fix')
def sys_migrate_contacts():
    try:
        from update_schema_contact import update_schema
        from migrate_contacts import migrate_data
        
        # 1. Update Schema
        update_schema()
        
        # 2. Migrate Data
        migrate_data()
        
        return jsonify({"status": "success", "message": "Migration completed successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/checkout')
def checkout_fallback():
    return render_template('checkout_page.html')

# Health Check - Visible in Production
@app.route('/ping')
def ping(): return "pong"

if __name__ == '__main__':
    app.run(debug=True, port=5001)
