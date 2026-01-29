from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Company, Role, Pipeline, PipelineStage, FinancialCategory, Integration, ROLE_ADMIN, ROLE_SALES


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
            
        if 'static' in request.endpoint or 'auth.' in request.endpoint or 'checkout' in request.endpoint:
            # Explicitly allow setup_company, payment routes, and checkout
            return
            
        # 1. Enforce Company Setup
        if not current_user.company_id:
            return redirect(url_for('auth.setup_company'))
            
        # 2. Enforce Subscription Active (Skip for Super Admin if needed)
        if current_user.company and current_user.company.subscription_status != 'active':
             # Allow access if bypassing payment (optional) or strictly redirect
             # For now, strictly redirect to payment plan
             if not getattr(current_user, 'is_super_admin', False):
                 return redirect('/checkout')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
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
                user.last_login = datetime.utcnow()
                if user.company:
                    user.company.last_active_at = datetime.utcnow()
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
            
    return render_template('login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Step 1: User Info Only
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone') # Captured but currently User model might not have strict column or we use it later
        password = request.form.get('password')
        
        # 1. Validation
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado.', 'error')
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
            
        # 3. Create User (Orphaned - No Company Yet)
        user = User(
            name=name,
            email=email,
            phone=phone, # Ensure User model has this field
            password_hash=generate_password_hash(password),
            supabase_uid=supabase_uid,
            company_id=None, # Explicitly None
            role=None,
            role_id=None
        )
        db.session.add(user)
        db.session.commit()
        
        # 4. Auto Login
        login_user(user)
        flash('Conta criada! Agora configure sua empresa.', 'success')
        return redirect(url_for('auth.setup_company'))
        
    return render_template('register.html')

@auth.route('/setup-company', methods=['GET', 'POST'])
@login_required
def setup_company():
    # If already has company, skip
    if current_user.company_id:
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        company_name = request.form.get('company_name')
        cpf_cnpj = request.form.get('cpf_cnpj')
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
        
        flash('Empresa configurada! Escolha seu plano.', 'success')
        return redirect('/checkout')
        
    return render_template('setup_company.html', minimal=True)

@auth.route('/payment-plan')
@login_required
def payment_plan():
    # Helper redirect to main checkout
    return redirect('/checkout')

@auth.route('/logout')
@login_required
def logout():
    try:
        current_app.supabase.auth.sign_out()
    except:
        pass
    logout_user()
    return redirect(url_for('auth.login'))
