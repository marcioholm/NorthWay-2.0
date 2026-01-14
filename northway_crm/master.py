from flask import Blueprint, render_template, redirect, url_for, session, abort, flash, request
from flask_login import login_required, current_user, login_user
from models import db, User, Company, ROLE_ADMIN

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
