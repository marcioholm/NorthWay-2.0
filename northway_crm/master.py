from flask import Blueprint, render_template, redirect, url_for, session, abort, flash, request
from flask_login import login_required, current_user, login_user
from models import db, User, Company, ROLE_ADMIN, ContractTemplate, template_company_association, DriveFolderTemplate, LibraryTemplate, LibraryTemplateGrant, LibraryBook, library_book_company_association
from utils import get_now_br
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import joinedload

master = Blueprint('master', __name__)

@master.before_request
def check_master_access():
    if request.endpoint == 'master.revert_access':
        original_id = session.get('super_admin_id')
        if not original_id:
            abort(403)
        original_user = User.query.get(original_id)
        if not original_user or not getattr(original_user, 'is_super_admin', False):
            abort(403)
        return

    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if not getattr(current_user, 'is_super_admin', False):
        abort(403)

@master.route('/master/dashboard')
@login_required
def dashboard():
    # Fetch all companies ordered by newest first WITH joinedload to avoid N+1 queries
    companies = (
        Company.query
        .options(joinedload(Company.users))
        .order_by(Company.created_at.desc())
        .all()
    )
    
    # Global Metrics Aggregation
    total_companies = len(companies)
    active_companies = sum(1 for c in companies if getattr(c, 'status', 'active') == 'active')
    
    # Calculate Users & Leads (Scanning all companies)
    total_users = User.query.count()
    from models import Lead, Contract
    try:
        total_leads = Lead.query.count() or 0
    except Exception:
        total_leads = 0
        
    try:
        total_contracts = Contract.query.count() or 0
    except Exception:
        total_contracts = 0
        
    # Mock MRR Calculation (Plan based) - Exclude Master Company
    mrr = 0
    # master_company_name = "NorthWay Master" # or just check if it's the current user's company if we assume only one master
    
    plan_prices = {'free': 0, 'starter': 149, 'pro': 197, 'enterprise': 997, 'courtesy_vip': 0}
    
    # Churn mock (companies with status='cancelled')
    cancelled_companies = sum(1 for c in companies if getattr(c, 'status', 'active') == 'cancelled')
    churn_rate = (cancelled_companies / total_companies * 100) if total_companies > 0 else 0
    
    stats = []
    
    for comp in companies:
        # Calculate MRR per company
        plan_name = (getattr(comp, 'plan', 'pro') or 'pro').lower()
        if comp.payment_status == 'courtesy': plan_name = 'courtesy_vip'
        
        # EXCLUDE Master/Super Admin company from MRR
        # ALSO EXCLUDE companies in trial
        is_paying = comp.id != current_user.company_id and comp.payment_status != 'trial'
        
        if is_paying:
            mrr += plan_prices.get(plan_name, 0)
        
        # Find an admin from pre-loaded users relationship (NO extra query)
        admin_user = next(
            (u for u in comp.users if u.role == ROLE_ADMIN), 
            comp.users[0] if comp.users else None
        )
        # Fallback to any user if no admin (rare) - still no extra query since users are in memory
        if not admin_user:
            admin_user = comp.users[0] if comp.users else None
            
        user_count = len(comp.users)  # Already in memory from joinedload
        comp.user_count = user_count # Attach for direct usage if needed
        comp.admin = admin_user
        
        stats.append({
            'company': comp,
            'user_count': user_count,
            'target_user_id': admin_user.id if admin_user else None,
            'admin_name': admin_user.name if admin_user else "---"
        })
        
    global_kpis = {
        'companies': total_companies,
        'active_companies': active_companies,
        'users': total_users,
        'leads': total_leads,
        'contracts': total_contracts,
        'mrr': mrr,
        'churn': round(churn_rate, 1)
    }
    
    from datetime import date
    return render_template('master_dashboard.html', stats=stats, kpis=global_kpis, now_date=date.today())

@master.route('/master/export/marketing')
@login_required
def export_marketing():
    """
    Generates a CSV export of all companies and their primary admins for marketing.
    """
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    import csv
    from io import StringIO
    from flask import Response
    
    companies = Company.query.order_by(Company.created_at.desc()).all()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow([
        'ID Empresa', 'Nome Empresa', 'CNPJ/CPF', 'Status Pagamento', 'Plano',
        'Data Criação', 'Nome Admin', 'Email Admin', 'WhatsApp Admin', 'Último Acesso'
    ])
    
    for comp in companies:
        admin = User.query.filter_by(company_id=comp.id, role=ROLE_ADMIN).first()
        if not admin:
            admin = User.query.filter_by(company_id=comp.id).first()
            
        cw.writerow([
            comp.id,
            comp.name,
            comp.cpf_cnpj or comp.document or '---',
            comp.payment_status,
            comp.plan or 'pro',
            comp.created_at.strftime('%d/%m/%Y %H:%M') if comp.created_at else '---',
            admin.name if admin else '---',
            admin.email if admin else '---',
            admin.phone if admin else '---',
            admin.last_login.strftime('%d/%m/%Y %H:%M') if admin and admin.last_login else 'Nunca'
        ])
        
    output = si.getvalue()
    si.close()
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=northway_marketing_export.csv"}
    )

@master.route('/master/company/<int:company_id>/materials', methods=['GET', 'POST'])
@login_required
def company_materials(company_id):
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        try:
            # 1. Update Library Books
            allowed_book_ids = request.form.getlist('books')
            
            all_books = LibraryBook.query.all()
            for book in all_books:
                if str(book.id) in allowed_book_ids:
                    if company not in book.allowed_companies:
                        book.allowed_companies.append(company)
                else:
                    if company in book.allowed_companies:
                        book.allowed_companies.remove(company)

            # 2. Update Contract Templates
            allowed_template_ids = request.form.getlist('templates')
            
            all_templates = ContractTemplate.query.all()
            for tmpl in all_templates:
                if str(tmpl.id) in allowed_template_ids:
                    if company not in tmpl.allowed_companies:
                        tmpl.allowed_companies.append(company)
                else:
                    if company in tmpl.allowed_companies:
                        tmpl.allowed_companies.remove(company)
                        
            # 3. Update Diagnostic Access
            diagnostic_enabled = request.form.get('diagnostic_enabled') == 'on'
            
            # Get the Diagnostic Template
            diag_template = LibraryTemplate.query.filter_by(key="diagnostico_northway_v1").first()
            
            if diag_template:
                # 3.1 Get Company Admins
                company_admins = User.query.filter_by(company_id=company.id, role=ROLE_ADMIN).all()
                
                if diagnostic_enabled:
                    # Grant active access to all admins if not already granted
                    for admin in company_admins:
                        grant = LibraryTemplateGrant.query.filter_by(
                            user_id=admin.id,
                            template_id=diag_template.id
                        ).first()
                        
                        if not grant:
                            # Create new grant
                            grant = LibraryTemplateGrant(
                                tenant_id=company.id,
                                template_id=diag_template.id,
                                user_id=admin.id,
                                granted_by_user_id=current_user.id,
                                status='active'
                            )
                            db.session.add(grant)
                        elif grant.status != 'active':
                            # Reactivate
                            grant.status = 'active'
                else:
                    # Revoke access for ALL users in this company (not just admins, to be safe)
                    all_company_grants = LibraryTemplateGrant.query.filter_by(
                        tenant_id=company.id,
                        template_id=diag_template.id
                    ).all()
                    
                    for grant in all_company_grants:
                        grant.status = 'revoked'
                        
            # 4. Update Global Drive Templates
            allowed_global_ids = request.form.getlist('allowed_global_templates')
            default_global_id = request.form.get('default_template_id')
            auto_create = request.form.get('auto_create_subfolders') == 'on'
            
            company.allowed_global_template_ids = [int(i) for i in allowed_global_ids]
            company.default_template_id = int(default_global_id) if default_global_id else None
            company.auto_create_subfolders = auto_create

            db.session.commit()
            flash(f"Permissões de materiais para {company.name} atualizadas!", "success")
            return redirect(url_for('master.dashboard'))
        except Exception as e:
            db.session.rollback()
            print(f"CRITICAL ERROR in company_materials: {e}")
            flash(f"Erro ao salvar permissões: {str(e)}", "error")
            return redirect(url_for('master.company_materials', company_id=company.id))
        
    books = LibraryBook.query.filter_by(active=True).order_by(LibraryBook.created_at.desc()).all()
    templates = ContractTemplate.query.filter_by(active=True).all()
    global_drive_templates = DriveFolderTemplate.query.filter_by(scope='global').all()
    
    # Check if diagnostic is active...
    diag_template = LibraryTemplate.query.filter_by(key="diagnostico_northway_v1").first()
    diagnostic_active = False
    if diag_template:
        diagnostic_active = LibraryTemplateGrant.query.filter_by(
            tenant_id=company.id, 
            template_id=diag_template.id, 
            status='active'
        ).count() > 0
    
    return render_template('master_company_materials.html', 
                           company=company, 
                           books=books, 
                           templates=templates,
                           global_drive_templates=global_drive_templates,
                           diagnostic_active=diagnostic_active,
                           now=get_now_br())

@master.route('/master/templates/global', methods=['GET', 'POST'])
@login_required
def global_templates():
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    if request.method == 'POST':
        import json
        name = request.form.get('name')
        structure_json = request.form.get('structure_json')
        template_id = request.form.get('template_id')
        
        try:
            # Validate JSON
            json.loads(structure_json)
            
            if template_id:
                template = DriveFolderTemplate.query.get_or_404(template_id)
                template.name = name
                template.structure_json = structure_json
                flash(f"Template '{name}' atualizado com sucesso.", "success")
            else:
                new_template = DriveFolderTemplate(
                    name=name,
                    structure_json=structure_json,
                    scope='global',
                    company_id=None
                )
                db.session.add(new_template)
                flash(f"Template '{name}' criado com sucesso.", "success")
            
            db.session.commit()
        except json.JSONDecodeError:
            flash("Erro: Estrutura JSON inválida.", "error")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar template: {e}", "error")
            
        return redirect(url_for('master.global_templates'))
        
    templates = DriveFolderTemplate.query.filter_by(scope='global').all()
    return render_template('master_global_templates.html', templates=templates)

@master.route('/master/templates/global/<int:id>/delete', methods=['POST'])
@login_required
def delete_global_template(id):
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    template = DriveFolderTemplate.query.get_or_404(id)
    try:
        db.session.delete(template)
        db.session.commit()
        flash(f"Template '{template.name}' excluído.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir template: {e}", "error")
        
    return redirect(url_for('master.global_templates'))

@master.route('/master/company/<int:company_id>/templates/global', methods=['POST'])
@login_required
def update_company_global_templates(company_id):
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    company = Company.query.get_or_404(company_id)
    allowed_ids = request.form.getlist('allowed_global_templates')
    default_id = request.form.get('default_template_id')
    auto_create = request.form.get('auto_create_subfolders') == 'on'
    
    try:
        # Convert IDs to integers
        company.allowed_global_template_ids = [int(i) for i in allowed_ids]
        company.default_template_id = int(default_id) if default_id else None
        company.auto_create_subfolders = auto_create
        
        db.session.commit()
        flash(f"Permissões de templates para {company.name} atualizadas!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao atualizar permissões: {e}", "error")
        
    return redirect(url_for('master.company_materials', company_id=company.id))

@master.route('/master/impersonate/<int:user_id>')
def impersonate(user_id):
    target_user = User.query.get_or_404(user_id)
    
    
    if target_user.id == current_user.id:
        flash("Você não pode impersonar a si mesmo.", "warning")
        return redirect(url_for('admin.master_companies'))

    # Store original admin ID in session
    session['super_admin_id'] = current_user.id
    
    # Perform Login as target
    login_user(target_user)
    
    flash(f"Acessando como: {target_user.name} @ {target_user.company.name}", "warning")
    return redirect(url_for('dashboard.home'))

@master.route('/master/revert')
def revert_access():
    original_id = session.get('super_admin_id')
    if not original_id:
        abort(403)
        
    original_user = User.query.get(original_id)
    if original_user and getattr(original_user, 'is_super_admin', False):
        login_user(original_user)
        session.pop('super_admin_id', None)
        flash("Sessão Master restaurada.", "success")
        return redirect(url_for('admin.master_companies'))
    
    abort(403)

@master.route('/master/company/<int:company_id>/users')
def company_users(company_id):
    company = Company.query.get_or_404(company_id)
    users = User.query.filter_by(company_id=company_id).all()
    return render_template('master_company_users.html', company=company, users=users)

@master.route('/master/company/<int:company_id>/user/new', methods=['GET', 'POST'])
@login_required
def company_user_new(company_id):
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role'] # 'admin' or 'user'
        
        # Check email availability
        if User.query.filter_by(email=email).first():
            flash("Email já cadastrado no sistema.", "error")
            return redirect(url_for('master.company_user_new', company_id=company_id))

        try:
            from werkzeug.security import generate_password_hash
            new_user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                company_id=company_id,
                role=role
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash(f"Usuário {name} criado com sucesso!", "success")
            return redirect(url_for('master.company_users', company_id=company_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar usuário: {e}", "error")
            
    return render_template('master_user_form.html', user=None, company=company)

@master.route('/master/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.role = request.form['role']
        
        new_password = request.form.get('password')
        if new_password:
            from werkzeug.security import generate_password_hash
            user.password_hash = generate_password_hash(new_password)
            
        try:
            db.session.commit()
            flash(f"Usuário {user.name} atualizado com sucesso!", "success")
            return redirect(url_for('master.company_users', company_id=user.company_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar: {e}", "error")
        
    return render_template('master_user_form.html', user=user, company=user.company)

@master.route('/master/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    user = User.query.get_or_404(user_id)
    company_id = user.company_id
    
    # Safety Check: Can't delete yourself
    if user.id == current_user.id:
        flash("Você não pode excluir a sua própria conta Master.", "error")
        return redirect(url_for('master.company_users', company_id=company_id))
        
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"Usuário {user.name} excluído com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir usuário: {e}", "error")
        
    return redirect(url_for('master.company_users', company_id=company_id))

@master.route('/master/companies')
@login_required
def companies():
    # Redirect to Unified Dashboard
    return redirect(url_for('master.dashboard'))

@master.route('/master/company/new', methods=['GET', 'POST'])
@login_required
def company_new():
    if request.method == 'POST':
        name = request.form['name']
        plan = request.form['plan']
        
        # Validation
        if not name:
            flash("Nome da empresa é obrigatório.", "error")
            return redirect(url_for('master.company_new'))
            
        try:
            new_comp = Company(name=name, plan=plan, status='active', payment_status='pending', subscription_status='inactive')
            
            # Set limits based on plan
            if plan == 'enterprise':
                new_comp.max_users = 100
                new_comp.max_leads = 50000
            elif plan == 'pro':
                new_comp.max_users = 10
                new_comp.max_leads = 5000
            else: # starter
                new_comp.max_users = 2
                new_comp.max_leads = 500
                
            # Features Handling
            feats = {
                'whatsapp': request.form.get('feature_whatsapp') == 'on',
                'prospecting': request.form.get('feature_prospecting') == 'on',
                'google_drive': request.form.get('feature_drive') == 'on',
                'cnpja': request.form.get('feature_cnpja') == 'on',
                'asaas': request.form.get('feature_asaas') == 'on',
                'compass': request.form.get('feature_compass') == 'on'
            }
            new_comp.features = feats

            db.session.add(new_comp)
            db.session.commit()

            # --- Initialize Default Data (Roles & Pipeline) ---
            from models import Role, Pipeline, PipelineStage
            
            # 1. Default Roles
            admin_role = Role(name='Administrador', company_id=new_comp.id, permissions=['admin_view', 'dashboard_view', 'pipeline_view', 'leads_view', 'company_settings_view', 'processes_view', 'library_view', 'prospecting_view'])
            db.session.add(admin_role)
            
            # 2. Default Pipeline
            default_pipeline = Pipeline(name='Vendas B2B', company_id=new_comp.id)
            db.session.add(default_pipeline)
            db.session.commit() # Commit to get ID
            
            # 3. Default Stages
            stages = ['Novo', 'Qualificação', 'Proposta', 'Negociação', 'Fechado']
            for i, s_name in enumerate(stages):
                stage = PipelineStage(name=s_name, order=i, pipeline_id=default_pipeline.id, company_id=new_comp.id)
                db.session.add(stage)
            
            db.session.commit()
            flash(f"Empresa '{name}' criada com sucesso!", "success")
            return redirect(url_for('master.companies'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar empresa: {e}", "error")
            
    return render_template('master_company_form.html', company=None)

@master.route('/master/company/<int:company_id>/edit', methods=['GET', 'POST'])
@login_required
def company_edit(company_id):
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        company.name = request.form['name']
        company.plan = request.form['plan']
        company.status = request.form['status']
        company.max_users = int(request.form['max_users'])
        company.max_leads = int(request.form['max_leads'])
        company.max_leads = int(request.form['max_leads'])
        company.document = request.form.get('document')
        
        # Features Handling - Force reassignment for SQLAlchemy tracking
        new_feats = {}
        # Preservar chaves existentes que não estão no form
        if company.features:
            if isinstance(company.features, str):
                import json
                try: new_feats = json.loads(company.features)
                except: new_feats = {}
            else:
                new_feats = dict(company.features)
            
        new_feats['whatsapp'] = request.form.get('feature_whatsapp') == 'on'
        new_feats['prospecting'] = request.form.get('feature_prospecting') == 'on'
        new_feats['google_drive'] = request.form.get('feature_drive') == 'on'
        new_feats['drive'] = request.form.get('feature_drive') == 'on' # Alias de compatibilidade
        new_feats['cnpja'] = request.form.get('feature_cnpja') == 'on'
        new_feats['asaas'] = request.form.get('feature_asaas') == 'on'
        new_feats['compass'] = request.form.get('feature_compass') == 'on'
        
        company.features = new_feats
        db.session.add(company) # Mark as dirty explicitly
        
        try:
            db.session.commit()
            flash(f"Empresa '{company.name}' atualizada.", "success")
            return redirect(url_for('master.companies'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar: {e}", "error")
            
    return render_template('master_company_form.html', company=company)


@master.route('/master/company/<int:company_id>/details')
@login_required
def company_details(company_id):
    from datetime import datetime, date
    company = Company.query.get_or_404(company_id)
    admin_user = User.query.filter_by(company_id=company_id, role='admin').first()
    
    # Subscription & Remaining Time Logic
    days_remaining = None
    next_due_fmt = None
    
    if company.subscription_id:
        try:
            from services.asaas_service import get_subscription
            sub_data = get_subscription(company.subscription_id)
            
            if sub_data and 'nextDueDate' in sub_data:
                # Update DB
                next_due_str = sub_data['nextDueDate']
                next_due = datetime.strptime(next_due_str, '%Y-%m-%d').date()
                # company.next_due_date = next_due
                
                # Check Status (Sync DB if needed)
                if sub_data.get('status') == 'ACTIVE':
                    if company.payment_status != 'active': company.payment_status = 'active'
                elif sub_data.get('status') == 'OVERDUE':
                    if company.payment_status != 'overdue': company.payment_status = 'overdue'

                db.session.commit()
                
                # Calculate Remaining Days
                delta = next_due - date.today()
                days_remaining = delta.days
                next_due_fmt = next_due.strftime('%d/%m/%Y')
                
        except Exception as e:
            print(f"Error fetching sub details: {e}")

    # Fallback if DB has date but API failed or wasn't called
    if not days_remaining and company.next_due_date:
        delta = company.next_due_date - get_now_br().date()
        days_remaining = delta.days
        next_due_fmt = company.next_due_date.strftime('%d/%m/%Y')

    return render_template('master_company_details.html', 
                          company=company, 
                          admin_user=admin_user,
                          days_remaining=days_remaining,
                          next_due_fmt=next_due_fmt)


@master.route('/master/company/<int:company_id>/generate-payment', methods=['POST'])
@login_required
def generate_payment(company_id):
    """
    Manually triggers payment generation (Asaas Customer + Subscription) for a company.
    Useful if the automatic flow failed or was skipped.
    """
    try:
        from services.asaas_service import create_customer, create_subscription, get_subscription_payments
        from datetime import datetime
        
        company = Company.query.get_or_404(company_id)
        
        # 1. Gather Best Available Data
        # Priority: Company Representative/Doc -> Admin User Data -> Fallbacks
        
        # Default/Fallback values
        name = company.representative or company.name
        email = f"billing_{company.id}@northway.com.br" # Generic fallback
        cpf_cnpj = company.cpf_cnpj or company.document
        phone = None
        
        # Try to find an Admin User to enrich data
        admin = User.query.filter_by(company_id=company.id, role=ROLE_ADMIN).first()
        if not admin:
             # Fallback to any user
             admin = User.query.filter_by(company_id=company.id).first()
             
        if admin:
            # If company representative is missing, use Admin's name
            if not company.representative:
                name = admin.name
                
            # Always prefer Admin email over generic one, unless company has a specific financial email field (which it doesn't yet)
            email = admin.email
            phone = admin.phone
            
        if not cpf_cnpj:
            flash("Empresa sem Documento (CPF/CNPJ). Edite a empresa antes de gerar pagamento.", "error")
            return redirect(url_for('master.company_details', company_id=company.id))

        # Clean CNPJ/CPF (Remove dots, dashes, slashes)
        import re
        cpf_cnpj_clean = re.sub(r'[^0-9]', '', str(cpf_cnpj))
        
        # 2. Ensure Customer
        if not company.asaas_customer_id:
            customer_id, error_msg = create_customer(
                name=name, 
                email=email,
                cpf_cnpj=cpf_cnpj_clean, 
                phone=phone, 
                external_id=company.id
            )
            if customer_id:
                company.asaas_customer_id = customer_id
                db.session.commit()
                flash(f"Cliente Asaas criado: {name} ({email})", "success")
            else:
                flash(f"Falha Asaas: {error_msg}", "error")
                return redirect(url_for('master.company_details', company_id=company.id))
        
        # 2.5 Validation: Check if existing subscription is valid in Asaas
        # If we have an ID like 'sub_sim_pro' (legacy/dummy), this will fail effectively.
        if company.subscription_id:
            # Import newly added function
            from services.asaas_service import get_subscription
            
            sub_check = get_subscription(company.subscription_id)
            if not sub_check or 'id' not in sub_check:
                print(f"⚠️ Invalid/Deleted Subscription found ({company.subscription_id}). Clearing to regenerate.")
                company.subscription_id = None
                company.payment_status = 'pending' # Reset status
                db.session.commit()
            elif sub_check.get('status') == 'DELETED':
                 # Also regenerate if deleted
                print(f"⚠️ Subscription {company.subscription_id} was DELETED in Asaas. Regenerating.")
                company.subscription_id = None
                company.payment_status = 'pending'
                db.session.commit()

        # 3. Ensure Subscription
        if not company.subscription_id:
            # Determine Value based on Plan
            val = 197.00
            plan_key = getattr(company, 'plan', 'pro')
            plan_type = getattr(company, 'plan_type', 'monthly')
            
            if plan_key == 'enterprise':
                val = 997.00
            elif plan_type == 'annual':
                val = 1999.00
                
            next_due = datetime.now().date().strftime('%Y-%m-%d')
            
            sub_data = create_subscription(
                customer_id=company.asaas_customer_id, 
                value=val, 
                next_due_date=next_due, 
                cycle='MONTHLY' if plan_type != 'annual' else 'YEARLY',
                description=f"NorthWay CRM - {company.name} ({plan_key}/{plan_type})",
                disable_notifications=True
            )
            if sub_data:
                company.subscription_id = sub_data['id']
                company.payment_status = 'pending'
                
                # Save Next Due Date immediately
                if 'nextDueDate' in sub_data:
                    try:
                         company.next_due_date = datetime.strptime(sub_data['nextDueDate'], '%Y-%m-%d').date()
                    except:
                        pass
                
                db.session.commit()
                flash("Assinatura criada com sucesso.", "success")
            else:
                flash("Falha ao criar assinatura no Asaas.", "error")
                return redirect(url_for('master.company_details', company_id=company.id))
                
        # 4. Get Invoice URL
        payments = get_subscription_payments(company.subscription_id)
        if payments:
            invoice_url = payments[0]['invoiceUrl']
            return redirect(invoice_url)
        else:
            flash("Assinatura criada/ativa, mas o link do boleto ainda não foi gerado pelo Asaas. Tente novamente em instantes.", "warning")
            
        return redirect(url_for('master.dashboard')) # Redirect to dashboard list instead of details for flow usage
        
    except Exception as e:
        print(f"Generate Payment Error: {e}")
        flash(f"Erro interno: {str(e)}", "error")
        return redirect(url_for('master.company_details', company_id=company_id))



@master.route('/master/company/<int:company_id>/block', methods=['POST'])
@login_required
def company_block(company_id):
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    company = Company.query.get_or_404(company_id)
    company.platform_inoperante = True
    company.payment_status = 'blocked'
    db.session.commit()
    
    flash(f"Acesso da empresa {company.name} foi BLOQUEADO.", "success")
    return redirect(url_for('master.dashboard'))

@master.route('/master/company/<int:company_id>/unlock', methods=['POST'])
@login_required
def company_unlock(company_id):
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    company = Company.query.get_or_404(company_id)
    
    # Unlock Logic: Give 7 days or custom
    days = 5
    if request.form.get('days'):
        try:
            days = int(request.form.get('days'))
        except:
            pass
            
    from datetime import datetime, timedelta, date
    
    company.platform_inoperante = False
    company.payment_status = 'active' # Force active visually
    company.overdue_since = None # Clear overdue flag
    
    # Push next due date to future to prevent auto-block scripts from catching it immediately
    company.next_due_date = date.today() + timedelta(days=days)
    
    db.session.commit()
    
    flash(f"Acesso LIBERADO para {company.name} por {days} dias.", "success")
    return redirect(url_for('master.dashboard'))

@master.route('/master/company/<int:company_id>/manual-activate', methods=['POST'])
@login_required
def manual_activate(company_id):
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    company = Company.query.get_or_404(company_id)
    
    from datetime import date, timedelta
    
    # 1. Handle Asaas Subscription Cancellation (if requested or automatic)
    if company.subscription_id:
        try:
            from services.asaas_service import delete_subscription
            deleted, error = delete_subscription(company.subscription_id)
            if deleted:
                company.subscription_id = None
                company.payment_status = 'active'
                flash(f"Boleto/Assinatura Asaas cancelada automaticamente.", "info")
            else:
                flash(f"Aviso: Não foi possível cancelar o boleto Asaas: {error}", "warning")
        except Exception as e:
            print(f"Auto-cancel error: {e}")

    company.platform_inoperante = False
    company.payment_status = 'active'
    company.subscription_status = 'active'
    company.overdue_since = None
    
    # 2. Set Trial/Next Due Date (Customizable)
    days = 30 # Default
    if request.form.get('days'):
        try:
            days = int(request.form.get('days'))
        except:
            pass
            
    company.next_due_date = get_now_br().date() + timedelta(days=days)
    
    try:
        db.session.commit()
        flash(f"Empresa {company.name} ativada manualmente por {days} dias! Vencimento: {company.next_due_date.strftime('%d/%m/%Y')}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao ativar manualmente: {e}", "error")
        
    return redirect(url_for('master.company_details', company_id=company_id))


# --- Library Books Management ---
from models import LibraryBook, library_book_company_association

@master.route('/master/books')
def books():
    # List all library books
    books = LibraryBook.query.order_by(LibraryBook.created_at.desc()).all()
    return render_template('master_books.html', books=books, now=get_now_br())

@master.route('/master/books/new', methods=['GET', 'POST'])
def books_new():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        cover_image = request.form.get('cover_image')
        route_name = request.form.get('route_name')
        content = request.form.get('content')
        
        book = LibraryBook(
            title=title,
            description=description,
            category=category,
            cover_image=cover_image,
            route_name=route_name,
            content=content,
            active=True
        )
        
        # Access Permission
        allowed_company_ids = request.form.getlist('companies')
        for cid in allowed_company_ids:
            comp = Company.query.get(int(cid))
            if comp:
                book.allowed_companies.append(comp)
        
        db.session.add(book)
        db.session.commit()
        flash("Novo material adicionado à biblioteca!", "success")
        return redirect(url_for('master.books'))
        
    companies = Company.query.all()
    return render_template('master_book_form.html', companies=companies, book=None)

@master.route('/master/books/<int:id>/edit', methods=['GET', 'POST'])
def books_edit(id):
    book = LibraryBook.query.get_or_404(id)
    
    if request.method == 'POST':
        book.title = request.form['title']
        book.description = request.form['description']
        book.category = request.form['category']
        book.cover_image = request.form.get('cover_image')
        book.route_name = request.form.get('route_name')
        book.content = request.form.get('content')
        
        # Update permissions
        allowed_company_ids = request.form.getlist('companies')
        
        # Clear existing
        book.allowed_companies = []
        
        for cid in allowed_company_ids:
            comp = Company.query.get(int(cid))
            if comp:
                book.allowed_companies.append(comp)
                
        db.session.commit()
        flash("Material atualizado!", "success")
        return redirect(url_for('master.books'))
        
    companies = Company.query.all()
    return render_template('master_book_form.html', companies=companies, book=book)
@master.route('/master/library/new', methods=['GET', 'POST'])
@login_required
def master_library_new():
    from models import LibraryBook
    from datetime import datetime
    if not current_user.is_super_admin:
        abort(403)
        
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        description = request.form.get('description')
        cover_image = request.form.get('cover_image')
        content = request.form.get('content')
        
        book = LibraryBook(
            title=title,
            category=category,
            description=description,
            cover_image=cover_image,
            content=content,
            created_at=datetime.utcnow()
        )
        db.session.add(book)
        db.session.commit()
        flash(f"Material '{title}' criado com sucesso!", "success")
        return redirect(url_for('docs.library'))
        
    return render_template('master_library_edit.html', book=None)

@master.route('/master/library/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def master_library_edit(id):
    from models import LibraryBook
    if not current_user.is_super_admin:
        abort(403)
        
    book = LibraryBook.query.get_or_404(id)
    
    if request.method == 'POST':
        book.title = request.form.get('title')
        book.category = request.form.get('category')
        book.description = request.form.get('description')
        book.cover_image = request.form.get('cover_image')
        book.content = request.form.get('content')
        
        db.session.commit()
        flash(f"Material '{book.title}' atualizado!", "success")
        return redirect(url_for('docs.library'))
        
    return render_template('master_library_edit.html', book=book)

@master.route('/master/library/<int:id>/delete', methods=['POST'])
@login_required
def master_library_delete(id):
    from models import LibraryBook
    if not current_user.is_super_admin:
        abort(403)
        
    book = LibraryBook.query.get_or_404(id)
    title = book.title
    db.session.delete(book)
    db.session.commit()
    flash(f"Material '{title}' excluído.", "success")
    return redirect(url_for('docs.library'))

@master.route('/master/test-email', methods=['POST'])
@login_required
def test_email():
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    from services.email_service import EmailService
    
    # Simple test email
    to_email = current_user.email
    subject = "Teste de Integração NorthWay - Resend"
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
        <h2 style="color: #fa0102; text-align: center;">Conexão Bem-sucedida! 🚀</h2>
        <p>Olá, <strong>{current_user.name}</strong>,</p>
        <p>Este é um e-mail de teste disparado pelo seu CRM para validar a integração com o <strong>Resend</strong>.</p>
        <p>Se você está lendo isso, a chave de API e o domínio foram configurados corretamente.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #666; text-align: center;">Enviado por NorthWay Master Command Center.</p>
    </div>
    """
    
    success, result = EmailService.send_email(to_email, subject, html_content=html_content)
    
    if success:
        flash(f"E-mail de teste enviado para {to_email}!", "success")
    else:
        flash(f"Erro ao enviar e-mail: {result}", "error")
        
    return redirect(url_for('master.dashboard'))

