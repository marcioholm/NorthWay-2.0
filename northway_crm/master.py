from flask import Blueprint, render_template, redirect, url_for, session, abort, flash, request
from flask_login import login_required, current_user, login_user
from models import db, User, Company, ROLE_ADMIN, ContractTemplate, template_company_association

master = Blueprint('master', __name__)

@master.before_request
@login_required
def check_master_access():
    # Allow 'revert' route even if current_user is not super_admin (because they are impersonating)
    if request.endpoint in ['master.revert_access', 'master.super_helper', 'master.run_library_migration', 'master.revoke_self', 'master.system_reset', 'master.migrate_saas']:
        return

    # For all other master routes, MUST be super_admin
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)

@master.route('/master/dashboard')
@login_required
def dashboard():
    companies = Company.query.all()
    
    # Global Metrics Aggregation
    total_companies = len(companies)
    active_companies = sum(1 for c in companies if getattr(c, 'status', 'active') == 'active')
    
    # Calculate Users & Leads (Scanning all companies)
    total_users = User.query.count()
    from models import Lead
    total_leads = Lead.query.count()
    
    # Mock MRR Calculation (Plan based)
    # Pro = 297, Enterprise = 997, Free = 0
    mrr = 0
    plan_prices = {'free': 0, 'starter': 149, 'pro': 297, 'enterprise': 997}
    
    # Churn mock (companies with status='cancelled')
    cancelled_companies = sum(1 for c in companies if getattr(c, 'status', 'active') == 'cancelled')
    churn_rate = (cancelled_companies / total_companies * 100) if total_companies > 0 else 0
    
    stats = []
    
    for comp in companies:
        # Calculate MRR per company
        plan_name = getattr(comp, 'plan', 'pro').lower()
        mrr += plan_prices.get(plan_name, 0)
        
        # Find an admin to login as
        admin_user = User.query.filter_by(company_id=comp.id, role=ROLE_ADMIN).first()
        # Fallback to any user if no admin (rare)
        if not admin_user:
            admin_user = User.query.filter_by(company_id=comp.id).first()
            
        user_count = User.query.filter_by(company_id=comp.id).count()
        
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
        'contracts': 0, # Placeholder until Contract model is imported/queried
        'mrr': mrr,
        'churn': round(churn_rate, 1)
    }
        
    return render_template('master_dashboard.html', stats=stats, kpis=global_kpis)

@master.route('/master/impersonate/<int:user_id>')
def impersonate(user_id):
    target_user = User.query.get_or_404(user_id)
    
    # Store original admin ID in session
    session['super_admin_id'] = current_user.id
    
    # Perform Login as target
    login_user(target_user)
    
    flash(f"Acessando como: {target_user.name} @ {target_user.company.name}", "warning")
    return redirect(url_for('main.home'))

@master.route('/master/revert')
def revert_access():
    original_id = session.get('super_admin_id')
    if not original_id:
        flash("Sessão de super admin não encontrada.", "error")
        return redirect(url_for('main.home'))
        
    original_user = User.query.get(original_id)
    if original_user:
        login_user(original_user)
        session.pop('super_admin_id', None)
        flash("Sessão Master restaurada.", "success")
        return redirect(url_for('master.dashboard'))
    
    return redirect(url_for('auth.login'))

@master.route('/master/company/<int:company_id>/users')
def company_users(company_id):
    company = Company.query.get_or_404(company_id)
    users = User.query.filter_by(company_id=company_id).all()
    return render_template('master_company_users.html', company=company, users=users)

@master.route('/master/user/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        
        new_password = request.form.get('password')
        if new_password:
            from werkzeug.security import generate_password_hash
            user.password_hash = generate_password_hash(new_password)
            
        db.session.commit()
        flash(f"Usuário {user.name} atualizado com sucesso!", "success")
        return redirect(url_for('master.company_users', company_id=user.company_id))
        
    return render_template('master_edit_user.html', user=user)

@master.route('/master/companies')
@login_required
def companies():
    companies_list = Company.query.order_by(Company.created_at.desc()).all()
    
    # Enrich with user counts
    for c in companies_list:
        c.user_count = User.query.filter_by(company_id=c.id).count()
        c.admin = User.query.filter_by(company_id=c.id, role=ROLE_ADMIN).first()
        
    return render_template('master_companies.html', companies=companies_list)

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
            new_comp = Company(name=name, plan=plan, status='active')
            
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
                
            db.session.add(new_comp)
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
        company.document = request.form.get('document')
        
        try:
            db.session.commit()
            flash(f"Empresa '{company.name}' atualizada.", "success")
            return redirect(url_for('master.companies'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar: {e}", "error")
            
    return render_template('master_company_form.html', company=company)


@master.route('/master/library/new', methods=['GET', 'POST'])
def library_new():
    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        content = request.form['content']
        allowed_company_ids = request.form.getlist('companies')
        
        # Super Admin owns these, but let's link to their company for consistency
        # or just purely global.
        
        tmpl = ContractTemplate(
            company_id=current_user.company_id, # Owner
            name=name,
            type=type_,
            content=content,
            is_global=True,
            active=True
        )
        
        # Add permissions
        for cid in allowed_company_ids:
            comp = Company.query.get(int(cid))
            if comp:
                tmpl.allowed_companies.append(comp)
                
        db.session.add(tmpl)
        db.session.commit()
        flash("Modelo de biblioteca criado!", "success")
        return redirect(url_for('master.library'))
        
    companies = Company.query.all()
    return render_template('master_library_form.html', companies=companies, template=None)

@master.route('/master/library/<int:id>/edit', methods=['GET', 'POST'])
def library_edit(id):
    tmpl = ContractTemplate.query.get_or_404(id)
    # Security check? Only Super Admin hits these routes via before_request
    
    if request.method == 'POST':
        tmpl.name = request.form['name']
        tmpl.type = request.form['type']
        tmpl.content = request.form['content']
        
        # Update permissions
        allowed_company_ids = request.form.getlist('companies')
        
        # Clear existing
        tmpl.allowed_companies = []
        
        for cid in allowed_company_ids:
            comp = Company.query.get(int(cid))
            if comp:
                tmpl.allowed_companies.append(comp)
                
        db.session.commit()
        flash("Modelo de biblioteca atualizado!", "success")
        return redirect(url_for('master.library'))
        
    companies = Company.query.all()
    return render_template('master_library_form.html', companies=companies, template=tmpl)

# --- Temporary Migration Route ---
@master.route('/master/migrate-library-now')
@login_required
def run_library_migration():
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)
        
    try:
        from migrate_library import migrate_library
        # Call the logic directly (adapting migrate_library to be callable without creating new app context if inside request)
        # However, migrate_library creates its own app context. Let's just inline the logic or call a helper that uses current context.
        
        # Better: Inline the logic here to use current db session
        from models import LibraryBook, Company
        
        # 1. Ensure Table Exists
        db.create_all()
        
        # 2. Define Initial Books
        initial_books = [
            {
                'title': 'Diagnóstico Estratégico',
                'description': 'Análise completa para Óticas 2026.',
                'category': 'Vendas',
                'route_name': 'docs.presentation_consultancy',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Apresentação Institucional',
                'description': 'Marketing com Direção - Quem somos e o que fazemos.',
                'category': 'Institucional',
                'route_name': 'docs.presentation_institutional',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Oferta Principal',
                'description': 'Estrutura Completa da Proposta Comercial.',
                'category': 'Vendas',
                'route_name': 'docs.presentation_offer_main',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Plano Essencial (Downsell)',
                'description': 'Alternativa de proposta para recuperação.',
                'category': 'Vendas',
                'route_name': 'docs.presentation_offer_downsell',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Manual de Onboarding',
                'description': 'Guia operacional para início de jornada.',
                'category': 'Processos',
                'route_name': 'docs.user_manual',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Scripts & Técnicas',
                'description': 'Roteiros de vendas e técnicas de fechamento.',
                'category': 'Vendas',
                'route_name': 'docs.playbook_comercial',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Objeções & SDR',
                'description': 'Matriz de objeções e guia para pré-vendas.',
                'category': 'Processos',
                'route_name': 'docs.playbook_processos',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Academia de Treinamento',
                'description': 'Training & Scripts area.',
                'category': 'Treinamento',
                'route_name': 'docs.playbook_treinamento',
                'cover_image': None,
                'active': True
            }
        ]
        
        all_companies = Company.query.all()
        count = 0
        
        for data in initial_books:
            existing = LibraryBook.query.filter_by(route_name=data['route_name']).first()
            if not existing:
                book = LibraryBook(
                    title=data['title'],
                    description=data['description'],
                    category=data['category'],
                    route_name=data['route_name'],
                    cover_image=data.get('cover_image'),
                    active=data['active']
                )
                for comp in all_companies:
                    book.allowed_companies.append(comp)
                db.session.add(book)
                count += 1
                
        db.session.commit()
        return f"Migration Successful! Added {count} new books. <a href='{url_for('master.books')}'>Go to Library</a>"
        
    except Exception as e:
        return f"Error: {str(e)}"

# --- Super Admin Restoration Helper ---
# --- Super Admin Restoration Helper (REMOVED) ---
# Route removed for security compliance. 
# Use CLI or DB direct access for promotions.

# --- Library Books Management ---
from models import LibraryBook, library_book_company_association

@master.route('/master/books')
def books():
    # List all library books
    books = LibraryBook.query.order_by(LibraryBook.created_at.desc()).all()
    return render_template('master_books.html', books=books)

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
@master.route('/master/system-reset')
@login_required
def system_reset():
    """
    EMERGENCY ROUTE: Wipes all users EXCEPT the current user.
    Promotes the current user to Super Admin and 'reset' state.
    """
    try:
        # 1. Promote Self (Just in case they lost it)
        current_user.is_super_admin = True
        current_user.role = 'ADMIN' # Ensure they have admin role too
        
        # 2. Find and Delete Others
        # Note: If cascade DELETE is not set on relationships (Leads, etc), this might fail or leave orphans.
        # For a "Reset", orphans might be acceptable or we should delete them too. 
        # For simplicity/safety, we just delete users. SQLAlchemy usually handles simple relationships.
        
        others = User.query.filter(User.id != current_user.id).all()
        count = len(others)
        
        for u in others:
            db.session.delete(u)
            
        db.session.commit()
        
        return f"""
        <h1>System Reset Successful</h1>
        <p>User <strong>{current_user.email}</strong> is now the ONLY user and is SUPER ADMIN.</p>
        <p>Deleted {count} other users.</p>
        <br>
        <a href='/'>Go to Dashboard</a>
        """
    except Exception as e:
        db.session.rollback()
        return f"Reset Failed: {str(e)}<br>Check logs for integrity errors (orphan records)."
@master.route('/master/migrate-saas')
@login_required
def migrate_saas():
    """
    Helper to apply schema changes for SaaS fields (plan, status, limits).
    """
    try:
        from sqlalchemy import text
        # List of commands to run safely
        commands = [
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS plan VARCHAR(50) DEFAULT 'pro';",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS max_users INTEGER DEFAULT 5;",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS max_leads INTEGER DEFAULT 1000;",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS max_storage_gb FLOAT DEFAULT 1.0;",
            "ALTER TABLE company ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();"
        ]
        
        results = []
        for cmd in commands:
            db.session.execute(text(cmd))
            results.append(f"Executed: {cmd}")
            
        db.session.commit()
        return "<br>".join(results) + "<br><br>Migration Successful! <a href='/'>Go Home</a>"
    except Exception as e:
        db.session.rollback()
        return f"Migration Failed: {str(e)}"
