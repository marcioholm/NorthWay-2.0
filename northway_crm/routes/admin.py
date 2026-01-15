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
