from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
# Defer model imports to avoid circular dependency with app initialization
# from models import db, User, Role, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES
from werkzeug.security import generate_password_hash

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
    if not current_user.has_permission('admin_view') and current_user.role.lower() != 'admin':
        abort(403)

@admin_bp.route('/admin/users')
def users():
    from models import User, Role # Lazy Import
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
        flash('Usuário criado com sucesso!', 'success')
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
        
        # Logo handled via separate logic or app context if needed
        # For now, keep it simple as app.py had logic involving app.config
    
        db.session.commit()
        flash('Configurações da empresa atualizadas!', 'success')
        return redirect(url_for('admin.company_settings'))
    
    return render_template('company_settings.html', company=company)

@admin_bp.route('/settings/integrations', methods=['GET', 'POST'])
def settings_integrations():
    from models import db, Integration
    import json
    
    if request.method == 'POST':
        service = request.form.get('service')
        api_key = request.form.get('api_key')
        if service and api_key:
            intg = Integration.query.filter_by(company_id=current_user.company_id, service=service).first()
            if not intg:
                intg = Integration(company_id=current_user.company_id, service=service)
                db.session.add(intg)
            intg.api_key = api_key
            intg.is_active = True
            db.session.commit()
            flash('Integração salva!', 'success')
        return redirect(url_for('admin.settings_integrations'))

    integrations = Integration.query.filter_by(company_id=current_user.company_id).all()
    integrations_map = {i.service: i for i in integrations}
    
    zapi_config = {}
    if 'z_api' in integrations_map:
        try: zapi_config = json.loads(integrations_map['z_api'].config_json or '{}')
        except: pass
        
    return render_template('settings_integrations.html', company=current_user.company, integrations_map=integrations_map, zapi_config=zapi_config)

@admin_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    from models import db
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.phone = request.form.get('phone')
        current_user.status_message = request.form.get('status_message')
        
        password = request.form.get('password')
        if password:
            current_user.password_hash = generate_password_hash(password)
            
        db.session.commit()
        flash('Perfil atualizado!', 'success')
        return redirect(url_for('admin.profile'))
        
    return render_template('profile.html', user=current_user)

@admin_bp.route('/settings')
@login_required
def settings_index():
    return redirect(url_for('admin.profile'))
