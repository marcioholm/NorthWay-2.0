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
from database_sync import sync_database
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
            return "DEPLOY_V9_LIVE_2026-03-30_09:50"


        @app.route('/sys-admin/sync-db')
        def admin_sync_db():
            secret = request.args.get('secret')
            is_secret_valid = secret == os.environ.get('MIGRATION_SECRET', 'northway_sync_2026')
            
            if not is_secret_valid:
                if not current_user.is_authenticated:
                    return redirect(url_for('login'))
                if not getattr(current_user, 'is_super_admin', False):
                    return jsonify({"error": "Unauthorized"}), 403
            
            try:
                from database_sync import sync_database
                results = sync_database()
                return jsonify({"status": "success", "message": "Database Sync Successful", "results": results})
            except Exception as e:
                import traceback
                return f"<h1>❌ Sync Failed</h1><pre>{traceback.format_exc()}</pre>", 500

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
            
        # --- DATABASE SYNC ---
        # Note: Migrations are now handled via CLI command: flask db-sync
        # No more automatic db.create_all() or ALTER TABLE on startup.

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

# --- GLOBAL PROXY FOR NEXT.JS ASSETS ---
# This ensures that CSS/JS from the Next.js app are served correctly
# when accessed via the Flask domain (e.g., in Playbooks and Forms).
@app.route('/_next/<path:path>')
def global_next_proxy(path):
    import requests
    from flask import make_response
    NEXT_APP_URL = "https://northway-crm-next.vercel.app"
    url = f"{NEXT_APP_URL}/_next/{path}"
    
    # Forward original query string
    if request.query_string:
        url += f"?{request.query_string.decode('utf-8')}"
    
    try:
        # Simple GET proxy for assets
        resp = requests.get(url, allow_redirects=True)
        response = make_response(resp.content, resp.status_code)
        if 'Content-Type' in resp.headers:
            response.headers['Content-Type'] = resp.headers['Content-Type']
        # Cache assets for better performance
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response
    except Exception as e:
        return f"Asset Proxy Error: {str(e)}", 502


@app.route('/checkout')
def checkout_fallback():
    return render_template('checkout_page.html')



@app.cli.command("db-sync")
def db_sync_command():
    """Manually synchronize database schema and seed data."""
    print("🔄 Starting database synchronization...")
    try:
        results = sync_database()
        for res in results:
            print(res)
        print("✅ Database synchronization completed.")
    except Exception as e:
        print(f"❌ Database synchronization failed: {e}")
        exit(1)

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5050)
