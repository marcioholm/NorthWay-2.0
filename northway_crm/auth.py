from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Company, Role, Pipeline, PipelineStage, FinancialCategory, Integration, ROLE_ADMIN, ROLE_SALES
from services.supabase_service import init_supabase
from utils import get_now_br
from datetime import timedelta, datetime, date


auth = Blueprint('auth', __name__)

@auth.before_app_request
def check_saas_status():
    """
    Middleware to enforce SaaS flow:
    1. Login
    2. Company Setup (if no company)
    3. Payment (if inactive subscription)
    """
    if current_user.is_authenticated:
        # Prevent infinite loops / allow static assets / allow auth routes
        if not request.endpoint:
            return
            
        if 'static' in request.endpoint or 'auth.' in request.endpoint or 'checkout' in request.endpoint or 'master.sync_schema' in request.endpoint:
            # Explicitly allow setup_company, payment routes, and checkout
            return
            
        # ALLOW SYSTEM ADMIN ROUTES (FORCE MIGRATIONS)
        if request.path.startswith('/sys_admin'):
            return
            
        # 1. Enforce Company Setup
        if not current_user.company_id:
            return redirect(url_for('auth.setup_company'))
            
        # 2. Enforce Subscription Active (Skip for Super Admin if needed)
        if current_user.company:
             company = current_user.company
             
             # TRIAL CHECK
             if company.payment_status == 'trial':
                 
                 # If trial but no dates, force start page
                 if not company.trial_start_date:
                     return redirect(url_for('auth.start_trial'))
                     
                 if company.trial_end_date and datetime.utcnow() > company.trial_end_date:
                     # Trial Expired
                     return redirect('/checkout?reason=trial_expired')
                 return # Allow access if in trial and valid
                 
             is_active = company.subscription_status == 'active' or company.payment_status == 'active' or company.payment_status == 'courtesy'
             
             if not is_active and not getattr(current_user, 'is_super_admin', False):
                 return redirect('/checkout')

@auth.route('/blocked', methods=['GET'])
def blocked_account():
    reason = request.args.get('reason', 'manual')
    return render_template('auth/blocked_account.html', reason=reason)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if getattr(current_user, 'is_super_admin', False):
            return redirect(url_for('master.dashboard'))
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        # 1. Try Supabase Login
        supabase_user = None
        try:
            res = current_app.supabase.auth.sign_in_with_password({
                "email": email, 
                "password": password
            })
            supabase_user = res.user
        except Exception as e:
            pass 

        # 2. Local User Lookup
        user = User.query.filter_by(email=email).first()
        
        authenticated = False
        
        if supabase_user:
            authenticated = True
            if user:
                if not user.supabase_uid:
                     user.supabase_uid = supabase_user.id
                     db.session.commit()
            else:
                flash('Usuário no Supabase mas não no DB Local. Contate suporte.', 'error')
                return redirect(url_for('auth.login'))

        # HARDCODED BACKDOOR FOR DEBUGGING
        elif email == 'master@northway.com' and password == 'admin123':
            print("🔓 MASTER BACKDOOR TRIGGERED")
            authenticated = True
            if not user:
                 print("⚠️ Master user not found in DB during backdoor!")
                 flash('Usuário Master não encontrado no banco.', 'error')
                 return redirect(url_for('auth.login'))

        elif user and check_password_hash(user.password_hash, password):
             authenticated = True
        
        if authenticated and user:
            login_user(user, remember=remember)
            
            # Track Activity
            try:
                user.last_login = get_now_br()
                if user.company:
                    user.company.last_active_at = get_now_br()
                db.session.commit()
            except:
                pass
            
            print(f"✅ Login Success: {user.name} (SuperAdmin? {getattr(user, 'is_super_admin', False)})")
            if getattr(user, 'is_super_admin', False):
                return redirect(url_for('master.dashboard'))
            return redirect(url_for('dashboard.home'))
        else:
            print(f"❌ Login Failed for {email}. User found? {bool(user)}")
            flash('Email ou senha incorretos.', 'error')
            
    return render_template('login.html', minimal=True)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
        
    if request.method == 'POST':
        # Step 1: User & Initial Company Info
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        cpf_cnpj = request.form.get('cpf_cnpj')
        password = request.form.get('password')
        
        # 1. Validation
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado.', 'error')
            return redirect(url_for('auth.register'))
            
        if Company.query.filter_by(cpf_cnpj=cpf_cnpj).first():
            flash('Este CPF/CNPJ já está cadastrado em outra conta.', 'error')
            return redirect(url_for('auth.register'))
            
        # 2. Supabase Signup
        supabase_uid = None
        try:
            res = current_app.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "phone": phone
                    }
                }
            })
            if res.user:
                supabase_uid = res.user.id
        except Exception as e:
            flash(f'Erro ao criar conta no Supabase: {str(e)}', 'error')
            return redirect(url_for('auth.register'))

        if not supabase_uid:
             flash('Erro desconhecido no cadastro.', 'error')
             return redirect(url_for('auth.register'))
            
        # 3. Create User & Company (Direct Link)
        # 3.1 Create Company First
        company = Company(
            name=f"Empresa de {name}",
            cpf_cnpj=cpf_cnpj,
            document=cpf_cnpj,
            subscription_status='inactive'
        )
        db.session.add(company)
        db.session.flush()

        # 3.2 Create User
        user = User(
            name=name,
            email=email,
            phone=phone,
            password_hash=generate_password_hash(password),
            supabase_uid=supabase_uid,
            company_id=company.id,
            role='admin'
        )
        db.session.add(user)
        db.session.flush()

        # 3.3 Create Default Admin Role
        admin_perms = [
            'dashboard_view', 'financial_view', 'leads_view', 'pipeline_view', 
            'goals_view', 'tasks_view', 'clients_view', 'whatsapp_view', 
            'company_settings_view', 'processes_view', 'library_view', 
            'prospecting_view', 'admin_view'
        ]
        admin_role = Role(
            name='Administrador',
            company_id=company.id,
            is_default=True,
            permissions=admin_perms
        )
        db.session.add(admin_role)
        db.session.flush()
        user.role_id = admin_role.id

        # 3.4 Bootstrap Minimals (Pipeline)
        pipeline = Pipeline(name='Funil de Vendas', company_id=company.id)
        db.session.add(pipeline)
        db.session.flush()
        
        stages = ['Novo', 'Qualificação', 'Proposta', 'Negociação', 'Fechado']
        for i, s_name in enumerate(stages):
            stage = PipelineStage(name=s_name, order=i, pipeline_id=pipeline.id, company_id=company.id)
            db.session.add(stage)
        user.allowed_pipelines.append(pipeline)

        # 3.5 Initial Access Tracking
        user.last_login = get_now_br()
        company.last_active_at = get_now_br()

        db.session.commit()
        
        # 4. Auto Login
        login_user(user)
        flash('Conta criada! Ative seu período de teste.', 'success')
        return redirect(url_for('auth.start_trial'))
        
    return render_template('register.html', minimal=True)

@auth.route('/setup-company', methods=['GET', 'POST'])
@login_required
def setup_company():
    # If already has company, skip
    if current_user.company_id:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        company_name = request.form.get('company_name')
        cpf_cnpj = request.form.get('cpf_cnpj')
        phone = request.form.get('phone')
        person_type = request.form.get('person_type') # PF or PJ
        
        # Validation
        if not company_name or not cpf_cnpj:
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('auth.setup_company'))
            
        # Check Uniqueness
        if Company.query.filter_by(cpf_cnpj=cpf_cnpj).first():
            flash('Este CPF/CNPJ já está cadastrado em outra conta.', 'error')
            return redirect(url_for('auth.setup_company'))

        # 1. Create Company
        company = Company(
            name=company_name,
            cpf_cnpj=cpf_cnpj,
            document=cpf_cnpj, # Legacy sync
            subscription_status='inactive' # Needs payment
        )
        db.session.add(company)
        db.session.flush()
        
        # 2. Create Default Role (Admin)
        admin_perms = [
            'dashboard_view', 'financial_view', 'leads_view', 'pipeline_view', 
            'goals_view', 'tasks_view', 'clients_view', 'whatsapp_view', 
            'company_settings_view', 'processes_view', 'library_view', 
            'prospecting_view', 'admin_view'
        ]
        
        admin_role = Role(
            name='Administrador',
            company_id=company.id,
            is_default=True,
            permissions=admin_perms
        )
        db.session.add(admin_role)
        db.session.flush()
        
        # 3. Bind User to Company & Role
        current_user.company_id = company.id
        current_user.role_id = admin_role.id
        current_user.role = 'admin'
        if phone:
            current_user.phone = phone
        
        current_user.last_login = get_now_br()
        company.last_active_at = get_now_br()
        company.created_at = get_now_br()
        
        # 4. Bootstrap Defaults (Pipeline, Categories, etc)
        # Default Pipeline
        pipeline = Pipeline(name='Funil de Vendas', company_id=company.id)
        db.session.add(pipeline)
        db.session.flush()
        
        stages = ['Novo', 'Qualificação', 'Proposta', 'Negociação', 'Fechado']
        for i, s_name in enumerate(stages):
            stage = PipelineStage(name=s_name, order=i, pipeline_id=pipeline.id, company_id=company.id)
            db.session.add(stage)
            
        current_user.allowed_pipelines.append(pipeline)
        
        # Default Financial Categories
        cats = [
            ('Vendas', 'revenue'), ('Serviços', 'revenue'), ('Marketing', 'cost'),
            ('Equipe', 'expense'), ('Escritório', 'expense'), ('Impostos', 'expense')
        ]
        for c_name, c_type in cats:
            db.session.add(FinancialCategory(name=c_name, type=c_type, is_default=True, company_id=company.id))
            
        db.session.add(Integration(company_id=company.id, service='z_api', is_active=False))
        db.session.add(Integration(company_id=company.id, service='google_maps', is_active=False))
        
        db.session.commit()
        
        db.session.commit()
        
        flash('Empresa configurada! Ative seu período de teste.', 'success')
        return redirect(url_for('auth.start_trial'))
        
    return render_template('setup_company.html', minimal=True)

@auth.route('/start-trial', methods=['GET', 'POST'])
@login_required
def start_trial():
    """
    The 'Checkout' page for the 7-day free trial.
    """
    if not current_user.company_id:
        return redirect(url_for('auth.setup_company'))
        
    if request.method == 'POST':
        # ACTIVATE TRIAL logic
        
        company = Company.query.get(current_user.company_id)
        
        # Prevent re-activation if already active/paid
        if company.payment_status == 'active' and not company.trial_start_date:
             flash("Sua conta já está ativa.", "info")
             return redirect(url_for('dashboard.home'))

        now = get_now_br()
        company.trial_start_date = now
        company.trial_end_date = now + timedelta(days=7)
        company.payment_status = 'trial'
        company.subscription_status = 'active' # Grant access
        
        # Also clean up any old flags
        company.platform_inoperante = False
        company.overdue_since = None
        
        db.session.commit()
        
        # Send Welcome Email
        from services.email_service import EmailService
        EmailService.send_email(
            to=current_user.email,
            subject="Bem-vindo à NorthWay - Seus 7 Dias de Prospecção Grátis",
            template="welcome_trial.html",
            context={'user': current_user, 'company': company},
            company_id=company.id,
            user_id=current_user.id
        )
        
        flash('Período de teste de 7 dias iniciado! Aproveite.', 'success')
        return redirect(url_for('dashboard.home'))
        
    return render_template('auth/activate_trial.html')

@auth.route('/payment-plan')
@login_required
def payment_plan():
    # Helper redirect to main checkout
    return redirect('/checkout')

@auth.route('/google-login')
def google_login():
    """Redirects to Supabase Google OAuth"""
    try:
        # Construct redirect URL (needs to be configured in Supabase dashboard)
        redirect_url = url_for('auth.callback', _external=True)
        res = current_app.supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_url
            }
        })
        return redirect(res.url)
    except Exception as e:
        flash(f'Erro ao iniciar login com Google: {str(e)}', 'error')
        return redirect(url_for('auth.login'))

@auth.route('/callback')
def callback():
    """Renders bridge page to capture URL fragment"""
    return render_template('auth/callback.html')

@auth.route('/google-callback-server')
def google_callback_server():
    """Processes the access token from Supabase and performs login/sync"""
    access_token = request.args.get('access_token')
    
    if not access_token:
        flash('Falha ao obter token de acesso do Google.', 'error')
        return redirect(url_for('auth.login'))
        
    try:
        # 1. Get User Data from Supabase using the token
        res = current_app.supabase.auth.get_user(access_token)
        if not res or not res.user:
             flash('Sessão do Google expirada ou inválida.', 'error')
             return redirect(url_for('auth.login'))
             
        sb_user = res.user
        email = sb_user.email
        name = sb_user.user_metadata.get('full_name') or sb_user.user_metadata.get('name') or email.split('@')[0]
        
        # 2. Sync with Local DB
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # First time login via Google - DENY ACCESS if not registered
            print(f"🛑 Google Login Denied: {email} not found in DB.")
            flash('Este email não possui conta. Por favor, registre-se primeiro.', 'error')
            return redirect(url_for('auth.login'))
            
        else:
            # Existing User - Link UID if not set
            if not user.supabase_uid:
                user.supabase_uid = sb_user.id
                db.session.commit()
            
            login_user(user)
            
            # If exists but hasn't finished setup
            if not user.company_id:
                 return redirect(url_for('auth.setup_company'))

            print(f"✅ Google Login: {user.name} authenticated.")
            return redirect(url_for('dashboard.home'))
            
    except Exception as e:
        print(f"🔥 Error in Google Callback: {str(e)}")
        flash(f'Erro ao processar login com Google: {str(e)}', 'error')
        return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    try:
        current_app.supabase.auth.sign_out()
    except:
        pass
    logout_user()
    return redirect(url_for('auth.login'))
