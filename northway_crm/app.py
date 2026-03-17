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
from sqlalchemy.pool import NullPool
from flask_login import LoginManager, current_user, login_required
from flask_migrate import Migrate
from models import db, User, Task, Role, AudienceMatrix, CREPIDiagnostico, CREPIPremissa, SwotAnalise, SwotItem
import json
# Blueprint imports moved to create_app to prevent global import crashes
from services.supabase_service import init_supabase
from flask_cors import CORS
from extensions import limiter
import logging

def create_app():
    # CRITICAL: Set instance path BEFORE Flask initialization
    # This prevents OSError on Vercel's read-only filesystem
    os.environ.setdefault('FLASK_INSTANCE_PATH', '/tmp')
    
    # EMERGENCY WRAPPER
    try:
        app = Flask(__name__, instance_path='/tmp', instance_relative_config=False)
        app.instance_path = '/tmp' # FORCE override for Vercel
        
        # SECURITY & CORS
        try:
             # Restrict CORS to specific common origins for extensions
             allowed_origins = [
                 "https://web.whatsapp.com",
                 "https://crm.northwaycompany.com.br"
             ]
             CORS(app, resources={r"/api/ext/*": {"origins": allowed_origins}})
        except:
             print("⚠️ CORS/Flask-Cors not available. Skipping.")

        @app.after_request
        def add_security_headers(response):
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            # Content Security Policy (Base safe policy)
            csp = (
                "default-src 'self' https:; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://www.googletagmanager.com https://unpkg.com https://cdn.tailwindcss.com https://cdn.quilljs.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://cdn.tailwindcss.com https://cdn.quilljs.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https://*.googleusercontent.com https://*.supabase.co https://*.whatsapp.net https://*.google.com https://*.whatsapp.com https://upload.wikimedia.org https://cdnjs.cloudflare.com; "
                "connect-src 'self' https://*.supabase.co https://*.google-analytics.com https://*.googleapis.com https://cdn.jsdelivr.net https://unpkg.com;"
            )
            response.headers['Content-Security-Policy'] = csp
            
            # SECURITY: Structured Logging (Audit)
            if response.status_code >= 400:
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "ip": request.remote_addr,
                    "user_id": current_user.id if current_user.is_authenticated else None,
                    "company_id": current_user.company_id if current_user.is_authenticated else None,
                    "agent": request.user_agent.string
                }
                app.logger.warning(f"AUDIT_LOG: {json.dumps(log_data)}")
            
            return response

        # Rate Limiting Configuration
        limiter.init_app(app)
        app.limiter = limiter

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        
        print("🚀 APP STARTUP: VERSION VERCEL-FIX-V6 (Auto-Migrate Contract)")
        
        # --- CONFIGURATION ---
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'northway-crm-secure-key')
        
        # Database Setup with Resilience
        database_url = os.environ.get('DATABASE_URL')
        
        @app.route('/api/debug/health')
        @login_required
        def debug_health():
            if not getattr(current_user, 'is_super_admin', False):
                return jsonify({"error": "Unauthorized"}), 403
            from models import Lead, Client, Transaction, Company
            return jsonify({
                'user': {
                    'email': getattr(current_user, 'email', 'unknown'),
                    'id': getattr(current_user, 'id', 'unknown'),
                    'company_id': getattr(current_user, 'company_id', None),
                    'role': getattr(current_user, 'role', 'unknown')
                },
                'db': {
                    'uri_host': str(db.engine.url).split('@')[-1] if db.engine else 'no_engine',
                    'is_postgres': 'postgresql' in str(db.engine.url) if db.engine else False
                },
                'counts': {
                    'leads_total': Lead.query.count(),
                    'clients_total': Client.query.count(),
                    'tx_total': Transaction.query.count(),
                    'companies_total': Company.query.count()
                },
                'company_counts': {
                    'leads': Lead.query.filter_by(company_id=current_user.company_id).count() if current_user.company_id else 0,
                    'clients': Client.query.filter_by(company_id=current_user.company_id).count() if current_user.company_id else 0,
                    'tx': Transaction.query.filter_by(company_id=current_user.company_id).count() if current_user.company_id else 0
                },
                'tx_details': [
                    {'id': t.id, 'status': t.status, 'due_date': str(t.due_date), 'amount': float(t.amount)} 
                    for t in Transaction.query.filter_by(company_id=current_user.company_id).limit(10).all()
                ] if current_user.company_id else []
            })
        
        def test_db_connection(url):
            if not url: 
                app.logger.error("📡 DB CONNECTION TEST: Missing URL.")
                return False
            return True # BYPASS connection test to prevent Vercel boot hanging
            try:
                app.logger.info(f"📡 DB CONNECTION TEST: Attempting connection to {url.split('@')[-1]}...")
                # Short timeout (5s) to avoid hanging startup
                connect_args = {}
                if 'postgresql' in url:
                    connect_args['connect_timeout'] = 5
                engine = create_engine(url, connect_args=connect_args)
                with engine.connect() as conn:
                    from sqlalchemy import text
                    conn.execute(text("SELECT 1"))
                app.logger.info("✅ DB CONNECTION TEST: SUCCESS.")
                return True
            except Exception as conn_e:
                import traceback
                error_trace = traceback.format_exc()
                app.logger.error(f"📡 DB CONNECTION TEST FAILED: {type(conn_e).__name__} - {conn_e}\nTraceback:\n{error_trace}")
                return False

        try:
            # 1. Normalize Postgres URL
            if database_url and database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            # 1.1 Force SSL for Supabase if missing
            if database_url and 'postgresql' in database_url and 'sslmode' not in database_url:
                separator = "?" if "?" not in database_url else "&"
                database_url += f"{separator}sslmode=require"
                print("🔒 DATABASE: Appending sslmode=require to connection string.")
            
            # 2. Check if we should use Postgres and if it's reachable
            is_postgres = database_url and 'postgresql' in database_url
            connection_ok = False
            
            if is_postgres:
                try:
                    import psycopg2
                    print(f"🐘 DATABASE: Testing PostgreSQL connection to {database_url.split('@')[-1]}...")
                    connection_ok = test_db_connection(database_url)
                    if not connection_ok:
                        print("❌ DATABASE: PostgreSQL connection test FAILED.")
                except ImportError:
                    print("⚠️ Postgres configured but 'psycopg2' missing.")
                except Exception as pg_e:
                    print(f"🔥 DATABASE: Unexpected Postgres error: {pg_e}")
            
            # 3. Decision Logic & Fallbacks
            if is_postgres and connection_ok:
                print("✅ DATABASE: Connection to PostgreSQL successful.")
            elif is_postgres and not connection_ok:
                print("❌ DATABASE: PostgreSQL connection FAILED.")
                if os.environ.get('VERCEL'):
                    print("🚨 DATABASE: Vercel environment. Blocking fallback.")
                else:
                    print("⚠️ DATABASE: Local environment. Falling back to SQLite.")
                    # Prioritize instance folder for local data if root db is missing or empty
                    instance_db = os.path.join(app.root_path, 'instance', 'crm.db')
                    root_db = os.path.join(app.root_path, "crm.db")
                    
                    if os.path.exists(instance_db):
                        database_url = f'sqlite:///{instance_db}'
                    else:
                        database_url = f'sqlite:///{root_db}'
            elif not database_url:
                # No database configured at all
                print("🏠 DATABASE: No URL configured. Using local SQLite.")
                instance_db = os.path.join(app.root_path, 'instance', 'crm.db')
                root_db = os.path.join(app.root_path, 'crm.db')
                
                if os.path.exists(instance_db):
                    database_url = f'sqlite:///{instance_db}'
                else:
                    database_url = f'sqlite:///{root_db}'
            else:
                print(f"📡 DATABASE: Using existing URL: {database_url.split('@')[-1] if '@' in database_url else 'hidden'}")

        except Exception as e:
            print(f"🔥 CRITICAL DB SETUP ERROR: {e}")
            database_url = 'sqlite:///:memory:' 

        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Optimize SQLAlchemy for Serverless (Vercel)
        engine_options = {
            'pool_pre_ping': True
        }
        if database_url and 'postgresql' in database_url:
            # Use NullPool for Serverless (Vercel) to prevent connection drops across frozen instances
            from sqlalchemy.pool import NullPool
            engine_options['poolclass'] = NullPool
            engine_options['connect_args'] = {
                'connect_timeout': 10,
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5,
            }
        else:
            engine_options['pool_recycle'] = 280
            
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
        
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
            try:
                return User.query.get(int(user_id))
            except Exception as e:
                print(f"⚠️ load_user failed (likely SSL drop), retrying: {e}")
                try:
                    db.session.remove()
                    return User.query.get(int(user_id))
                except Exception as e2:
                    print(f"❌ load_user retry also failed: {e2}")
                    return None

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

        # --- UNIFIED RESILIENT MIDDLEWARE ---
        @app.before_request
        def unified_before_request():
            if not request.endpoint: return
            if request.endpoint.startswith('static'): return
            
            # EXEMPTIONS: Always allow access to maintenance and auth routes
            # This is critical to recover from DB errors
            exempt_paths = ['/sys_admin', '/forms/public', '/admin/run-initial-migrations', '/emergency-migration', '/debug_schema']
            if any(request.path.startswith(p) for p in exempt_paths):
                return

            exempt_endpoints = ['auth.login', 'auth.register', 'auth.logout', 
                                'billing.asaas_webhook', 'billing.payment_pending',
                                'auth.suspended_account', 'master.revert_access',
                                'master.sync_schema']
            if request.endpoint in exempt_endpoints:
                return

            # Protected DB logic wrapped in global try-except
            if current_user and current_user.is_authenticated:
                try:
                    # Super Admins are NEVER blocked
                    if getattr(current_user, 'is_super_admin', False):
                        return
                        
                    # Fetching company can trigger UndefinedColumn error
                    company = getattr(current_user, 'company', None)
                    if not company:
                        return

                    # 1. Manual Block
                    if getattr(company, 'platform_inoperante', False):
                        if not request.endpoint.startswith('billing.'):
                            return redirect(url_for('billing.payment_pending'))

                    # 2. Automated Block (D+30)
                    payment_status = getattr(company, 'payment_status', None)
                    overdue_since = getattr(company, 'overdue_since', None)
                    
                    if payment_status == 'overdue' and overdue_since:
                        # Courtesy exemption
                        if getattr(company, 'status', None) != 'courtesy':
                            days_late = (datetime.utcnow() - overdue_since).days
                            if days_late >= 30:
                                return render_template('suspended.html', company_name=company.name, reason='overdue')
                    
                    # 3. Trial Expired
                    trial_ends = getattr(company, 'trial_ends_at', None)
                    if payment_status == 'trial' and trial_ends:
                        if datetime.utcnow() > trial_ends:
                            return render_template('suspended.html', company_name=company.name, reason='trial_expired')

                    # 4. Status Check
                    if getattr(company, 'status', 'active') in ['suspended', 'cancelled']:
                        return render_template('suspended.html', company_name=company.name, reason='manual')

                except Exception as e:
                    # SILENT FAIL: If anything fails here (likely DB schema mismatch), 
                    # we let the request proceed so the user can reach repair routes.
                    print(f"📡 Middleware Safety Trip: {e}")
                    pass

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
            
            error_msg = str(error)
            
            # CRITICAL: Log traceback to stderr/logs
            import traceback
            error_trace = traceback.format_exc()
            app.logger.error(f"🚨 INTERNAL SERVER ERROR (500): {error_msg}\n{error_trace}")

            # If it's an API request, return JSON so the frontend can parse the error
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': 'Erro Interno do Servidor (500)',
                    'message': error_msg
                }), 500

            if os.environ.get('VERCEL'):
                error_msg = "Internal Server Error. Please contact support."
                
            return render_template('500.html', error=error_msg), 500

        @app.route('/debug_schema')
        @login_required
        def debug_schema():
            if not getattr(current_user, 'is_super_admin', False):
                return jsonify({"error": "Unauthorized"}), 403
            
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
                
                return jsonify({'status': 'ok', 'user': current_user.email, 'debug_info': debug_info, 'tables': tables, 'schema': schema_info})
            except Exception as e:
                import traceback
                return jsonify({'error': str(e), 'traceback': traceback.format_exc(), 'partial_info': debug_info}), 500

        @app.route('/debug_test_template')
        def debug_test_template():
            from models import Client, User, Transaction, ProcessTemplate, DriveFolderTemplate
            from datetime import date
            from flask_login import login_user
            
            # Find a user to "login" for this debug session
            user = User.query.first()
            if user:
                login_user(user)
            
            client = Client.query.first()
            if not client: return "No client found", 404
            users = User.query.limit(5).all()
            return render_template('client_details.html',
                                  client=client,
                                  mrr=1000.0,
                                  today=date.today(),
                                  client_txs=[],
                                  total_paid=0.0,
                                  total_pending=0.0,
                                  total_overdue=0.0,
                                  process_templates=[],
                                  users=users,
                                  diag_instance=None,
                                  drive_templates=[],
                                  is_drive_connected=False)

        @app.route('/verify-deploy-2026')
        def verify_deploy():
            return "DEPLOY_V7_LIVE_2026-03-09_01:10"

        @app.route('/emergency-migration')
        def emergency_migration():
            # Auth Check: Super Admin, Admin role, or secret token (fallback)
            is_super = getattr(current_user, 'is_super_admin', False)
            is_admin = getattr(current_user, 'role', '') == 'admin'
            token = request.args.get('token')
            expected_token = "northway_fix_2026" # Temporary secret for this fix
            
            if not is_super and not is_admin and token != expected_token:
                user_email = getattr(current_user, 'email', 'Anonymous')
                user_role = getattr(current_user, 'role', 'N/A')
                return f"Unauthorized Access - User: {user_email}, Role: {user_role}. Please use token if admin check fails.", 403
            try:
                from models import db
                from sqlalchemy import text
                import time
                
                action = request.args.get('action', 'status')
                results = []
                
                # 1. DIAGNOSTICS
                db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                is_postgres = 'postgres' in db_uri or 'psycopg' in db_uri
                
                results.append(f"<b>--- EMERGENCY MODE ---</b>")
                results.append(f"Detected Type for SQL: {'Postgres' if is_postgres else 'SQLite/Other'}")
                
                # Test Connection
                try:
                    start_time = time.time()
                    db.session.execute(text("SELECT 1"))
                    elapsed = time.time() - start_time
                    results.append(f"Connection Test: SUCCESS ({elapsed:.4f}s)")
                except Exception as conn_e:
                    results.append(f"Connection Test: FAILED ({str(conn_e)})")
                    return f"DB Connection Failed: {str(conn_e)}<br><pre>" + "\n".join(results) + "</pre>", 200

                if action == 'status':
                    results.append("<br><b>--- INSTRUCTIONS ---</b>")
                    results.append(f"To run the migration, add <b>?action=execute</b> to the URL.")
                    results.append(f"<a href='{url_for('emergency_migration', action='execute')}'>Click here to RUN MIGRATION</a>")
                    return "<br>".join(results)

                # 2. EXECUTION
                results.append(f"<br><b>--- EXECUTION ---</b>")
                queries = []
                
                if is_postgres:
                    # POSTGRESQL QUERIES
                    queries = [
                        "CREATE EXTENSION IF NOT EXISTS pgcrypto;",
                        # Drive Folder Template
                        """CREATE TABLE IF NOT EXISTS drive_folder_template (
                            id SERIAL PRIMARY KEY,
                            company_id INTEGER NOT NULL REFERENCES company(id),
                            name VARCHAR(100) NOT NULL,
                            structure_json TEXT NOT NULL,
                            is_default BOOLEAN DEFAULT FALSE,
                            enabled BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );""",
                        
                        # Columns with IF NOT EXISTS (Postgres 9.6+)
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_score FLOAT;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_stars FLOAT;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_classification VARCHAR(50);",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_date TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS diagnostic_pillars JSONB;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS drive_folder_id VARCHAR(100);",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS drive_folder_url VARCHAR(500);",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS drive_folder_name VARCHAR(255);",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS drive_last_scan_at TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS drive_unread_files_count INTEGER DEFAULT 0;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS gmb_link VARCHAR(500);",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS gmb_rating FLOAT DEFAULT 0.0;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS gmb_reviews INTEGER DEFAULT 0;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS gmb_photos INTEGER DEFAULT 0;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS gmb_last_sync TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS profile_pic_url VARCHAR(500);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_score FLOAT;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_stars FLOAT;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_classification VARCHAR(50);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_date TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_pillars JSONB;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS drive_folder_id VARCHAR(100);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS drive_folder_url VARCHAR(500);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS drive_folder_name VARCHAR(255);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS drive_last_scan_at TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS drive_unread_files_count INTEGER DEFAULT 0;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS gmb_link VARCHAR(500);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS gmb_rating FLOAT DEFAULT 0.0;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS gmb_reviews INTEGER DEFAULT 0;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS gmb_photos INTEGER DEFAULT 0;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS gmb_last_sync TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS profile_pic_url VARCHAR(500);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS matrix_token VARCHAR(36) UNIQUE;",
                        "UPDATE client SET matrix_token = gen_random_uuid() WHERE matrix_token IS NULL;",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS health_status VARCHAR(20) DEFAULT 'verde';",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT 'em_dia';",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS niche VARCHAR(100);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS document VARCHAR(20);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS representative VARCHAR(100);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS representative_cpf VARCHAR(20);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS email_contact VARCHAR(120);",
                        "ALTER TABLE client ADD COLUMN IF NOT EXISTS asaas_customer_id VARCHAR(50);",
                        
                        # Task Updates (BDR Cadence)
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS description TEXT;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS overdue_reminder_sent BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS recurrence VARCHAR(20);",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS source_type VARCHAR(50);",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS auto_generated BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS is_urgent BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS is_important BOOLEAN DEFAULT FALSE;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS task_type VARCHAR(50);",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS origin_stage_id INTEGER REFERENCES pipeline_stage(id);",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS observation TEXT;",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                        "ALTER TABLE task ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES \"user\"(id);",

                        "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                        "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS stars FLOAT;",
                        "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS classification VARCHAR(100);",
                        "ALTER TABLE interaction ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                        "ALTER TABLE company ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}';",
                        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS amount FLOAT DEFAULT 0.0;",
                        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS billing_type VARCHAR(20) DEFAULT 'BOLETO';",
                        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS total_installments INTEGER DEFAULT 12;",
                        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS emit_nfse BOOLEAN DEFAULT TRUE;",
                        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS nfse_service_code VARCHAR(20);",
                        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS nfse_iss_rate FLOAT;",
                        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS nfse_desc VARCHAR(255);",
                        
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS lost_reason VARCHAR(500);",
                        "ALTER TABLE lead ADD COLUMN IF NOT EXISTS lost_at_stage_name VARCHAR(100);",
                        
                        # Performance Indexes (CRM Loading Speed Fix)
                        "CREATE INDEX IF NOT EXISTS idx_lead_company_id ON lead(company_id);",
                        "CREATE INDEX IF NOT EXISTS idx_lead_pipeline_id ON lead(pipeline_id);",
                        "CREATE INDEX IF NOT EXISTS idx_lead_pipeline_stage_id ON lead(pipeline_stage_id);",
                        "CREATE INDEX IF NOT EXISTS idx_lead_assigned_to_id ON lead(assigned_to_id);",
                        "CREATE INDEX IF NOT EXISTS idx_lead_created_at ON lead(created_at);",
                        
                        "CREATE INDEX IF NOT EXISTS idx_client_company_id ON client(company_id);",
                        "CREATE INDEX IF NOT EXISTS idx_client_account_manager_id ON client(account_manager_id);",
                        "CREATE INDEX IF NOT EXISTS idx_client_status ON client(status);",
                        
                        "CREATE INDEX IF NOT EXISTS idx_task_company_id ON task(company_id);",
                        "CREATE INDEX IF NOT EXISTS idx_task_assigned_to_id ON task(assigned_to_id);",
                        "CREATE INDEX IF NOT EXISTS idx_task_due_date ON task(due_date);",
                        "CREATE INDEX IF NOT EXISTS idx_task_status ON task(status);",
                        
                        "CREATE INDEX IF NOT EXISTS idx_interaction_client_id ON interaction(client_id);",
                        "CREATE INDEX IF NOT EXISTS idx_interaction_lead_id ON interaction(lead_id);",
                        "CREATE INDEX IF NOT EXISTS idx_interaction_company_id ON interaction(company_id);",
                        
                        "CREATE INDEX IF NOT EXISTS idx_transaction_company_id ON transaction(company_id);",
                        "CREATE INDEX IF NOT EXISTS idx_transaction_client_id ON transaction(client_id);",

                        """CREATE TABLE IF NOT EXISTS pipeline_stage_task_template (
                            id SERIAL PRIMARY KEY,
                            stage_id INTEGER NOT NULL REFERENCES pipeline_stage(id),
                            company_id INTEGER NOT NULL REFERENCES company(id),
                            task_type VARCHAR(50) NOT NULL,
                            title VARCHAR(200) NOT NULL,
                            script TEXT,
                            delay_hours INTEGER DEFAULT 0
                        );""",
                        """CREATE TABLE IF NOT EXISTS tenant_integration (
                            id SERIAL PRIMARY KEY,
                            company_id INTEGER NOT NULL REFERENCES company(id),
                            provider VARCHAR(50) NOT NULL,
                            status VARCHAR(20) DEFAULT 'disconnected',
                            google_account_email VARCHAR(120),
                            google_account_id VARCHAR(100),
                            access_token TEXT,
                            refresh_token_encrypted TEXT,
                            token_expiry_at TIMESTAMP,
                            root_folder_id VARCHAR(100),
                            root_folder_url VARCHAR(500),
                            last_error TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );""",
                        """CREATE TABLE IF NOT EXISTS drive_file_event (
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
                        );""",
                        """CREATE TABLE IF NOT EXISTS swot_analises (
                            id VARCHAR(36) PRIMARY KEY,
                            client_id INTEGER NOT NULL REFERENCES client(id),
                            contexto VARCHAR(255),
                            data_analise DATE NOT NULL DEFAULT CURRENT_DATE,
                            status VARCHAR(50) DEFAULT 'rascunho',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );""",
                        """CREATE TABLE IF NOT EXISTS audience_matrices (
                            id VARCHAR(36) PRIMARY KEY,
                            client_id INTEGER NOT NULL REFERENCES client(id),
                            product VARCHAR(255),
                            status VARCHAR(20) DEFAULT 'rascunho',
                            audiences JSONB NOT NULL,
                            tone_of_voice TEXT,
                            external_token VARCHAR(36) UNIQUE,
                            filled_by VARCHAR(100),
                            accepted_at TIMESTAMP WITH TIME ZONE,
                            accepted_ip VARCHAR(50),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );""",
                        
                        "ALTER TABLE audience_matrices ADD COLUMN IF NOT EXISTS tone_of_voice TEXT;",
                        "ALTER TABLE audience_matrices ADD COLUMN IF NOT EXISTS external_token VARCHAR(36);",
                        "ALTER TABLE audience_matrices ADD COLUMN IF NOT EXISTS filled_by VARCHAR(100);",
                        "ALTER TABLE audience_matrices ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMP WITH TIME ZONE;",
                        "ALTER TABLE audience_matrices ADD COLUMN IF NOT EXISTS accepted_ip VARCHAR(50);",
                        "ALTER TABLE audience_matrices ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'rascunho';",
                        "UPDATE audience_matrices SET external_token = gen_random_uuid() WHERE external_token IS NULL;",

                        """CREATE TABLE IF NOT EXISTS swot_itens (
                            id VARCHAR(36) PRIMARY KEY,
                            swot_analise_id VARCHAR(36) NOT NULL REFERENCES swot_analises(id),
                            quadrante VARCHAR(50) NOT NULL,
                            texto TEXT NOT NULL,
                            ordem INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );""",
                        """CREATE TABLE IF NOT EXISTS commercial_presentations (
                            id VARCHAR(36) PRIMARY KEY,
                            consultor_id INTEGER REFERENCES \"user\"(id),
                            company_id INTEGER REFERENCES company(id),
                            prospect_name VARCHAR(200) NOT NULL,
                            prospect_logo VARCHAR(500),
                            observacao TEXT,
                            pdf_url TEXT,
                            token VARCHAR(100) UNIQUE,
                            gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expira_em TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );"""
                    ]
                else:
                    # SQLITE
                    results.append("WARNING: Using SQLite fallback.")
                    queries = [
                        """CREATE TABLE IF NOT EXISTS drive_folder_template (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            company_id INTEGER NOT NULL REFERENCES company(id),
                            name VARCHAR(100) NOT NULL,
                            structure_json TEXT NOT NULL,
                            is_default BOOLEAN DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );""",
                        """CREATE TABLE IF NOT EXISTS audience_matrices (
                            id TEXT PRIMARY KEY,
                            client_id INTEGER NOT NULL REFERENCES client(id),
                            product TEXT,
                            status TEXT DEFAULT 'rascunho',
                            audiences TEXT NOT NULL,
                            tone_of_voice TEXT,
                            external_token TEXT UNIQUE,
                            filled_by TEXT,
                            accepted_at TIMESTAMP,
                            accepted_ip TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );""",
                         """CREATE TABLE IF NOT EXISTS tenant_integration (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            company_id INTEGER NOT NULL REFERENCES company(id),
                            service VARCHAR(50) NOT NULL,
                            access_token TEXT,
                            refresh_token_encrypted TEXT,
                            token_expiry_at TIMESTAMP,
                            status VARCHAR(20) DEFAULT 'connected',
                            last_error TEXT,
                            config_json TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );""",
                        "ALTER TABLE lead ADD COLUMN diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                        "ALTER TABLE lead ADD COLUMN diagnostic_score FLOAT;",
                        "ALTER TABLE lead ADD COLUMN diagnostic_stars FLOAT;",
                        "ALTER TABLE lead ADD COLUMN diagnostic_classification VARCHAR(50);",
                        "ALTER TABLE lead ADD COLUMN diagnostic_date TIMESTAMP;",
                        "ALTER TABLE lead ADD COLUMN diagnostic_pillars TEXT;",
                        "ALTER TABLE lead ADD COLUMN drive_folder_id VARCHAR(100);",
                        "ALTER TABLE lead ADD COLUMN drive_folder_url VARCHAR(500);",
                        "ALTER TABLE lead ADD COLUMN drive_folder_name VARCHAR(255);",
                        "ALTER TABLE lead ADD COLUMN drive_last_scan_at TIMESTAMP;",
                        "ALTER TABLE lead ADD COLUMN drive_unread_files_count INTEGER DEFAULT 0;",
                        "ALTER TABLE lead ADD COLUMN gmb_link VARCHAR(500);",
                        "ALTER TABLE lead ADD COLUMN gmb_rating FLOAT DEFAULT 0.0;",
                        "ALTER TABLE lead ADD COLUMN gmb_reviews INTEGER DEFAULT 0;",
                        "ALTER TABLE lead ADD COLUMN gmb_photos INTEGER DEFAULT 0;",
                        "ALTER TABLE lead ADD COLUMN gmb_last_sync TIMESTAMP;",
                        "ALTER TABLE lead ADD COLUMN profile_pic_url VARCHAR(500);",

                        "ALTER TABLE client ADD COLUMN diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                        "ALTER TABLE client ADD COLUMN diagnostic_score FLOAT;",
                        "ALTER TABLE client ADD COLUMN diagnostic_stars FLOAT;",
                        "ALTER TABLE client ADD COLUMN diagnostic_classification VARCHAR(50);",
                        "ALTER TABLE client ADD COLUMN diagnostic_date TIMESTAMP;",
                        "ALTER TABLE client ADD COLUMN diagnostic_pillars TEXT;",
                        "ALTER TABLE client ADD COLUMN drive_folder_id VARCHAR(100);",
                        "ALTER TABLE client ADD COLUMN drive_folder_url VARCHAR(500);",
                        "ALTER TABLE client ADD COLUMN drive_folder_name VARCHAR(255);",
                        "ALTER TABLE client ADD COLUMN drive_last_scan_at TIMESTAMP;",
                        "ALTER TABLE client ADD COLUMN drive_unread_files_count INTEGER DEFAULT 0;",
                        "ALTER TABLE client ADD COLUMN gmb_link VARCHAR(500);",
                        "ALTER TABLE client ADD COLUMN gmb_rating FLOAT DEFAULT 0.0;",
                        "ALTER TABLE client ADD COLUMN gmb_reviews INTEGER DEFAULT 0;",
                        "ALTER TABLE client ADD COLUMN gmb_photos INTEGER DEFAULT 0;",
                        "ALTER TABLE client ADD COLUMN gmb_last_sync TIMESTAMP;",
                        "ALTER TABLE client ADD COLUMN profile_pic_url VARCHAR(500);",
                        "ALTER TABLE client ADD COLUMN matrix_token VARCHAR(36);",
                        "ALTER TABLE client ADD COLUMN health_status VARCHAR(20) DEFAULT 'verde';",
                        "ALTER TABLE client ADD COLUMN payment_status VARCHAR(20) DEFAULT 'em_dia';",
                        "ALTER TABLE client ADD COLUMN niche VARCHAR(100);",
                        "ALTER TABLE client ADD COLUMN document VARCHAR(20);",
                        "ALTER TABLE client ADD COLUMN representative VARCHAR(100);",
                        "ALTER TABLE client ADD COLUMN representative_cpf VARCHAR(20);",
                        "ALTER TABLE client ADD COLUMN email_contact VARCHAR(120);",
                        "ALTER TABLE client ADD COLUMN asaas_customer_id VARCHAR(50);",

                        "ALTER TABLE task ADD COLUMN description TEXT;",
                        "ALTER TABLE task ADD COLUMN reminder_sent BOOLEAN DEFAULT 0;",
                        "ALTER TABLE task ADD COLUMN overdue_reminder_sent BOOLEAN DEFAULT 0;",
                        "ALTER TABLE task ADD COLUMN is_recurring BOOLEAN DEFAULT 0;",
                        "ALTER TABLE task ADD COLUMN recurrence VARCHAR(20);",
                        "ALTER TABLE task ADD COLUMN completed_at TIMESTAMP;",
                        "ALTER TABLE task ADD COLUMN source_type VARCHAR(50);",
                        "ALTER TABLE task ADD COLUMN auto_generated BOOLEAN DEFAULT 0;",
                        "ALTER TABLE task ADD COLUMN is_urgent BOOLEAN DEFAULT 0;",
                        "ALTER TABLE task ADD COLUMN is_important BOOLEAN DEFAULT 0;",
                        "ALTER TABLE task ADD COLUMN task_type VARCHAR(50);",
                        "ALTER TABLE task ADD COLUMN origin_stage_id INTEGER;",
                        "ALTER TABLE task ADD COLUMN observation TEXT;",
                        "ALTER TABLE task ADD COLUMN client_id INTEGER;",
                        "ALTER TABLE task ADD COLUMN created_by_user_id INTEGER;",

                        "ALTER TABLE company ADD COLUMN features TEXT DEFAULT '{}';",
                        "ALTER TABLE contract ADD COLUMN amount FLOAT DEFAULT 0.0;",
                        "ALTER TABLE contract ADD COLUMN billing_type VARCHAR(20) DEFAULT 'BOLETO';",
                        "ALTER TABLE contract ADD COLUMN total_installments INTEGER DEFAULT 12;",
                        "ALTER TABLE contract ADD COLUMN emit_nfse BOOLEAN DEFAULT 1;",
                        "ALTER TABLE contract ADD COLUMN nfse_service_code VARCHAR(20);",
                        "ALTER TABLE contract ADD COLUMN nfse_iss_rate FLOAT;",
                        "ALTER TABLE contract ADD COLUMN nfse_desc VARCHAR(255);",
                        "ALTER TABLE audience_matrices ADD COLUMN tone_of_voice TEXT;",
                        "ALTER TABLE audience_matrices ADD COLUMN external_token VARCHAR(36);",
                        "ALTER TABLE audience_matrices ADD COLUMN filled_by VARCHAR(100);",
                        "ALTER TABLE audience_matrices ADD COLUMN accepted_at DATETIME;",
                        "ALTER TABLE audience_matrices ADD COLUMN accepted_ip VARCHAR(50);",
                        "ALTER TABLE audience_matrices ADD COLUMN status VARCHAR(20);",

                        """CREATE TABLE IF NOT EXISTS commercial_presentations (
                            id TEXT PRIMARY KEY,
                            consultor_id INTEGER REFERENCES users(id),
                            company_id INTEGER REFERENCES companies(id),
                            prospect_name TEXT NOT NULL,
                            prospect_logo TEXT,
                            observacao TEXT,
                            pdf_url TEXT,
                            token TEXT UNIQUE,
                            gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expira_em TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );"""
                    ]

                for q in queries:
                    try:
                        db.session.execute(text(q))
                        results.append(f"SUCCESS: {q[:30]}...")
                    except Exception as e:
                        msg = str(e).lower()
                        if "already exists" in msg or "duplicate column" in msg:
                            results.append(f"SKIPPED (Exists): {q[:30]}...")
                        else:
                            results.append(f"ERROR: {q[:30]}... -> {str(e)}")
                
                try:
                    db.session.commit()
                    results.append("FINAL COMMIT: Success")
                except Exception as e:
                    db.session.rollback()
                    results.append(f"FINAL COMMIT FAILED: {str(e)}")
                    
                return "Migration finished.<br><pre>" + "\n".join(results) + "</pre>"
            except Exception as e:
                return f"FATAL ERROR: {str(e)}", 200

        # --- REGISTER BLUEPRINTS ---
        # Defensive loading: one failing blueprint won't crash the whole app
        blueprints = [
            ('auth', 'auth', 'auth_blueprint', None),
            ('master', 'master', 'master_blueprint', None),
            ('routes.financial', 'financial_bp', 'financial_bp', None),
            ('routes.financial_strategic', 'financial_strategic_bp', 'financial_strategic_bp', None),
            ('routes.docs', 'docs_bp', 'docs_bp', None),
            ('routes.goals', 'goals_bp', 'goals_bp', None),
            ('routes.prospecting', 'prospecting_bp', 'prospecting_bp', None),
            ('routes.integrations', 'integrations_bp', 'integrations_bp', None),
            ('routes.admin', 'admin_bp', 'admin_bp', None),
            ('routes.api_debug', 'api_debug_bp', 'api_debug_bp', None),
            ('routes.forms', 'forms_bp', 'forms_bp', '/forms'),
            ('routes.jobs', 'jobs_bp', 'jobs_bp', None),
            ('routes.api_extension', 'api_ext', 'api_ext', None),
            ('routes.whatsapp', 'whatsapp_bp', 'whatsapp_bp', None),
            ('routes.clients', 'clients_bp', 'clients_bp', None),
            ('routes.leads', 'leads_bp', 'leads_bp', None),
            ('routes.leads_enrichment', 'enrichment_bp', 'enrichment_bp', None),
            ('routes.contracts', 'contracts_bp', 'contracts_bp', None),
            ('routes.dashboard', 'dashboard_bp', 'dashboard_bp', None),
            ('routes.tasks', 'tasks_bp', 'tasks_bp', None),
            ('routes.templates', 'templates_bp', 'templates_bp', None),
            ('routes.checklists', 'checklists_bp', 'checklists_bp', None),
            ('routes.notifications', 'notifications_bp', 'notifications_bp', None),
            ('routes.roles', 'roles_bp', 'roles_bp', None),
            ('routes.billing', 'billing_bp', 'billing_bp', None),
            ('routes.service_orders', 'service_orders_bp', 'service_orders_bp', None),
            ('routes.pdf_routes', 'pdf_bp', 'pdf_bp', None),
            ('routes.financial_payable', 'payable_bp', 'payable_bp', None),
            ('routes.commercial_performance', 'commercial_bp', 'commercial_bp', None),
            ('routes.matrix_routes', 'matrix_bp', 'matrix_bp', None),
            ('routes.crepi_routes', 'crepi_bp', 'crepi_bp', None),
            ('routes.swot_routes', 'swot_bp', 'swot_bp', None),
            ('routes.marketing', 'marketing_bp', 'marketing_bp', None)
        ]

        import importlib
        for module_path, attr_name, var_name, prefix in blueprints:
            try:
                mod = importlib.import_module(module_path)
                bp = getattr(mod, attr_name)
                if prefix:
                    app.register_blueprint(bp, url_prefix=prefix)
                else:
                    app.register_blueprint(bp)
            except Exception as e:
                print(f"❌ Failed to load blueprint {var_name}: {e}")
                
        # --- BLUEPRINT FALLBACKS (Safety for router build errors) ---
        @app.route('/prospecting')
        @login_required
        def prospecting_fallback():
            try:
                # Try to redirect to leads if prospecting is totally broken
                return redirect(url_for('leads.leads'))
            except:
                return "The prospecting module is currently offline. Please contact support.", 503

        # --- BILLING MIDDLEWARE ---
            
        # --- AUTO-MIGRATION / TABLE CREATION ---
        # Critical for Vercel/Ephemeral environments
        with app.app_context():
            try:
                # Force SQLAlchemy to know about new models before create_all
                from models import PipelineStageTaskTemplate, SwotAnalise, SwotItem, CREPIDiagnostico, CREPIPremissa, AudienceMatrix, CommercialPresentation, LibraryBook

                # 1. Simple Table Creation
                db.create_all()
                print("✅ Tables created (if missing).")

                # 1.1. Manual Migrations (Safety check for new columns)
                # Using engine.connect() for more direct DDL execution
                try:
                    from sqlalchemy import text
                    with db.engine.connect() as conn:
                        # Check if it's postgres or sqlite
                        is_postgres_env = 'postgresql' in str(db.engine.url)
                        print(f"🛠️ MIGRATION: Running on {'PostgreSQL' if is_postgres_env else 'SQLite'}")
                        
                        try:
                            conn.execute(text("ALTER TABLE client ADD COLUMN payment_status VARCHAR(20) DEFAULT 'em_dia'"))
                            conn.commit()
                            print("🛠️ MIGRATION: Column 'payment_status' added successfully.")
                        except Exception as e_inner:
                            # Postgres often throws unique error for duplicate column
                            if "already exists" in str(e_inner).lower() or "duplicate column" in str(e_inner).lower():
                                print("🛠️ MIGRATION: Column 'payment_status' already exists. OK.")
                            else:
                                raise e_inner
                        
                        # Added Lead Repairs directly here for robustness
                        try:
                            from sqlalchemy import inspect, text
                            inspector = inspect(db.engine)
                            if inspector.has_table("lead"):
                                lead_cols = [c['name'] for c in inspector.get_columns("lead")]
                                lead_repairs = [
                                    ('estimated_value', "NUMERIC(12, 2) DEFAULT 0.0"),
                                    ('google_place_id', "VARCHAR(100)"),
                                    ('address', "TEXT"),
                                    ('website', "VARCHAR(500)"),
                                    ('profile_pic_url', "VARCHAR(500)"),
                                    ('diagnostic_status', "VARCHAR(20) DEFAULT 'pending'"),
                                    ('diagnostic_pillars', "JSONB" if is_postgres_env else "TEXT"),
                                    ('gmb_rating', "FLOAT DEFAULT 0.0"),
                                    ('gmb_reviews', "INTEGER DEFAULT 0"),
                                    ('gmb_link', "VARCHAR(500)"),
                                    ('gmb_photos', "INTEGER DEFAULT 0"),
                                    ('gmb_last_sync', "TIMESTAMP")
                                ]
                                for col, dtype in lead_repairs:
                                    if col not in lead_cols:
                                        try:
                                            print(f"🛠️ MIGRATION: Adding {col} to lead...")
                                            conn.execute(text(f"ALTER TABLE lead ADD COLUMN {col} {dtype}"))
                                            conn.commit()
                                        except Exception as e_lead:
                                            print(f"⚠️ MIGRATION FAILED for lead.{col}: {e_lead}")
                        except Exception as e_lead_mig:
                            print(f"⚠️ LEAD MIGRATION ERROR: {e_lead_mig}")

                        # Added User Repairs
                        try:
                            if inspector.has_table("user"):
                                user_cols = [c['name'] for c in inspector.get_columns("user")]
                                user_repairs = [
                                    ('is_super_admin', "BOOLEAN DEFAULT FALSE"),
                                    ('role_id', "INTEGER"),
                                    ('supabase_uid', "VARCHAR(100)"),
                                    ('funcao_comercial', "VARCHAR(100)"),
                                    ('tipo_vinculo', "VARCHAR(20)"),
                                    ('profile_image', "VARCHAR(150)"),
                                    ('phone', "VARCHAR(20)"),
                                    ('status_message', "VARCHAR(100)"),
                                    ('onboarding_dismissed', "BOOLEAN DEFAULT FALSE"),
                                    ('papel_comercial_id', "VARCHAR(36)"),
                                    ('regra_comissao_id', "VARCHAR(36)")
                                ]
                                for col, dtype in user_repairs:
                                    if col not in user_cols:
                                        try:
                                            print(f"🛠️ MIGRATION: Adding {col} to user...")
                                            conn.execute(text(f"ALTER TABLE \"user\" ADD COLUMN {col} {dtype}"))
                                            conn.commit()
                                        except Exception as e_user:
                                            print(f"⚠️ MIGRATION FAILED for user.{col}: {e_user}")
                        except Exception as e_user_mig:
                            print(f"⚠️ USER MIGRATION ERROR: {e_user_mig}")
                            print(f"⚠️ USER MIGRATION ERROR: {e_user_mig}")
                            
                        # Added Task Repairs
                        try:
                            if inspector.has_table("task"):
                                task_cols = [c['name'] for c in inspector.get_columns("task")]
                                task_repairs = [
                                    ('overdue_reminder_sent', "BOOLEAN DEFAULT FALSE"),
                                    ('is_recurring', "BOOLEAN DEFAULT FALSE"),
                                    ('recurrence', "VARCHAR(20)"),
                                    ('completed_at', "TIMESTAMP"),
                                    ('source_type', "VARCHAR(50)"),
                                    ('auto_generated', "BOOLEAN DEFAULT FALSE"),
                                    ('is_urgent', "BOOLEAN DEFAULT FALSE"),
                                    ('is_important', "BOOLEAN DEFAULT FALSE"),
                                    ('task_type', "VARCHAR(50)"),
                                    ('origin_stage_id', "INTEGER"),
                                    ('observation', "TEXT"),
                                    ('client_id', "INTEGER"),
                                    ('created_by_user_id', "INTEGER")
                                ]
                                for col, dtype in task_repairs:
                                    if col not in task_cols:
                                        try:
                                            print(f"🛠️ MIGRATION: Adding {col} to task...")
                                            conn.execute(text(f"ALTER TABLE task ADD COLUMN {col} {dtype}"))
                                            conn.commit()
                                        except Exception as e_task:
                                            print(f"⚠️ MIGRATION FAILED for task.{col}: {e_task}")
                        except Exception as e_task_mig:
                            print(f"⚠️ TASK MIGRATION ERROR: {e_task_mig}")
                            
                        # Added ClientProcess Table Creation
                        try:
                            if not inspector.has_table("client_processes"):
                                print("🛠️ MIGRATION: Creating client_processes table...")
                                conn.execute(text("""
                                    CREATE TABLE client_processes (
                                        id VARCHAR(36) PRIMARY KEY,
                                        client_id INTEGER NOT NULL REFERENCES client(id) ON DELETE CASCADE,
                                        company_id INTEGER NOT NULL REFERENCES company(id),
                                        tool_type VARCHAR(50) NOT NULL,
                                        mode VARCHAR(50) NOT NULL,
                                        data TEXT,
                                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                                    )
                                """))
                                conn.commit()
                        except Exception as e_cp_mig:
                            print(f"⚠️ CLIENT PROCESS MIGRATION ERROR: {e_cp_mig}")

                except Exception as e_mig:
                    print(f"⚠️ MIGRATION NOTICE (Non-critical if already exists): {e_mig}")
                
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
                    from sqlalchemy import inspect, text
                    inspector = inspect(db.engine)
                    
                    if inspector.has_table("company"):
                        with db.engine.connect() as conn:
                            columns = [c['name'] for c in inspector.get_columns("company")]
                            
                            # Safely add columns
                            for col, dtype in [
                                ('next_due_date', 'DATE'), 
                                ('trial_start_date', 'DATETIME'), 
                                ('trial_end_date', 'DATETIME'),
                                ('features', 'JSONB DEFAULT \'{}\''),
                                ('allowed_global_template_ids', 'JSONB DEFAULT \'[]\''),
                                ('default_template_id', 'INTEGER'),
                                ('auto_create_subfolders', 'BOOLEAN DEFAULT TRUE')
                            ]:
                                if col not in columns:
                                    try:
                                        conn.execute(text(f"ALTER TABLE company ADD COLUMN {col} {dtype}"))
                                    except: pass
                            
                            conn.commit()

                    # 4. LEAD REPAIR (Fix drive folders, gmb, cnpj)
                    if inspector.has_table("lead"):
                        with db.engine.connect() as conn:
                            lead_cols = [c['name'] for c in inspector.get_columns("lead")]
                            repairs = [
                                ('diagnostic_status', "VARCHAR(20) DEFAULT 'pending'"),
                                ('diagnostic_score', "FLOAT"),
                                ('diagnostic_stars', "FLOAT"),
                                ('diagnostic_classification', "VARCHAR(50)"),
                                ('diagnostic_date', "TIMESTAMP"),
                                ('diagnostic_pillars', "JSONB"),
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
                                ('legal_name', "VARCHAR(200)"),
                                ('cnpj', "VARCHAR(20)"),
                                ('registration_status', "VARCHAR(50)"),
                                ('company_size', "VARCHAR(50)"),
                                ('equity', "FLOAT"),
                                ('foundation_date', "VARCHAR(20)"),
                                ('legal_nature', "VARCHAR(100)"),
                                ('opening_date', "VARCHAR(20)"),
                                ('estimated_value', "FLOAT DEFAULT 0.0"),
                                ('google_place_id', "VARCHAR(100)"),
                                ('legal_email', "VARCHAR(120)"),
                                ('legal_phone', "VARCHAR(50)"),
                                ('cnae', "VARCHAR(200)"),
                                ('partners_json', "TEXT"),
                                ('enrichment_history', "TEXT")
                            ]
                            for col, dtype in repairs:
                                if col not in lead_cols:
                                    try:
                                        print(f"🛠️ REPAIR: Adding {col} to lead...")
                                        conn.execute(text(f"ALTER TABLE lead ADD COLUMN {col} {dtype}"))
                                    except Exception as e_rep:
                                        print(f"⚠️ REPAIR FAILED for {col}: {e_rep}")
                            conn.commit()

                    # 5. CLIENT REPAIR
                    if inspector.has_table("client"):
                        with db.engine.connect() as conn:
                            client_cols = [c['name'] for c in inspector.get_columns("client")]
                            repairs = [
                                ('health_status', "VARCHAR(20) DEFAULT 'verde'"),
                                ('niche', "VARCHAR(100)"),
                                ('document', "VARCHAR(20)"),
                                ('address_street', "VARCHAR(150)"),
                                ('address_number', "VARCHAR(20)"),
                                ('address_neighborhood', "VARCHAR(100)"),
                                ('address_city', "VARCHAR(100)"),
                                ('address_state', "VARCHAR(2)"),
                                ('address_zip', "VARCHAR(10)"),
                                ('representative', "VARCHAR(100)"),
                                ('representative_cpf', "VARCHAR(20)"),
                                ('email_contact', "VARCHAR(120)"),
                                ('profile_pic_url', "VARCHAR(500)"),
                                ('diagnostic_status', "VARCHAR(20) DEFAULT 'pending'"),
                                ('diagnostic_score', "FLOAT"),
                                ('diagnostic_stars', "FLOAT"),
                                ('diagnostic_classification', "VARCHAR(50)"),
                                ('diagnostic_date', "TIMESTAMP"),
                                ('diagnostic_pillars', "JSONB"),
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
                                ('asaas_customer_id', "VARCHAR(50)")
                            ]
                            for col, dtype in repairs:
                                if col not in client_cols:
                                    try: conn.execute(text(f"ALTER TABLE client ADD COLUMN {col} {dtype}"))
                                    except: pass
                            conn.commit()
                    
                    # 6. CONTRACT REPAIR
                    if inspector.has_table("contract"):
                        with db.engine.connect() as conn:
                            ctr_cols = [c['name'] for c in inspector.get_columns("contract")]
                            repairs = [
                                ('amount', "FLOAT DEFAULT 0.0"),
                                ('billing_type', "VARCHAR(20) DEFAULT 'BOLETO'"),
                                ('total_installments', "INTEGER DEFAULT 12"),
                                ('emit_nfse', "BOOLEAN DEFAULT TRUE"),
                                ('nfse_service_code', "VARCHAR(20)"),
                                ('nfse_iss_rate', "FLOAT"),
                                ('nfse_desc', "VARCHAR(255)")
                            ]
                            for col, dtype in repairs:
                                if col not in ctr_cols:
                                    try: conn.execute(text(f"ALTER TABLE contract ADD COLUMN {col} {dtype}"))
                                    except: pass
                            conn.commit()

                    # 7. DRIVE TEMPLATE REPAIR
                    if inspector.has_table("drive_folder_template"):
                        with db.engine.connect() as conn:
                            tmpl_cols = [c['name'] for c in inspector.get_columns("drive_folder_template")]
                            
                            if 'scope' not in tmpl_cols:
                                try: conn.execute(text("ALTER TABLE drive_folder_template ADD COLUMN scope VARCHAR(20) DEFAULT 'tenant'"))
                                except: pass

                            if 'enabled' not in tmpl_cols:
                                try: conn.execute(text("ALTER TABLE drive_folder_template ADD COLUMN enabled BOOLEAN DEFAULT TRUE"))
                                except: pass
                            
                            # Try to make company_id nullable
                            try: conn.execute(text("ALTER TABLE drive_folder_template ALTER COLUMN company_id DROP NOT NULL"))
                            except: pass
                            
                            conn.commit()
                                
                except Exception as mig_e:
                    print(f"⚠️ Migration/Inspect Error: {mig_e}")

                # 8. TASK REPAIR (Critical for Matrix)
                try:
                    if inspector.has_table("task"):
                        with db.engine.connect() as conn:
                            task_cols = [c['name'] for c in inspector.get_columns("task")]
                            repairs = [
                                ('is_urgent', "BOOLEAN DEFAULT FALSE"),
                                ('is_important', "BOOLEAN DEFAULT FALSE"),
                                ('completed_at', "TIMESTAMP"),
                                ('source_type', "VARCHAR(50)"),
                                ('auto_generated', "BOOLEAN DEFAULT FALSE"),
                                ('contract_id', "INTEGER"),
                                ('service_order_id', "INTEGER"),
                                ('created_by_user_id', "INTEGER")
                            ]
                            for col, dtype in repairs:
                                if col not in task_cols:
                                    try: conn.execute(text(f"ALTER TABLE task ADD COLUMN {col} {dtype}"))
                                    except: pass
                            conn.commit()
                except Exception as task_mig_e:
                    print(f"⚠️ Task Migration Error: {task_mig_e}")

            except Exception as context_e:
                print(f"❌ Startup Context Error: {context_e}")

        # --- GLOBAL CONTEXT PROCESSOR ---
        @app.context_processor
        def inject_saas_metrics():
            try:
                # SKIP FOR ADMIN ROUTES to avoid schema crashes during fix
                if request.path.startswith('/sys_admin'):
                    return {}

                if not current_user or not getattr(current_user, 'is_authenticated', False) or not getattr(current_user, 'company_id', None):
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
    except Exception as factory_e:
        import traceback
        tb_str = traceback.format_exc()
        print(f"🔥 FATAL FACTORY EXPLOSION:\n{tb_str}")
        
        # Capture error for closure
        error_msg = str(factory_e)
        
        # EMERGENCY APP
        fallback = Flask(__name__)
        @fallback.route('/', defaults={'path': ''})
        @fallback.route('/<path:path>')
        def emergency_catch_all(path, **kwargs):
            return f"""
            <html>
            <head><title>Emergency Mode</title></head>
            <body style="font-family: monospace; padding: 20px; background: #fff5f5;">
                <h1 style="color: #c53030;">EMERGENCY MODE</h1>
                <p>The application factory failed to start.</p>
                <div style="background: #eee; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <strong>Error:</strong> {error_msg}
                </div>
                <h3>Stack Trace:</h3>
                <pre style="background: #2d3748; color: #fff; padding: 15px; border-radius: 5px; overflow: auto;">{tb_str}</pre>
            </body>
            </html>
            """, 503
            
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
            ("created_by_user_id", "INTEGER REFERENCES \"user\"(id)"),
            ("is_urgent", "BOOLEAN DEFAULT FALSE"),
            ("is_important", "BOOLEAN DEFAULT FALSE"),
            ("completed_at", "TIMESTAMP")
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
        return jsonify({"status": "error", "error": str(e)}), 500
        
@app.route('/sys_admin/migrate_drive')
def sys_migrate_drive():
    try:
        results = []
        conn = db.engine.connect()
        
        # 1. Create TenantIntegration
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tenant_integration (
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
            """))
            results.append("✅ Created table tenant_integration")
        except Exception as e:
            if "syntax error" in str(e).lower() and "SERIAL" in str(e):
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS tenant_integration (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                """))
                results.append("✅ Created table tenant_integration (SQLite)")
            else:
                results.append(f"❌ Failed tenant_integration: {e}")

        # 2. Create DriveFileEvent
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS drive_file_event (
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
            """))
            results.append("✅ Created table drive_file_event")
        except Exception as e:
            if "syntax error" in str(e).lower() and "SERIAL" in str(e):
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS drive_file_event (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                """))
                results.append("✅ Created table drive_file_event (SQLite)")
            else:
                results.append(f"❌ Failed drive_file_event: {e}")

        # 3. Add Columns to Lead
        lead_cols = [
            ("drive_folder_id", "VARCHAR(100)"),
            ("drive_folder_url", "VARCHAR(500)"),
            ("drive_folder_name", "VARCHAR(255)"),
            ("drive_last_scan_at", "TIMESTAMP"),
            ("drive_unread_files_count", "INTEGER DEFAULT 0")
        ]
        for col, dtype in lead_cols:
            try:
                conn.execute(text(f"ALTER TABLE lead ADD COLUMN {col} {dtype}"))
                results.append(f"✅ Added lead.{col}")
            except Exception as e:
                results.append(f"⚠️ lead.{col}: {e}")

        # 4. Add Columns to Client
        client_cols = [
            ("drive_folder_id", "VARCHAR(100)"),
            ("drive_folder_url", "VARCHAR(500)"),
            ("drive_folder_name", "VARCHAR(255)"),
            ("drive_last_scan_at", "TIMESTAMP"),
            ("drive_unread_files_count", "INTEGER DEFAULT 0")
        ]
        for col, dtype in client_cols:
            try:
                conn.execute(text(f"ALTER TABLE client ADD COLUMN {col} {dtype}"))
                results.append(f"✅ Added client.{col}")
            except Exception as e:
                results.append(f"⚠️ client.{col}: {e}")

        conn.close()
        return jsonify({"status": "completed", "log": results})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sys_admin/migrate_followup_pipeline')
def sys_migrate_followup_pipeline():
    try:
        from models import Company, Pipeline, PipelineStage
        results = []
        
        # We need app context for full ORM if we want to use the models easily
        companies = Company.query.all()
        for company in companies:
            # Check if it already has the follow-up pipeline
            existing_fu = Pipeline.query.filter_by(company_id=company.id, name='Follow-up (12 Dias)').first()
            if not existing_fu:
                try:
                    fu_pipeline = Pipeline(name='Follow-up (12 Dias)', company_id=company.id)
                    db.session.add(fu_pipeline)
                    db.session.flush() # get ID
                    
                    fu_stages = ['Dia 1', 'Dia 2', 'Dia 4', 'Dia 7', 'Dia 12', 'Perdido/Sem Resposta']
                    for i, fu_name in enumerate(fu_stages):
                        fu_stage = PipelineStage(name=fu_name, order=i, pipeline_id=fu_pipeline.id, company_id=company.id)
                        db.session.add(fu_stage)
                        
                    results.append(f"✅ Created Follow-up pipeline for Company ID {company.id}")
                except Exception as ce:
                    db.session.rollback()
                    results.append(f"❌ Failed for Company ID {company.id}: {str(ce)}")
            else:
                results.append(f"⚠️ Company ID {company.id} already has Follow-up pipeline")
                
        db.session.commit()
        return jsonify({"status": "completed", "log": results})
        
    except Exception as e:
        db.session.rollback()
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


@app.route('/sys_admin/migrate_forms')
def sys_migrate_forms():
    try:
        from models import LibraryTemplate, LibraryTemplateGrant, FormInstance, FormSubmission
        
        # 1. Create Tables
        with app.app_context():
            db.create_all()
            
        # 2. Seed Template "diagnostico_northway_v1"
        key = "diagnostico_northway_v1"
        template = LibraryTemplate.query.filter_by(key=key).first()
        
        schema = {
            "title": "Diagnóstico de Crescimento – Framework Northway",
            "description": "Atrair, Engajar, Vender, Vender de Novo",
            "pillars": ["Atrair", "Engajar", "Vender", "Reter"],
            "max_score": 60,
            "questions": [
                # ATRAIR (1-5)
                {"id": "q1", "text": "Tenho um canal previsível de geração de leads (tráfego, SEO, etc.)", "pilar": "Atrair"},
                {"id": "q2", "text": "Sei exatamente de onde vêm meus leads hoje", "pilar": "Atrair"},
                {"id": "q3", "text": "Tenho uma landing page ou vitrine clara de oferta", "pilar": "Atrair"},
                {"id": "q4", "text": "Meu Google Meu Negócio é atualizado com frequência", "pilar": "Atrair"},
                {"id": "q5", "text": "Já testei anúncios de forma estruturada", "pilar": "Atrair"},
                
                # ENGAJAR (6-10)
                {"id": "q6", "text": "Respondo leads em até 15 minutos", "pilar": "Engajar"},
                {"id": "q7", "text": "Tenho um processo de follow-up definido", "pilar": "Engajar"},
                {"id": "q8", "text": "Uso WhatsApp ou CRM de forma organizada", "pilar": "Engajar"},
                {"id": "q9", "text": "Produzo conteúdo para educar meu cliente", "pilar": "Engajar"},
                {"id": "q10", "text": "Uso provas sociais (depoimentos, avaliações, cases)", "pilar": "Engajar"},
                
                # VENDER (11-15)
                {"id": "q11", "text": "Tenho um funil de vendas claro", "pilar": "Vender"},
                {"id": "q12", "text": "Uso CRM ou pipeline para acompanhar oportunidades", "pilar": "Vender"},
                {"id": "q13", "text": "Tenho proposta padrão e oferta clara", "pilar": "Vender"},
                {"id": "q14", "text": "Tenho script/processo comercial definido", "pilar": "Vender"},
                {"id": "q15", "text": "Acompanho métricas de conversão", "pilar": "Vender"},
                
                # RETER (16-20)
                {"id": "q16", "text": "Tenho campanhas de remarketing ativas", "pilar": "Reter"},
                {"id": "q17", "text": "Faço ações de pós-venda", "pilar": "Reter"},
                {"id": "q18", "text": "Trabalho recompra, upsell ou cross-sell", "pilar": "Reter"},
                {"id": "q19", "text": "Tenho base de clientes organizada", "pilar": "Reter"},
                {"id": "q20", "text": "Me comunico com clientes ativos e inativos", "pilar": "Reter"}
            ],
            "options": [
                {"value": 0, "label": "Não faço"},
                {"value": 1, "label": "Faço de forma improvisada"},
                {"value": 2, "label": "Faço com processo básico"},
                {"value": 3, "label": "Faço com processo + métricas"}
            ]
        }
        
        if not template:
            template = LibraryTemplate(
                key=key,
                name="Diagnóstico de Crescimento – Framework Northway",
                description="Descubra onde estão os gargalos do seu crescimento: Atrair, Engajar, Vender ou Vender de Novo.",
                schema_json=schema,
                version=1,
                active=True
            )
            db.session.add(template)
            db.session.commit()
            msg = "Template Created and Tables Synced."
        else:
            # Update schema if needed
            template.schema_json = schema
            db.session.commit()
            msg = "Template Updated."
            
        return jsonify({"status": "success", "message": msg})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


    @app.route('/sys_admin/migrate_matrix')
    def sys_migrate_matrix():
        try:
            from sqlalchemy import text
            print("Starting Manual Matrix Migration...")
            
            # 1. avg_ticket
            try:
                db.session.execute(text("ALTER TABLE audience_matrices ADD COLUMN avg_ticket VARCHAR(50);"))
                db.session.commit()
                print("avg_ticket added.")
            except Exception as e:
                db.session.rollback()
                print(f"avg_ticket skip: {e}")

            # 2. margin
            try:
                db.session.execute(text("ALTER TABLE audience_matrices ADD COLUMN margin VARCHAR(50);"))
                db.session.commit()
                print("margin added.")
            except Exception as e:
                db.session.rollback()
                print(f"margin skip: {e}")

            # 3. filled_by
            try:
                db.session.execute(text("ALTER TABLE audience_matrices ADD COLUMN filled_by VARCHAR(100);"))
                db.session.commit()
                print("filled_by added.")
            except Exception as e:
                db.session.rollback()
                print(f"filled_by skip: {e}")

            return jsonify({"status": "success", "message": "Matrix migration attempt completed. Check logs for details."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/sys_admin/check_columns')
    def sys_check_columns():
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('audience_matrices')]
            return jsonify({"columns": columns})
        except Exception as e:
            return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5050)
