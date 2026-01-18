from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Lead, Client, Pipeline, PipelineStage, ProcessTemplate, ClientChecklist, Task, Interaction, WhatsAppMessage, LEAD_STATUS_WON, LEAD_STATUS_NEW, LEAD_STATUS_IN_PROGRESS, LEAD_STATUS_LOST
from utils import create_notification
from datetime import datetime, timedelta

leads_bp = Blueprint('leads', __name__)

@leads_bp.route('/leads')
@login_required
def leads():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    query = Lead.query.filter_by(company_id=current_user.company_id)
    
    # Filters
    status = request.args.get('status')
    source = request.args.get('source')
    assigned_to = request.args.get('assigned_to')
    
    if status:
        query = query.filter_by(status=status)
    if source:
        query = query.filter_by(source=source)
    if assigned_to:
        query = query.filter_by(assigned_to_id=int(assigned_to))
        
    pagination = query.options(
        db.joinedload(Lead.assigned_user),
        db.joinedload(Lead.pipeline_stage)
    ).order_by(Lead.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    leads_list = pagination.items
    
    from models import User # Lazy import
    users = User.query.filter_by(company_id=current_user.company_id).all()
    
    return render_template('leads.html', leads=leads_list, pagination=pagination, users=users)

@leads_bp.route('/leads/<int:id>')
@login_required
def lead_details(id):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
    return render_template('lead_details.html', lead=lead)

@leads_bp.route('/pipeline')
@leads_bp.route('/pipeline/<int:pipeline_id>')
@login_required
def pipeline(pipeline_id=None):
    # Get current company's pipelines
    pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
    
    if not pipelines:
        # Create a default pipeline if none exists
        default_p = Pipeline(name="Pipeline Comercial", company_id=current_user.company_id)
        db.session.add(default_p)
        db.session.flush()
        
        # Create default stages
        stages = ["Qualificação", "Apresentação", "Proposta", "Negociação", "Fechado"]
        for i, s_name in enumerate(stages):
            stage = PipelineStage(name=s_name, pipeline_id=default_p.id, company_id=current_user.company_id, order_index=i)
            db.session.add(stage)
        
        db.session.commit()
        pipelines = [default_p]
        pipeline_id = default_p.id
    
    if not pipeline_id:
        pipeline_id = pipelines[0].id
        
    current_pipeline = Pipeline.query.get_or_404(pipeline_id)
    if current_pipeline.company_id != current_user.company_id:
        abort(403)
        
    stages = PipelineStage.query.filter_by(pipeline_id=pipeline_id).order_by(PipelineStage.order_index).all()
    leads_list = Lead.query.filter_by(pipeline_id=pipeline_id, company_id=current_user.company_id)\
                        .options(db.joinedload(Lead.assigned_user))\
                        .all()
        
    return render_template('pipeline.html', 
                          pipelines=pipelines, 
                          active_pipeline=current_pipeline, 
                          stages=stages, 
                          leads=leads_list)

@leads_bp.route('/leads/<int:id>/move/\u003cdirection\u003e', methods=['POST'])
@login_required
def move_lead(id, direction):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
        
    stages = PipelineStage.query.filter_by(pipeline_id=lead.pipeline_id).order_by(PipelineStage.order_index).all()
    current_idx = next((i for i, s in enumerate(stages) if s.id == lead.pipeline_stage_id), 0)
    
    if direction == 'next' and current_idx < len(stages) - 1:
        lead.pipeline_stage_id = stages[current_idx + 1].id
        lead.status = LEAD_STATUS_IN_PROGRESS
    elif direction == 'prev' and current_idx > 0:
        lead.pipeline_stage_id = stages[current_idx - 1].id

    db.session.commit()
    return redirect(url_for('leads.pipeline', pipeline_id=lead.pipeline_id))

@leads_bp.route('/leads/\u003cint:id\u003e/convert', methods=['POST'])
@login_required
def convert_lead(id):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
        
    service = request.form.get('service')
    contract_type = request.form.get('contract_type')
    start_date_str = request.form.get('start_date')
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else datetime.utcnow().date()
    renewal_date = start_date + timedelta(days=30)
    
    monthly_value = request.form.get('monthly_value')
    value = 0.0
    try:
        if monthly_value:
            clean_value = monthly_value.replace('R$', '').replace('.', '').replace(',', '.').strip()
            value = float(clean_value)
    except ValueError:
        pass

    client = Client(
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        company_id=lead.company_id,
        account_manager_id=lead.assigned_to_id or current_user.id,
        lead_id=lead.id,
        status='onboarding',
        health_status='verde',
        service=service,
        contract_type=contract_type,
        monthly_value=value,
        start_date=start_date,
        renewal_date=renewal_date,
        notes=f"Convertido de Lead em {start_date.strftime('%d/%m/%Y')}. \n{lead.notes or ''}",
        niche=lead.bant_need
    )
    
    db.session.add(client)
    db.session.flush()
    
    lead.status = LEAD_STATUS_WON
    lead.client_id = client.id
    
    fechado_stage = PipelineStage.query.filter(
        PipelineStage.pipeline_id == lead.pipeline_id,
        PipelineStage.company_id == current_user.company_id,
        PipelineStage.name.ilike('%fechado%')
    ).first()
    
    if fechado_stage:
        lead.pipeline_stage_id = fechado_stage.id
        
    template = ProcessTemplate.query.filter_by(company_id=current_user.company_id, name="Onboarding Padrão").first()
    checklist_data = template.steps if template else [{
        "title": "Start",
        "items": [
            {"text": "Enviar Welcome Kit", "done": False},
            {"text": "Solicitar Acessos", "done": False},
            {"text": "Agendar Kickoff", "done": False},
            {"text": "Criar Pasta no Drive", "done": False}
        ]
    }]
        
    checklist = ClientChecklist(
        client_id=client.id,
        company_id=current_user.company_id,
        name="Onboarding Inicial",
        progress=checklist_data
    )
    db.session.add(checklist)
    
    task_create = Task(
        title="Criar Contrato",
        description=f"Gerar/Emitir contrato para {client.name}.",
        due_date=datetime.utcnow() + timedelta(days=1),
        priority='alta',
        status='pendente',
        client_id=client.id,
        assigned_to_id=client.account_manager_id,
        company_id=client.company_id
    )
    db.session.add(task_create)

    if client.account_manager_id and client.account_manager_id != current_user.id:
        create_notification(
            user_id=client.account_manager_id,
            company_id=current_user.company_id,
            type='lead_converted',
            title='Lead Convertido',
            message=f"Lead {lead.name} convertido e atribuído a você."
        )
    
    WhatsAppMessage.query.filter_by(lead_id=lead.id).update({'client_id': client.id, 'lead_id': None})
    
    db.session.commit()
    flash(f'Parabéns! {client.name} agora é um cliente ativo.', 'success')
    return redirect(url_for('clients.client_details', id=client.id))

@leads_bp.route('/leads/\u003cint:id\u003e/bant', methods=['POST'])
@login_required
def update_bant(id):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
        
    lead.bant_budget = request.form.get('bant_budget')
    lead.bant_authority = request.form.get('bant_authority')
    lead.bant_need = request.form.get('bant_need')
    lead.bant_timeline = request.form.get('bant_timeline')
    
    db.session.commit()
    flash('Critérios BANT atualizados.', 'success')
    return redirect(url_for('leads.lead_details', id=id))

@leads_bp.route('/leads/<int:id>/interactions', methods=['POST'])
@login_required
def add_lead_interaction(id):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
    
    content = request.form.get('content')
    if not content:
        flash('Conteúdo da nota é obrigatório.', 'error')
        return redirect(url_for('leads.lead_details', id=id))

    interaction = Interaction(
        lead_id=lead.id,
        user_id=current_user.id,
        company_id=current_user.company_id,
        type='note',
        content=content,
        created_at=datetime.now()
    )
    db.session.add(interaction)
    db.session.commit()
    flash('Nota adicionada.', 'success')
    return redirect(url_for('leads.lead_details', id=id))

@leads_bp.route('/pipeline/stages/new', methods=['POST'])
@login_required
def create_stage():
    pipeline_id = request.form.get('pipeline_id')
    pipeline = Pipeline.query.get_or_404(pipeline_id)
    if pipeline.company_id != current_user.company_id:
        abort(403)
        
    name = request.form.get('name')
    if not name:
        flash('Nome da etapa é obrigatório.', 'error')
        return redirect(url_for('leads.pipeline', pipeline_id=pipeline_id))
        
    # Get last order index
    last_stage = PipelineStage.query.filter_by(pipeline_id=pipeline_id).order_by(PipelineStage.order_index.desc()).first()
    new_index = (last_stage.order_index + 1) if last_stage else 0
    
    stage = PipelineStage(
        name=name,
        pipeline_id=pipeline_id,
        company_id=current_user.company_id,
        order_index=new_index
    )
    db.session.add(stage)
    db.session.commit()
    flash('Etapa criada com sucesso.', 'success')
    return redirect(url_for('leads.pipeline', pipeline_id=pipeline_id))

@leads_bp.route('/pipeline/stages/\u003cint:id\u003e/update', methods=['POST'])
@login_required
def update_stage(id):
    stage = PipelineStage.query.get_or_404(id)
    if stage.company_id != current_user.company_id:
        abort(403)
        
    name = request.form.get('name')
    if name:
        stage.name = name
        db.session.commit()
        flash('Etapa atualizada.', 'success')
    
    return redirect(url_for('leads.pipeline', pipeline_id=stage.pipeline_id))

@leads_bp.route('/pipeline/stages/\u003cint:id\u003e/delete', methods=['POST'])
@login_required
def delete_stage(id):
    stage = PipelineStage.query.get_or_404(id)
    if stage.company_id != current_user.company_id:
        abort(403)
        
    p_id = stage.pipeline_id
    db.session.delete(stage)
    db.session.commit()
    flash('Etapa excluída.', 'success')
    return redirect(url_for('leads.pipeline', pipeline_id=p_id))

@leads_bp.route('/pipelines/new', methods=['POST'])
@login_required
def create_pipeline():
    name = request.form.get('name')
    if not name:
        flash('Nome do pipeline é obrigatório.', 'error')
        return redirect(url_for('leads.pipeline'))
        
    pipeline = Pipeline(name=name, company_id=current_user.company_id)
    db.session.add(pipeline)
    db.session.flush()
    
    # Add default stages
    stages = ["Qualificação", "Apresentação", "Proposta", "Negociação", "Fechado"]
    for i, s_name in enumerate(stages):
        stage = PipelineStage(name=s_name, pipeline_id=pipeline.id, company_id=current_user.company_id, order_index=i)
        db.session.add(stage)
        
    db.session.commit()
    flash('Pipeline criado com sucesso.', 'success')
    return redirect(url_for('leads.pipeline', pipeline_id=pipeline.id))
