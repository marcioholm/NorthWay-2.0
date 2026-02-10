from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, Role, User, ROLE_ADMIN

roles_bp = Blueprint('roles', __name__)

@roles_bp.route('/settings/permissions')
@login_required
def settings_permissions():
    # Security Check: Ensure safe access to user_role properties
    is_admin = False
    
    # 1. Check Legacy Role String
    if current_user.role == ROLE_ADMIN:
        is_admin = True
        
    # 2. Check RBAC Role Object
    if current_user.user_role:
        if current_user.user_role.name == 'Administrador':
            is_admin = True
        elif 'manage_team' in (current_user.user_role.permissions or []):
            is_admin = True
            
    if not is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard.home'))

    # Fetch roles for this company
    roles = Role.query.filter_by(company_id=current_user.company_id).all()
    
    # Standard Permission Definitions
    available_permissions = {
        'dashboard': {
            'dashboard_view': 'Visualizar Dashboard',
            'financial_view': 'Visualizar Financeiro'
        },
        'sales': {
            'leads_view': 'Gerenciar Leads',
            'pipeline_view': 'Acessar Pipeline',
            'clients_view': 'Gerenciar Clientes',
            'contracts_view': 'Gerenciar Contratos'
        },
        'operations': {
            'tasks_view': 'Gerenciar Tarefas',
            'goals_view': 'Visualizar Metas',
            'processes_view': 'Gerenciar Processos',
            'library_view': 'Acessar Biblioteca'
        },
        'admin': {
            'manage_team': 'Gerenciar Equipe',
            'company_settings_view': 'Configurações da Empresa', 
            'admin_view': 'Administração Total'
        }
    }
    
    # Feature Conditional Permissions
    if current_user.company.has_feature('prospecting'):
        available_permissions['sales']['prospecting_view'] = 'Prospecção'
        
    if current_user.company.has_feature('whatsapp'):
        available_permissions['operations']['whatsapp_view'] = 'Acessar WhatsApp'
    
    category_labels = {
        'dashboard': 'Visão Geral',
        'sales': 'Vendas',
        'operations': 'Operações',
        'admin': 'Administrativo'
    }
    
    return render_template('settings_permissions.html', 
                           roles=roles, 
                           available_permissions=available_permissions,
                           category_labels=category_labels)

@roles_bp.route('/settings/roles/new', methods=['POST'])
@login_required
def create_role():
    if current_user.role != ROLE_ADMIN and (not current_user.user_role or 'manage_team' not in (current_user.user_role.permissions or [])):
        abort(403)
        
    name = request.form.get('name')
    if not name:
        flash('Nome do cargo é obrigatório.', 'error')
        return redirect(url_for('roles.settings_permissions'))
        
    new_role = Role(name=name, company_id=current_user.company_id, permissions=[])
    db.session.add(new_role)
    db.session.commit()
    
    flash('Cargo criado com sucesso!', 'success')
    return redirect(url_for('roles.settings_permissions'))

@roles_bp.route('/settings/roles/<int:id>/update', methods=['POST'])
@login_required
def update_role(id):
    role = Role.query.get_or_404(id)
    if role.company_id != current_user.company_id:
        abort(403)
        
    if current_user.role != ROLE_ADMIN and (not current_user.user_role or 'manage_team' not in (current_user.user_role.permissions or [])):
        abort(403)
        
    role.name = request.form.get('name')
    # Get list of selected permissions
    perms = request.form.getlist('permissions[]')
    role.permissions = perms
    
    db.session.commit()
    flash('Permissões atualizadas.', 'success')
    return redirect(url_for('roles.settings_permissions'))

@roles_bp.route('/settings/roles/<int:id>/delete', methods=['POST'])
@login_required
def delete_role(id):
    role = Role.query.get_or_404(id)
    if role.company_id != current_user.company_id:
        abort(403)
        
    if role.is_default:
        flash('Cargos padrão não podem ser excluídos.', 'error')
        return redirect(url_for('roles.settings_permissions'))
        
    if len(role.users) > 0:
        flash('Não é possível excluir cargo com usuários vinculados.', 'error')
        return redirect(url_for('roles.settings_permissions'))
        
    db.session.delete(role)
    db.session.commit()
    flash('Cargo excluído.', 'success')
    return redirect(url_for('roles.settings_permissions'))
