from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, ContractTemplate, ROLE_ADMIN
from datetime import datetime

templates_bp = Blueprint('templates', __name__)

@templates_bp.route('/settings/templates')
@login_required
def settings_templates():
    if not current_user.company_id:
        abort(403)

    if current_user.role != ROLE_ADMIN:
        abort(403)
    
    # Get company templates
    company_templates = ContractTemplate.query.filter(ContractTemplate.company_id == current_user.company_id).all()
    
    # Get global templates
    global_templates = ContractTemplate.query.filter_by(is_global=True).all()
    
    # Get library templates (Shared with this company)
    # This involves the association table
    from models import template_company_association
    library_templates = ContractTemplate.query.join(template_company_association)\
                                             .filter(template_company_association.c.company_id == current_user.company_id).all()
    
    return render_template('settings_templates.html', 
                           templates=company_templates + global_templates + library_templates)

@templates_bp.route('/settings/templates/new', methods=['GET', 'POST'])
@login_required
def new_template():
    if not current_user.company_id:
        abort(403)

    if current_user.role != ROLE_ADMIN:
        abort(403)
        
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        content = request.form.get('content')
        template_type = request.form.get('type', 'contract')
        is_library = request.form.get('is_library') == 'on'
        
        template = ContractTemplate(
            name=name,
            description=description,
            content=content,
            type=template_type,
            company_id=current_user.company_id,
            is_library=is_library,
            created_at=datetime.now()
        )
        db.session.add(template)
        db.session.commit()
        flash('Template criado com sucesso!', 'success')
        return redirect(url_for('templates.settings_templates'))
        
    return render_template('settings_template_edit.html', template=None)

@templates_bp.route('/settings/templates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    template = ContractTemplate.query.get_or_404(id)
    if template.company_id != current_user.company_id and not template.is_global:
        abort(403)
        
    if request.method == 'POST':
        if template.is_global and current_user.company_id != template.company_id:
             flash('Templates globais não podem ser editados por outras empresas.', 'error')
             return redirect(url_for('templates.settings_templates'))

        template.name = request.form.get('name')
        template.description = request.form.get('description')
        template.content = request.form.get('content')
        template.type = request.form.get('type')
        template.is_library = request.form.get('is_library') == 'on'
        
        db.session.commit()
        flash('Template atualizado!', 'success')
        return redirect(url_for('templates.settings_templates'))
        
    return render_template('settings_template_edit.html', template=template)

@templates_bp.route('/settings/templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    template = ContractTemplate.query.get_or_404(id)
    if template.company_id != current_user.company_id:
        abort(403)
        
    db.session.delete(template)
    db.session.commit()
    flash('Template excluído.', 'success')
    return redirect(url_for('templates.settings_templates'))

@templates_bp.route('/settings/processes')
@login_required
def settings_processes():
    from models import ProcessTemplate
    if current_user.role != 'admin':
         # Check permissions via RBAC
         can_manage = current_user.user_role and (current_user.user_role.name in ['Administrador', 'Gestor', 'admin'] or 'manage_settings' in (current_user.user_role.permissions or []))
         if not can_manage:
              flash('Acesso negado.', 'error')
              return redirect(url_for('dashboard.home'))
    
    if not current_user.company_id:
         abort(403)

    templates = ProcessTemplate.query.filter(ProcessTemplate.company_id == current_user.company_id).all()
    return render_template('settings_processes.html', templates=templates)

@templates_bp.route('/settings/processes/new', methods=['POST'])
@login_required
def create_process_template():
    if not current_user.company_id:
        abort(403)

    from models import db, ProcessTemplate
    name = request.form.get('name')
    description = request.form.get('description')
    steps = [{"title": "Etapa 1", "items": ["Item A"]}]
    
    template = ProcessTemplate(name=name, description=description, steps=steps, company_id=current_user.company_id)
    db.session.add(template)
    db.session.commit()
    flash('Modelo de processo criado.', 'success')
    return redirect(url_for('templates.edit_process_template', id=template.id))

@templates_bp.route('/settings/processes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_process_template(id):
    from models import db, ProcessTemplate
    import json
    template = ProcessTemplate.query.get_or_404(id)
    if template.company_id != current_user.company_id:
        abort(403)
    
    if request.method == 'POST':
        template.name = request.form.get('name')
        template.description = request.form.get('description')
        try:
            template.steps = json.loads(request.form.get('steps_json'))
            db.session.commit()
            flash('Processo salvo!', 'success')
        except:
            flash('Erro no JSON.', 'error')
        return redirect(url_for('templates.edit_process_template', id=id))
    
    return render_template('settings_process_edit.html', template=template)

@templates_bp.route('/settings/processes/<int:id>/delete', methods=['POST'])
@login_required
def delete_process_template(id):
    from models import db, ProcessTemplate
    template = ProcessTemplate.query.get_or_404(id)
    if template.company_id != current_user.company_id:
        abort(403)
    db.session.delete(template)
    db.session.commit()
    flash('Modelo excluído.', 'success')
    return redirect(url_for('templates.settings_processes'))
