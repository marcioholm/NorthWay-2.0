from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Lead, Client, Pipeline, PipelineStage, ProcessTemplate, ClientChecklist, Task, Interaction, WhatsAppMessage, LEAD_STATUS_WON, LEAD_STATUS_NEW, LEAD_STATUS_IN_PROGRESS, LEAD_STATUS_LOST, User
from utils import create_notification
from datetime import datetime, timedelta

leads_bp = Blueprint('leads', __name__)

@leads_bp.route('/leads', methods=['GET', 'POST'])
@login_required
def leads():
    if not current_user.company_id:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        source = request.form.get('source')
        assigned_to_id = request.form.get('assigned_to_id', current_user.id)
        email = request.form.get('email')
        interest = request.form.get('interest')
        notes = request.form.get('notes')

        if not name or not phone or not source:
            flash('Nome, Telefone e Origem são obrigatórios.', 'error')
            return redirect(url_for('leads.leads'))

        # Get default pipeline and stage for this company
        pipeline = Pipeline.query.filter_by(company_id=current_user.company_id).first()
        stage_id = None
        pipeline_id = None
        
        if pipeline:
            pipeline_id = pipeline.id
            first_stage = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).first()
            if first_stage:
                stage_id = first_stage.id

        new_lead = Lead(
            name=name,
            phone=phone,
            email=email,
            source=source,
            bant_need=interest,
            notes=notes,
            company_id=current_user.company_id,
            status=LEAD_STATUS_NEW,
            assigned_to_id=assigned_to_id,
            pipeline_id=pipeline_id,
            pipeline_stage_id=stage_id
        )

        try:
            db.session.add(new_lead)
            db.session.commit()
            flash('Lead criado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar lead: {str(e)}', 'error')
            
        return redirect(url_for('leads.leads'))
    if not current_user.company_id:
        abort(403)

    page = request.args.get('page', 1, type=int)
    per_page = 20
    # Strict filter
    query = Lead.query.filter(Lead.company_id == current_user.company_id)
    
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
    # Strict filter
    users = User.query.filter(User.company_id == current_user.company_id).all()
    
    return render_template('leads.html', leads=leads_list, pagination=pagination, users=users)

@leads_bp.route('/leads/<int:id>')
@login_required
def lead_details(id):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
    
    users = User.query.filter_by(company_id=current_user.company_id).all()
    
    stages = []
    is_first_stage = False
    
    if lead.pipeline_id:
        stages = PipelineStage.query.filter_by(pipeline_id=lead.pipeline_id).order_by(PipelineStage.order).all()
        if stages and lead.pipeline_stage_id == stages[0].id:
            is_first_stage = True
    else:
        # If no pipeline assigned yet (orphan), treat as first stage (editable)
        is_first_stage = True
        
    return render_template('lead_details.html', lead=lead, users=users, stages=stages, is_first_stage=is_first_stage)

# ... (skip to update_lead_info) ...

@leads_bp.route('/leads/<int:id>/update_info', methods=['POST'])
@login_required
def update_lead_info(id):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
    
    # Check if allowed to edit identity (First Stage Only)
    is_first_stage = False
    if lead.pipeline_id:
        first_stage = PipelineStage.query.filter_by(pipeline_id=lead.pipeline_id).order_by(PipelineStage.order).first()
        if first_stage and lead.pipeline_stage_id == first_stage.id:
            is_first_stage = True
    else:
        is_first_stage = True

    # Identity Fields (Restricted)
    if is_first_stage:
        new_name = request.form.get('name')
        if new_name:
            lead.name = new_name

    lead.email = request.form.get('email')
    
    # Handle Split Phone
    phone_ddi = request.form.get('phone_ddi')
    phone_number = request.form.get('phone_number')
    if phone_ddi and phone_number:
        # Strip formatting from number
        clean_number = ''.join(filter(str.isdigit, phone_number))
        lead.phone = f"{phone_ddi}{clean_number}"
    elif request.form.get('phone'): # Fallback / direct update
        lead.phone = request.form.get('phone')

    lead.website = request.form.get('website')
    lead.address = request.form.get('address')
    lead.source = request.form.get('source')
    lead.interest = request.form.get('interest')
    
    # Enrichment fields (Manual Edit)
    lead.legal_name = request.form.get('legal_name')
    lead.cnpj = request.form.get('cnpj')
    lead.foundation_date = request.form.get('foundation_date')
    lead.legal_email = request.form.get('legal_email')
    lead.legal_phone = request.form.get('legal_phone')
    
    equity_val = request.form.get('equity')
    if equity_val:
        try:
            # Clean formatting if present
            clean_equity = equity_val.replace('R$', '').replace('.', '').replace(',', '.').strip()
            lead.equity = float(clean_equity)
        except (ValueError, TypeError):
             pass
            
    # Stage Update
    pipeline_stage_id = request.form.get('pipeline_stage_id')
    if pipeline_stage_id:
        lead.pipeline_stage_id = int(pipeline_stage_id)
        lead.status = LEAD_STATUS_IN_PROGRESS
    
    # Handle Assignment
    assigned_id = request.form.get('assigned_to_id')
    if assigned_id:
        if assigned_id == 'none':
            lead.assigned_to_id = None
        else:
            # Validate Cross-Company Assignment
            user_to_assign = User.query.get(int(assigned_id))
            if user_to_assign and user_to_assign.company_id == current_user.company_id:
                lead.assigned_to_id = int(assigned_id)
            else:
                flash("Erro: Tentativa de atribuir usuário inválido ou de outra organização.", "error")
    
    db.session.commit()
    flash('Informações do lead atualizadas.', 'success')
    return redirect(request.referrer or url_for('leads.lead_details', id=id))

@leads_bp.route('/leads/<int:id>/delete', methods=['POST'])
@login_required
def delete_lead(id):
    lead = Lead.query.get_or_404(id)
    if lead.company_id != current_user.company_id:
        abort(403)
        
    # Validation: Only delete if in first stage
    if lead.pipeline_id:
        first_stage = PipelineStage.query.filter_by(pipeline_id=lead.pipeline_id).order_by(PipelineStage.order).first()
        if first_stage and lead.pipeline_stage_id != first_stage.id:
            flash('Só é possível excluir leads na primeira etapa do funil (Qualificação).', 'error')
            return redirect(url_for('leads.lead_details', id=id))
            
    db.session.delete(lead)
    db.session.commit()
    flash('Lead excluído com sucesso.', 'success')
    return redirect(url_for('leads.leads'))

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
    last_stage = PipelineStage.query.filter_by(pipeline_id=pipeline_id).order_by(PipelineStage.order.desc()).first()
    new_index = (last_stage.order + 1) if last_stage else 0
    
    stage = PipelineStage(
        name=name,
        pipeline_id=pipeline_id,
        company_id=current_user.company_id,
        order=new_index
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
        stage = PipelineStage(name=s_name, pipeline_id=pipeline.id, company_id=current_user.company_id, order=i)
        db.session.add(stage)
        
    db.session.commit()
    flash('Pipeline criado com sucesso.', 'success')
    flash('Pipeline criado com sucesso.', 'success')
    return redirect(url_for('leads.pipeline', pipeline_id=pipeline.id))

@leads_bp.route('/leads/template/download')
@login_required
def download_lead_template():
    import csv 
    import io
    from flask import Response
    
    header = ['Nome', 'Email', 'Telefone', 'Origem', 'Interesse', 'Observações']
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(header)
    cw.writerow(['Exemplo Empresa', 'contato@empresa.com', '(11) 99999-9999', 'Google', 'Consultoria', 'Cliente interessado em...'])
    
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=modelo_importacao_leads.csv"}
    )

@leads_bp.route('/leads/export')
@login_required
def export_leads():
    if not current_user.company_id:
        abort(403)

    import csv 
    import io
    from flask import Response
    
    leads = Lead.query.filter(Lead.company_id == current_user.company_id).all()
    
    header = ['ID', 'Nome', 'Email', 'Telefone', 'Status', 'Origem', 'Data Criação']
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(header)
    
    for l in leads:
        cw.writerow([l.id, l.name, l.email or '', l.phone or '', l.status, l.source or '', l.created_at.strftime('%d/%m/%Y')])
        
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=leads_export_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@leads_bp.route('/leads/import', methods=['POST'])
@login_required
def import_leads():
    import csv
    import io
    
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('leads.leads'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('leads.leads'))
        
    if file:
        try:
            # Read content first to detect delimiter
            content = file.stream.read().decode("UTF8")
            stream = io.StringIO(content, newline=None)
            
            # Auto-detect delimiter (Robuster for different versions of the extension)
            delimiter = ';'
            if content.count(',') > content.count(';'):
                delimiter = ','
                
            csv_input = csv.reader(stream, delimiter=delimiter)
            header = next(csv_input, None) # Skip header
            
            count = 0
            for row in csv_input:
                if len(row) < 1: continue
                # Simple mapping based on template order: Name, Email, Phone, Source, Interest, Notes
                name = row[0]
                if not name: continue
                
                email = row[1] if len(row) > 1 else None
                phone = row[2] if len(row) > 2 else None
                source = row[3] if len(row) > 3 else 'Importado'
                interest = row[4] if len(row) > 4 else None
                notes = row[5] if len(row) > 5 else None
                
                lead = Lead(
                    name=name,
                    email=email,
                    phone=phone,
                    source=source,
                    bant_need=interest,
                    notes=notes,
                    company_id=current_user.company_id,
                    status='new',
                    assigned_to_id=current_user.id
                )
                db.session.add(lead)
                count += 1
            
            db.session.commit()
            flash(f'{count} leads importados com sucesso!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro na importação: {str(e)}', 'error')
            
    return redirect(url_for('leads.leads'))

@leads_bp.route('/leads/fix-orphans')
@login_required
def fix_orphans():
    # 1. Get or Create Default Pipeline
    pipeline = Pipeline.query.filter_by(company_id=current_user.company_id).first()
    if not pipeline:
         pipeline = Pipeline(name="Pipeline Comercial", company_id=current_user.company_id)
         db.session.add(pipeline)
         db.session.flush()
         stages = ["Qualificação", "Apresentação", "Proposta", "Negociação", "Fechado"]
         for i, s_name in enumerate(stages):
            st = PipelineStage(name=s_name, pipeline_id=pipeline.id, company_id=current_user.company_id, order=i)
            db.session.add(st)
         db.session.commit()
    
    stages = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).all()
    first_stage = stages[0]
    last_stage = stages[-1]
    
    # Identify closed stage specifically if possible
    fechado_stage = next((s for s in stages if 'fechado' in s.name.lower() or 'fechamento' in s.name.lower()), last_stage)
    
    # 2. Update Leads
    orphans = Lead.query.filter_by(company_id=current_user.company_id, pipeline_id=None).all()
    count = 0
    for lead in orphans:
        lead.pipeline_id = pipeline.id
        # If won/converted -> closed stage
        if lead.status == 'won' or lead.client_id:
            lead.pipeline_stage_id = fechado_stage.id
        else:
            lead.pipeline_stage_id = first_stage.id
        count += 1
        
    db.session.commit()
    
    flash(f'Correção aplicada: {count} leads atribuídos ao funil "{pipeline.name}".', 'success')
    return redirect(url_for('leads.pipeline'))

@leads_bp.route('/api/leads/quick-add', methods=['POST'])
@login_required # Relies on session cookie shared with browser
def quick_add_lead():
    data = request.get_json()
    name = data.get('name')
    # Info helps map phone or company/job title
    info = data.get('info') 
    source = data.get('source', 'Extension')
    
    if not name:
        return jsonify({'error': 'Name required'}), 400
        
    # Heuristic for phone vs company in "info"
    phone = None
    notes = None
    if info:
        # Simple check: if it looks like a phone, use it. Else put in notes.
        if any(c.isdigit() for c in info) and len(info) < 20: 
            phone = info
        else:
            notes = f"Info capturada: {info}"

    # Get default pipeline
    pipeline = Pipeline.query.filter_by(company_id=current_user.company_id).first()
    stage_id = None
    pipeline_id = None
    if pipeline:
        pipeline_id = pipeline.id
        stage = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).first()
        if stage:
            stage_id = stage.id

    lead = Lead(
        name=name,
        phone=phone or "Não informado",
        source=source,
        notes=notes,
        company_id=current_user.company_id,
        status=LEAD_STATUS_NEW,
        assigned_to_id=current_user.id,
        pipeline_id=pipeline_id,
        pipeline_stage_id=stage_id
    )
    
    try:
        db.session.add(lead)
        db.session.commit()
        return jsonify({'success': True, 'lead_id': lead.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
