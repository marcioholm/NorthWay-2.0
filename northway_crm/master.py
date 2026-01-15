from flask import Blueprint, render_template, redirect, url_for, session, abort, flash, request
from flask_login import login_required, current_user, login_user
from models import db, User, Company, ROLE_ADMIN, ContractTemplate, template_company_association

master = Blueprint('master', __name__)

@master.before_request
@login_required
def check_master_access():
    # Allow 'revert' route even if current_user is not super_admin (because they are impersonating)
    if request.endpoint == 'master.revert_access':
        return

    # For all other master routes, MUST be super_admin
    if not getattr(current_user, 'is_super_admin', False):
        abort(403)

@master.route('/master/dashboard')
def dashboard():
    companies = Company.query.all()
    stats = []
    
    for comp in companies:
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
        
    return render_template('master_dashboard.html', stats=stats)

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

@master.route('/master/library')
def library():
    # List global/system templates
    templates = ContractTemplate.query.filter_by(is_global=True).all()
    return render_template('master_library.html', templates=templates)

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
