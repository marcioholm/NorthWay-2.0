from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
# Defer model imports to avoid circular dependency with app initialization
# from models import db, User, Role, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
import time
import base64

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def check_admin_access():
    """
    Ensure only company Admins (or Super Admins) can access these routes.
    Strictly scoped to the user's own company.
    """
    # Allow Super Admin to use these restricted views if they really want, 
    # but primarily this is for ROLE_ADMIN.
    # Check if user has 'admin_view' permission OR has role='admin'
    # Allow access to the migration route to fix production 500 errors
    if request.endpoint == 'admin.run_initial_migrations':
        return

    if not current_user.has_permission('admin_view') and current_user.role.lower() != 'admin':
        abort(403)

@admin_bp.route('/admin/users')
def users():
    from models import User, Role, EMAIL_TEMPLATES # Lazy Import
    """
    List users ONLY for the current user's company.
    """
    users = User.query.filter_by(company_id=current_user.company_id).all()
    roles = Role.query.filter_by(company_id=current_user.company_id).all() 
    # Fallback to hardcoded if no DB roles yet, or just pass for now
    
    return render_template('admin/users.html', users=users)

@admin_bp.route('/admin/users/new', methods=['GET', 'POST'])
def new_user():
    from models import db, User # Lazy Import
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'vendedor') # Default value
        
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'error')
            return redirect(url_for('admin.new_user'))
            
        new_user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            company_id=current_user.company_id, # STRICTLY FORCE COMPANY ID
            role=role
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # --- INVITE FLOW START ---
        from models import PasswordResetToken, EMAIL_TEMPLATES
        from services.email_service import EmailService
        import secrets
        import hashlib
        from datetime import timedelta
        from utils import get_now_br
        
        # Generate generic Invite Token (reusing Password Reset logic)
        token_raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        
        reset_token = PasswordResetToken(
            user_id=new_user.id,
            token_hash=token_hash,
            expires_at=get_now_br() + timedelta(hours=48) # 48h for invite
        )
        db.session.add(reset_token)
        db.session.commit()
        
        invite_url = url_for('auth.reset_password', token=token_raw, _external=True)
        
        EmailService.send_email(
            to=new_user.email,
            subject=f"Convite para entrar na {current_user.company.name}",
            template=EMAIL_TEMPLATES.invite_user,
            context={'user': new_user, 'company': current_user.company, 'invite_url': invite_url},
            company_id=current_user.company_id,
            user_id=new_user.id
        )
        # --- INVITE FLOW END ---

        flash('Usuário criado e convite enviado por e-mail!', 'success')
        return redirect(url_for('admin.users'))
        
    return render_template('admin/user_form.html', user=None)

@admin_bp.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    from models import db, User # Lazy Import
    # CRITICAL: Verify user belongs to SAME company
    user = User.query.get_or_404(user_id)
    
    if user.company_id != current_user.company_id:
        abort(403) # Prevent accessing other company's users
        
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        
        password = request.form.get('password')
        if password:
             user.password_hash = generate_password_hash(password)
             
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('admin.users'))
        
    return render_template('admin/user_form.html', user=user)

@admin_bp.route('/settings/company', methods=['GET', 'POST'])
def company_settings():
    from models import db, Company
    company = Company.query.get(current_user.company_id)
    if not company:
        abort(404)
    
    if request.method == 'POST':
        company.name = request.form.get('name')
        company.document = request.form.get('document')
        company.address_street = request.form.get('address_street')
        company.address_number = request.form.get('address_number')
        company.address_neighborhood = request.form.get('address_neighborhood')
        company.address_city = request.form.get('address_city')
        company.address_state = request.form.get('address_state')
        company.address_zip = request.form.get('address_zip')
        company.representative = request.form.get('representative')
        company.representative_cpf = request.form.get('representative_cpf')
        
        # Branding
        company.primary_color = request.form.get('primary_color', '#fa0102')
        company.secondary_color = request.form.get('secondary_color', '#111827')
        
        # Logo Upload Logic
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                try:
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
                    unique_filename = f"logo_{company.id}_{int(time.time())}.{ext}"
                    
                    uploaded = False
                    # 1. Try Supabase Storage
                    if hasattr(current_app, 'supabase') and current_app.supabase:
                        try:
                            # Reset cursor ensures clean read
                            file.seek(0)
                            bucket = 'company-assets'
                            file_content = file.read()
                            path = f"logos/{unique_filename}"
                            current_app.supabase.storage.from_(bucket).upload(path, file_content, {"content-type": file.content_type})
                            public_url = current_app.supabase.storage.from_(bucket).get_public_url(path)
                            company.logo_filename = public_url
                            # Clear base64 if cloud upload works to save DB space (optional, but good practice)
                            company.logo_base64 = None 
                            uploaded = True
                            print(f"✅ Uploaded logo to Supabase: {public_url}")
                        except Exception as storage_e:
                            print(f"⚠️ Supabase Upload Failed: {storage_e}")
                            # Fallback continues below
                    
                    # 2. Fallback: Base64 Database Storage (Persistence Guarantee)
                    if not uploaded:
                        try:
                            print("💾 Falling back to Base64 Database Storage...")
                            file.seek(0) # Reset cursor again
                            file_data = file.read()
                            base64_str = base64.b64encode(file_data).decode('utf-8')
                            company.logo_base64 = base64_str
                            # Set filename to indicate base64 mode if needed, or keep for reference
                            # company.logo_filename = "base64" 
                            uploaded = True
                            print("✅ Logo saved as Base64 in Database.")
                        except Exception as b64_e:
                            print(f"❌ Base64 Conversion Failed: {b64_e}")
                            raise b64_e # Trigger outer except

                except Exception as e:
                    print(f"❌ Error uploading logo: {e}")
                    flash(f'Erro ao salvar logotipo: {str(e)}', 'error')
    
        db.session.commit()
        flash('Configurações da empresa atualizadas!', 'success')
        return redirect(url_for('admin.company_settings'))
    
    return render_template('company_settings.html', company=company)

@admin_bp.route('/settings/integrations', methods=['GET', 'POST'])
def settings_integrations():
    from models import db, Integration
    import json
    
    if not current_user.company_id:
        abort(403)

    if request.method == 'POST':
        service = request.form.get('service')
        api_key = request.form.get('api_key')
        if service and api_key:
            # Strict filter
            intg = Integration.query.filter(Integration.company_id == current_user.company_id, Integration.service == service).first()
            if not intg:
                intg = Integration(company_id=current_user.company_id, service=service)
                db.session.add(intg)
            intg.api_key = api_key
            intg.is_active = True
            db.session.commit()
            flash('Integração salva!', 'success')
        return redirect(url_for('admin.settings_integrations'))

    # Strict filter
    integrations = Integration.query.filter(Integration.company_id == current_user.company_id).all()
    integrations_map = {i.service: i for i in integrations}
    
    zapi_config = {}
    if 'z_api' in integrations_map:
        try: zapi_config = json.loads(integrations_map['z_api'].config_json or '{}')
        except: pass
        
    return render_template('settings_integrations.html', company=current_user.company, integrations_map=integrations_map, zapi_config=zapi_config)

@admin_bp.route('/settings/integrations/delete/<service>', methods=['POST'])
def delete_integration(service):
    from models import db, Integration
    if not current_user.company_id:
        abort(403)
        
    intg = Integration.query.filter_by(company_id=current_user.company_id, service=service).first()
    if intg:
        db.session.delete(intg)
        db.session.commit()
        flash(f'Integração {service} removida.', 'success')
    else:
        flash('Integração não encontrada.', 'error')
        
    return redirect(url_for('admin.settings_integrations'))

@admin_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    from models import db
    if request.method == 'POST':
        current_user.phone = request.form.get('phone')
        current_user.status_message = request.form.get('status_message')
        
        password = request.form.get('new_password')
        if password:
            current_user.password_hash = generate_password_hash(password)
            
        db.session.commit()
        flash('Perfil atualizado!', 'success')
        return redirect(url_for('admin.profile'))
        
    return render_template('profile.html', user=current_user)

@admin_bp.route('/admin/master/companies')
@login_required
def master_companies():
    if not current_user.is_super_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('master.dashboard'))

@admin_bp.route('/admin/master/companies/<int:id>/toggle-courtesy', methods=['POST'])
@login_required
def master_toggle_courtesy(id):
    from models import db, Company
    if not current_user.is_super_admin:
        abort(403)
        
    company = Company.query.get_or_404(id)
    action = request.form.get('action') # 'grant' or 'revoke'
    
    if action == 'grant':
        company.payment_status = 'courtesy'
        company.plan_type = 'courtesy_vip'
        company.platform_inoperante = False # Unblock
        flash(f'Cortesia concedida para {company.name}. Acesso liberado vitalício.', 'success')
    elif action == 'revoke':
        company.payment_status = 'pending' # Reset to pending to force regular flow or checking
        company.plan_type = 'monthly' # Default back
        flash(f'Cortesia revogada de {company.name}.', 'info')
        
    db.session.commit()
    return redirect(url_for('admin.master_companies'))

@admin_bp.route('/settings')
@login_required
def settings_index():
    return redirect(url_for('admin.profile'))

@admin_bp.route('/settings/subscription/pay', methods=['POST'])
@login_required
def generate_self_payment():
    """
    Allows the Tenant Admin to generate their own slip/subscription link.
    Reuses logic from master but strictly scoped to current_user.company_id.
    """
    # 1. Security Check
    if not current_user.company_id:
        abort(403)
        
    # Ensure only admin role (or has permission)
    if not current_user.has_permission('admin_view') and current_user.role.lower() != 'admin':
        flash("Apenas administradores podem gerenciar pagamentos.", "error")
        return redirect(url_for('admin.company_settings'))

    company_id = current_user.company_id
    
    try:
        from models import Company
        from services.asaas_service import create_customer, create_subscription, get_subscription_payments, get_subscription
        from datetime import datetime
        
        company = Company.query.get_or_404(company_id)
        
        # 2. Gather Data (Self Context)
        name = company.representative or company.name
        email = current_user.email # Use the admin's email for contact
        cpf_cnpj = company.cpf_cnpj or company.document
        phone = current_user.phone
        
        if not cpf_cnpj:
            flash("Atualize o CNPJ/CPF da empresa antes de gerar o pagamento.", "error")
            return redirect(url_for('admin.company_settings'))

        # Clean CNPJ
        import re
        cpf_cnpj_clean = re.sub(r'[^0-9]', '', str(cpf_cnpj))
        
        # 3. Ensure Customer
        if not company.asaas_customer_id:
            customer_id, error_msg = create_customer(
                name=name, email=email, cpf_cnpj=cpf_cnpj_clean, phone=phone, external_id=company.id
            )
            if customer_id:
                company.asaas_customer_id = customer_id
                db.session.commit()
            else:
                flash(f"Erro no cadastro Asaas: {error_msg}", "error")
                return redirect(url_for('admin.company_settings'))
                
        # 4. Check/Ensure Subscription
        if company.subscription_id:
             # Check validity
            sub_check = get_subscription(company.subscription_id)
            if not sub_check or 'id' not in sub_check or sub_check.get('status') == 'DELETED':
                 company.subscription_id = None
                 company.payment_status = 'pending'
                 db.session.commit()

        if not company.subscription_id:
            # Create New
            val = 197.00
            plan_key = getattr(company, 'plan', 'pro')
            if plan_key == 'enterprise': val = 997.00
            
            next_due = datetime.now().date().strftime('%Y-%m-%d')
            
            sub_data = create_subscription(
                customer_id=company.asaas_customer_id, 
                value=val, 
                next_due_date=next_due, 
                cycle='MONTHLY',
                description=f"NorthWay CRM - {company.name} ({plan_key})"
            )
            if sub_data:
                company.subscription_id = sub_data['id']
                company.payment_status = 'pending'
                db.session.commit()
                flash("Assinatura gerada com sucesso.", "success")
            else:
                flash("Falha ao criar assinatura.", "error")
                return redirect(url_for('admin.company_settings'))

        # 5. Redirect to Invoice
        payments = get_subscription_payments(company.subscription_id)
        if payments:
            invoice_url = payments[0]['invoiceUrl']
            return redirect(invoice_url)
        else:
            flash("Boleto ainda sendo processado. Tente novamente em 1 minuto.", "warning")
            
        return redirect(url_for('admin.company_settings'))
        
    except Exception as e:
        print(f"Self Payment Error: {e}")
        flash(f"Erro interno: {e}", "error")
        return redirect(url_for('admin.company_settings'))
@admin_bp.route('/admin/run-initial-migrations', methods=['GET'])
@login_required
def run_initial_migrations():
    """
    Temporary route to add diagnostic columns to relevant tables.
    Uses 'ALTER TABLE ... ADD COLUMN IF NOT EXISTS' for PostgreSQL compatibility.
    """
    # Blueprint level before_request already skips check for this endpoint.
    
    try:
        from models import db
        from sqlalchemy import text
        from flask import current_app
        
        results = []
        
        # Avoid accessing db.engine.dialect.name if possible to prevent connection hang
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        is_postgres = 'postgres' in db_uri or 'psycopg' in db_uri
        
        results.append(f"INFO: Detected DB Type via Config: {'Postgres' if is_postgres else 'SQLite/Other'}")
        
        queries = []
        
        if is_postgres:
            # POSTGRESQL QUERIES
            queries = [
                # Drive Folder Template
                """CREATE TABLE IF NOT EXISTS drive_folder_template (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id),
                    name VARCHAR(100) NOT NULL,
                    structure_json TEXT NOT NULL,
                    is_default BOOLEAN DEFAULT FALSE,
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
                
                "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_score FLOAT;",
                "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_stars FLOAT;",
                "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_classification VARCHAR(50);",
                "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_date TIMESTAMP WITH TIME ZONE;",
                "ALTER TABLE client ADD COLUMN IF NOT EXISTS diagnostic_pillars JSONB;",
                
                "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS stars FLOAT;",
                "ALTER TABLE form_submission ADD COLUMN IF NOT EXISTS classification VARCHAR(100);",
                
                "ALTER TABLE interaction ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                "ALTER TABLE task ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client(id);",
                
                "ALTER TABLE company ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}';",
                
                """CREATE TABLE IF NOT EXISTS tenant_integration (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES company(id),
                    service VARCHAR(50) NOT NULL,
                    access_token TEXT,
                    refresh_token_encrypted TEXT,
                    token_expiry_at TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'connected',
                    last_error TEXT,
                    config_json JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );"""
            ]
        else:
            # SQLITE (Simple Fallback - Warning: ALTER TABLE ADD COLUMN IF NOT EXISTS not supported in all sqlite versions directly same as PG)
            # SQLite ignores 'IF NOT EXISTS' in add column in older versions, but 'ADD COLUMN' works. 
            # We will use simple ADD COLUMN and catch 'duplicate column' errors silently.
            results.append("WARNING: Using SQLite fallback mode. Some operations might complain if columns exist.")
            results.append("WARNING: Using SQLite fallback mode. Some operations might complain if columns exist.")
            
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
                # Try adding columns one by one
                "ALTER TABLE lead ADD COLUMN diagnostic_status VARCHAR(20) DEFAULT 'pending';",
                "ALTER TABLE company ADD COLUMN features TEXT DEFAULT '{}';"
                # Add others if critical, but these are the main ones crashing the app right now
            ]

        for q in queries:
            try:
                db.session.execute(text(q))
                results.append(f"SUCCESS: {q[:30]}...")
            except Exception as e:
                # Ignore "already exists" errors (Postgres code 42701, or generic text)
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
        
    except Exception as fatal_e:
        return f"FATAL ERROR IN MIGRATION: {str(fatal_e)}"
