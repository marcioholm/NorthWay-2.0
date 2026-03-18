from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, ContractTemplate, ROLE_ADMIN, AutomationRule, Pipeline, PipelineStage
from datetime import datetime

templates_bp = Blueprint('templates', __name__)

@templates_bp.route('/settings/templates')
@login_required
def settings_templates():
    if not current_user.company_id:
        abort(403)

    if current_user.role != ROLE_ADMIN:
        abort(403)
    
    # SUPER ADMIN: Sees everything
    if getattr(current_user, 'is_super_admin', False):
        all_templates = ContractTemplate.query.all()
        return render_template('settings_templates.html', templates=all_templates)

    # Standard Admin: Get company templates
    company_templates = ContractTemplate.query.filter(ContractTemplate.company_id == current_user.company_id).all()
    
    # Get global templates
    global_templates = ContractTemplate.query.filter_by(is_global=True).all()
    
    # Get library templates (Shared with this company)
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
    is_super = getattr(current_user, 'is_super_admin', False)
    
    if not is_super and template.company_id != current_user.company_id and not template.is_global:
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
    is_super = getattr(current_user, 'is_super_admin', False)
    
    if not is_super and template.company_id != current_user.company_id:
        abort(403)
        
    db.session.delete(template)
    db.session.commit()
    flash('Template excluído.', 'success')
    return redirect(url_for('templates.settings_templates'))

@templates_bp.route('/settings/templates/<int:id>/duplicate', methods=['POST'])
@login_required
def duplicate_template(id):
    if not current_user.company_id:
        abort(403)

    if current_user.role != ROLE_ADMIN:
        abort(403)

    source_template = ContractTemplate.query.get_or_404(id)
    
    # Security check: Must be same company OR global OR library (shared)
    is_super = getattr(current_user, 'is_super_admin', False)
    has_access = is_super or source_template.company_id == current_user.company_id or source_template.is_global
    
    if not has_access:
        # Check library association
        from models import template_company_association
        lib_access = db.session.query(template_company_association).filter_by(
            template_id=id, company_id=current_user.company_id
        ).first()
        if not lib_access:
            abort(403)

    new_template = ContractTemplate(
        name=f"{source_template.name} (Cópia)",
        description=source_template.description,
        content=source_template.content,
        type=source_template.type,
        company_id=current_user.company_id,
        is_library=False, # Copy becomes a private template
        is_global=False,  # Copy becomes a private template
        created_at=datetime.now()
    )
    
    db.session.add(new_template)
    db.session.commit()
    
    flash('Modelo duplicado com sucesso!', 'success')
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

@templates_bp.route('/settings/drive-templates')
@login_required
def settings_drive_templates():
    from models import DriveFolderTemplate, Company
    
    if not current_user.company_id:
        abort(403)
        
    # 1. Get Tenant Templates
    my_templates = DriveFolderTemplate.query.filter_by(
        company_id=current_user.company_id,
        scope='tenant'
    ).all()
    
    # 2. Get Allowed Global Templates
    # Start with all global enabled
    all_global = DriveFolderTemplate.query.filter_by(scope='global', enabled=True).all()
    
    # Filter by company.allowed_global_template_ids
    # If allowed_ids is empty/None, user sees NOTHING (or potentially "Universal" if logic dictates, but we stick to strict Allow List)
    allowed_ids = current_user.company.allowed_global_template_ids or []
    
    available_global_templates = [t for t in all_global if t.id in allowed_ids]
    
    return render_template('settings_drive_templates.html', 
                           my_templates=my_templates, 
                           global_templates=available_global_templates)

@templates_bp.route('/settings/drive-templates/duplicate/<int:id>', methods=['POST'])
@login_required
def duplicate_drive_template(id):
    from models import db, DriveFolderTemplate
    import json
    
    if not current_user.company_id:
        abort(403)
        
    global_template = DriveFolderTemplate.query.get_or_404(id)
    
    # Security check: Must be allowed
    allowed_ids = current_user.company.allowed_global_template_ids or []
    if global_template.id not in allowed_ids or global_template.scope != 'global':
        flash('Você não tem permissão para copiar este template.', 'error')
        return redirect(url_for('templates.settings_drive_templates'))
        
    # Create copy
    new_template = DriveFolderTemplate(
        name=f"{global_template.name} (Cópia)",
        structure_json=global_template.structure_json,
        scope='tenant',
        company_id=current_user.company_id,
        enabled=True,
        is_default=False
    )
    
    db.session.add(new_template)
    db.session.commit()
    
    flash('Template duplicado com sucesso! Agora você pode editá-lo em "Meus Templates".', 'success')
    return redirect(url_for('templates.settings_drive_templates'))

@templates_bp.route('/settings/drive-templates/delete/<int:id>', methods=['POST'])
@login_required
def delete_drive_template(id):
    from models import db, DriveFolderTemplate
    
    template = DriveFolderTemplate.query.get_or_404(id)
    
    if template.company_id != current_user.company_id:
        abort(403)
        
    db.session.delete(template)
    db.session.commit()
    
    flash('Template excluído.', 'success')
    return redirect(url_for('templates.settings_drive_templates'))

@templates_bp.route('/settings/drive-templates/create', methods=['POST'])
@login_required
def create_drive_template():
    from models import db, DriveFolderTemplate
    
    if not current_user.company_id:
        abort(403)
    
    name = request.form.get('name')
    structure_json = request.form.get('structure_json')
    
    # Validate JSON
    try:
        import json
        json.loads(structure_json)
    except:
        flash('Estrutura JSON inválida. Verifique o formato.', 'error')
        return redirect(url_for('templates.settings_drive_templates'))
    
    new_template = DriveFolderTemplate(
        name=name,
        structure_json=structure_json,
        scope='tenant',
        company_id=current_user.company_id,
        enabled=True,
        is_default=False
    )
    
    db.session.add(new_template)
    db.session.commit()
    
    flash('Template criado com sucesso!', 'success')
    return redirect(url_for('templates.settings_drive_templates'))

@templates_bp.route('/settings/drive-templates/<int:id>/update', methods=['POST'])
@login_required
def update_drive_template(id):
    from models import db, DriveFolderTemplate
    
    template = DriveFolderTemplate.query.get_or_404(id)
    
    if template.company_id != current_user.company_id:
        abort(403)
    
    name = request.form.get('name')
    structure_json = request.form.get('structure_json')
    
    # Validate JSON
    try:
        import json
        json.loads(structure_json)
    except:
        flash('Estrutura JSON inválida. Verifique o formato.', 'error')
        return redirect(url_for('templates.settings_drive_templates'))
    
    template.name = name
    template.structure_json = structure_json
    
    db.session.commit()
    
    flash('Template atualizado com sucesso!', 'success')
    return redirect(url_for('templates.settings_drive_templates'))


@templates_bp.route('/settings/automations')
@login_required
def settings_automations():
    if current_user.role != ROLE_ADMIN:
        abort(403)
    
    rules_query = AutomationRule.query.filter_by(company_id=current_user.company_id).all()
    rules = []
    for r in rules_query:
        rules.append({
            'id': r.id,
            'name': r.name,
            'company_id': r.company_id,
            'pipeline_id': r.pipeline_id,
            'stage_id': r.stage_id,
            'trigger_type': r.trigger_type,
            'target_day': r.target_day,
            'action_type': r.action_type,
            'message_template': r.message_template,
            'description_template': r.description_template,
            'priority': r.priority,
            'delay_hours': r.delay_hours,
            'active': r.active,
            'created_at_display': r.created_at.strftime('%d/%m/%Y') if r.created_at else ''
        })
    
    pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
    stages = PipelineStage.query.filter_by(company_id=current_user.company_id).all()
    
    return render_template('settings_automations.html', 
                           rules=rules, 
                           pipelines=pipelines,
                           stages=stages)

@templates_bp.route('/settings/automations/new', methods=['POST'])
@login_required
def new_automation():
    if current_user.role != ROLE_ADMIN:
        abort(403)
        
    name = request.form.get('name')
    pipeline_id = request.form.get('pipeline_id')
    stage_id = request.form.get('stage_id')
    trigger_type = request.form.get('trigger_type', 'stage_entry')
    target_day = request.form.get('target_day')
    action_type = request.form.get('action_type', 'whatsapp')
    message_template = request.form.get('message_template')
    description_template = request.form.get('description_template')
    priority = request.form.get('priority', 'media')
    delay_hours = request.form.get('delay_hours', 0)
    
    rule = AutomationRule(
        name=name,
        company_id=current_user.company_id,
        pipeline_id=pipeline_id if pipeline_id else None,
        stage_id=stage_id if stage_id else None,
        trigger_type=trigger_type,
        target_day=int(target_day) if target_day else None,
        action_type=action_type,
        message_template=message_template,
        description_template=description_template,
        priority=priority,
        delay_hours=int(delay_hours) if delay_hours else 0,
        active=True
    )
    db.session.add(rule)
    db.session.commit()
    
    flash('Regra de automação criada com sucesso!', 'success')
    return redirect(url_for('templates.settings_automations'))

@templates_bp.route('/settings/automations/<int:id>/edit', methods=['POST'])
@login_required
def edit_automation(id):
    if current_user.role != ROLE_ADMIN:
        abort(403)
        
    rule = AutomationRule.query.get_or_404(id)
    if rule.company_id != current_user.company_id:
        abort(403)
        
    rule.name = request.form.get('name')
    rule.pipeline_id = request.form.get('pipeline_id') if request.form.get('pipeline_id') else None
    rule.stage_id = request.form.get('stage_id') if request.form.get('stage_id') else None
    rule.trigger_type = request.form.get('trigger_type', 'stage_entry')
    
    target_day = request.form.get('target_day')
    rule.target_day = int(target_day) if target_day else None
    
    rule.action_type = request.form.get('action_type', 'whatsapp')
    rule.message_template = request.form.get('message_template')
    rule.description_template = request.form.get('description_template')
    rule.priority = request.form.get('priority', 'media')
    
    delay_hours = request.form.get('delay_hours', 0)
    rule.delay_hours = int(delay_hours) if delay_hours else 0
    
    rule.active = 'active' in request.form
    
    db.session.commit()
    flash('Automação atualizada!', 'success')
    return redirect(url_for('templates.settings_automations'))

@templates_bp.route('/settings/automations/<int:id>/delete', methods=['POST'])
@login_required
def delete_automation(id):
    if current_user.role != ROLE_ADMIN:
        abort(403)
        
    rule = AutomationRule.query.get_or_404(id)
    if rule.company_id != current_user.company_id:
        abort(403)
        
    db.session.delete(rule)
    db.session.commit()
    flash('Automação removida!', 'success')
    return redirect(url_for('templates.settings_automations'))

