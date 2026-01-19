from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Company, Role, Pipeline, PipelineStage, FinancialCategory, Integration, ROLE_ADMIN, ROLE_SALES

auth = Blueprint('auth', __name__)

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
            # If Supabase login fails, we might fall back to legacy check logic below
            # verify specifically if it was invalid credentials vs other error
            pass # Keep supabase_user as None

        # 2. Local User Lookup
        user = User.query.filter_by(email=email).first()
        
        # 3. Validation Logic
        authenticated = False
        
        if supabase_user:
            # Supabase auth successful
            authenticated = True
            
            if user:
                # Link if not linked
                if not user.supabase_uid:
                     user.supabase_uid = supabase_user.id
                     db.session.commit()
            else:
                # User exists in Supabase but not locally?
                # This could happen if signed up elsewhere. For now, we block or create.
                # Let's create a minimal user linked to a default/orphan? Or just block.
                # SAFEST: Flash error "Contact support" or implementation auto-create.
                # For this task, we assume flow starts at Register.
                flash('Usuário encontrado no Supabase mas não no sistema local. Contate suporte.', 'error')
                return redirect(url_for('auth.login'))

        elif user and check_password_hash(user.password_hash, password):
             # Legacy Auth Successful
             authenticated = True
             # We should probably migrate them to Supabase here if we had the raw password,
             # but we can't migrate the hash. So they stay legacy until manual password reset.
        
        if authenticated and user:
            login_user(user)
            if getattr(user, 'is_super_admin', False):
                return redirect(url_for('master.dashboard'))
            return redirect(url_for('dashboard.home'))
        else:
            flash('Email ou senha incorretos.', 'error')
            
    return render_template('login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        name = request.form.get('name')
        email = request.form.get('email')
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
                        "company_name": company_name
                    }
                }
            })
            if res.user:
                supabase_uid = res.user.id
        except Exception as e:
            flash(f'Erro ao criar conta no Supabase: {str(e)}', 'error')
            return redirect(url_for('auth.register'))

        if not supabase_uid:
             # Should be caught by exception but just in case
             flash('Erro desconhecido no cadastro.', 'error')
             return redirect(url_for('auth.register'))
            
        # 2. Create Company
        company = Company(name=company_name)
        db.session.add(company)
        db.session.flush() # Get ID
        
        # 3. Create Default Role (Admin)
        # Updated Permissions to match new standard
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
        
        # 4. Create or Update User
        # Check if user was auto-created by Supabase Trigger (orphaned without company)
        user = User.query.filter_by(email=email).first()
        
        if user:
             # Update existing orphaned user
             user.name = name
             user.password_hash = generate_password_hash(password)
             user.supabase_uid = supabase_uid
             user.company_id = company.id
             user.role_id = admin_role.id
             user.role = 'admin'
        else:
             # Create new user
            user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password), # Keep legacy hash for fallback/hybrid
                supabase_uid=supabase_uid, 
                company_id=company.id,
                role_id=admin_role.id,
                role='admin' # Legacy field support
            )
            db.session.add(user)
        
        # 5. Bootstrap Defaults
        
        # Default Pipeline
        pipeline = Pipeline(name='Funil de Vendas', company_id=company.id)
        db.session.add(pipeline)
        db.session.flush()
        
        stages = ['Novo', 'Qualificação', 'Proposta', 'Negociação', 'Fechado']
        for i, s_name in enumerate(stages):
            stage = PipelineStage(name=s_name, order=i, pipeline_id=pipeline.id, company_id=company.id)
            db.session.add(stage)
            
        # Assign Pipeline Access
        user.allowed_pipelines.append(pipeline)
        
        # Default Financial Categories
        cats = [
            ('Vendas', 'revenue'),
            ('Serviços', 'revenue'),
            ('Marketing', 'cost'),
            ('Equipe', 'expense'),
            ('Escritório', 'expense'),
            ('Impostos', 'expense')
        ]
        for c_name, c_type in cats:
            db.session.add(FinancialCategory(name=c_name, type=c_type, is_default=True, company_id=company.id))
            
        # Default Integration Placeholders
        db.session.add(Integration(company_id=company.id, service='z_api', is_active=False))
        db.session.add(Integration(company_id=company.id, service='google_maps', is_active=False))
        
        db.session.commit()
        
        # 6. Auto Login
        login_user(user)
        flash(f'Bem-vindo à {company_name}! Sua conta foi criada.', 'success')
        return redirect(url_for('dashboard.home'))
        
    return render_template('register.html')

@auth.route('/logout')
@login_required
def logout():
    try:
        current_app.supabase.auth.sign_out()
    except:
        pass
    logout_user()
    return redirect(url_for('auth.login'))
