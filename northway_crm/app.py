import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Blueprint
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from models import db, User, Task, Role
import json
from auth import auth as auth_blueprint
from master import master as master_blueprint
from routes.financial import financial_bp
from routes.docs import docs_bp
from routes.goals import goals_bp
from routes.prospecting import prospecting_bp
from routes.integrations import integrations_bp
from routes.admin import admin_bp
from routes.whatsapp import whatsapp_bp
from routes.clients import clients_bp
from routes.leads import leads_bp
from routes.contracts import contracts_bp
from routes.dashboard import dashboard_bp
from routes.tasks import tasks_bp
from routes.templates import templates_bp
from routes.checklists import checklists_bp
from routes.notifications import notifications_bp
from services.supabase_service import init_supabase

def create_app():
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # --- CONFIGURATION ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'northway-crm-secure-key')
    
    # Database
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    if not database_url:
        # Vercel Workaround: Copy SQLite to /tmp
        try:
            import shutil
            src_db = os.path.join(app.root_path, 'crm.db')
            tmp_db = '/tmp/crm.db'
            if os.path.exists(src_db):
                shutil.copy2(src_db, tmp_db)
                database_url = f'sqlite:///{tmp_db}'
            else:
                database_url = 'sqlite:///crm.db'
        except:
            database_url = 'sqlite:///crm.db'

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
    app.config['SUPABASE_URL'] = os.environ.get('SUPABASE_URL', 'https://bnumpvhsfujpprovajkt.supabase.co')
    app.config['SUPABASE_KEY'] = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJudW1wdmhzZnVqcHByb3Zhamt0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgzNjA5OTgsImV4cCI6MjA4MzkzNjk5OH0.pVcON2srZ2FXQ36Q-72WAHB-gVdrP_5Se-_K8XQ15Gs')
    app.config['SUPABASE_SERVICE_ROLE_KEY'] = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    app.supabase = init_supabase(app)

    # --- INITIALIZE EXTENSIONS ---
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- CONTEXT PROCESSORS ---
    @app.context_processor
    def inject_globals():
        try:
            if current_user.is_authenticated:
                try:
                    # Defensive check for table existence/schema issues
                    pending_count = Task.query.filter_by(assigned_to_id=current_user.id, status='pendente').count()
                    return dict(pending_tasks_count=pending_count, now=datetime.now())
                except Exception as db_e:
                    print(f"Database error in inject_globals: {db_e}")
                    return dict(pending_tasks_count=0, now=datetime.now())
        except Exception as e:
            # Log error but don't crash the page
            print(f"Critical error in inject_globals: {e}")
            return dict(pending_tasks_count=0, now=datetime.now())
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
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(master_blueprint)
    app.register_blueprint(financial_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(prospecting_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(contracts_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(checklists_bp)
    app.register_blueprint(notifications_bp)
    
    from routes.roles import roles_bp
    app.register_blueprint(roles_bp)

    return app

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

app = create_app()

if __name__ == '__main__':
    # Add a /ping route directly if not in any bp for debugging
    @app.route('/ping')
    def ping(): return "pong"
    
    app.run(debug=True, port=5001)
