from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import requests
from sqlalchemy import func
from models import db, Lead, Interaction, ProspectingSearch, Company, ProspectingCampaign, ProspectingMessage, ProspectingSetting, TenantAICredential, ProspectingIntegration, CRMWebhookLog
from datetime import datetime, timedelta
from utils.webhooks import send_outbound_webhook
from constants import ProspectingStatus, IntentStatus, LeadChannel, MessageStatus, MessageType, NotificationType, IntegrationProvider, AIProvider, CampaignStatus

from services.cnpj_service import CNPJAService
from utils.crypto import encrypt_api_key, decrypt_api_key

prospecting_bp = Blueprint('prospecting', __name__)

def check_prospecting_access():
    """Verifica acesso ao módulo de prospecção de forma segura"""
    if not current_user.company_id:
        return False, 'Acesso negado'
    try:
        company = getattr(current_user, 'company', None)
        if company and hasattr(company, 'has_feature'):
            if not company.has_feature('prospecting'):
                return False, 'Acesso negado'
        return True, None
    except Exception as e:
        print(f"Error checking prospecting access: {e}")
        return True, None  # Allow access if check fails


def api_response(success=True, data=None, error=None, status=200):
    return jsonify({
        'success': success,
        'data': data,
        'error': error
    }), status


def sync_prospecting_stage(lead, prospecting_status):
    """
    Sincroniza o estágio do pipeline do lead com base no status da prospecção.
    """
    if not lead or not lead.prospecting_campaign_id:
        return
    campaign = lead.prospecting_campaign
    if not campaign or not campaign.pipeline_id:
        return

    status_to_stage_name = {
        ProspectingStatus.NOVO: 'Lista Fria',
        ProspectingStatus.EM_EXECUCAO: 'Lista Fria',
        ProspectingStatus.AGUARDANDO_APROVACAO: 'Aguardando Aprovação',
        ProspectingStatus.PENDING_APPROVAL: 'Aguardando Aprovação',
        ProspectingStatus.CONTATADO: 'Contatado',
        ProspectingStatus.SENT: 'Contatado',
        ProspectingStatus.APPROVED: 'Contatado',
        ProspectingStatus.RESPONDEU: 'Respondeu',
        ProspectingStatus.INTERESSADO: 'Respondeu',
        ProspectingStatus.REUNIAO: 'Reunião Agendada',
        ProspectingStatus.CLIENTE: 'Cliente',
        ProspectingStatus.DESCARTADO: 'Descartado',
        ProspectingStatus.ERRO: 'Descartado',
        ProspectingStatus.FAILED: 'Descartado'
    }

    target_stage_name = status_to_stage_name.get(prospecting_status)
    if not target_stage_name:
        return

    from models import PipelineStage
    stage = PipelineStage.query.filter_by(pipeline_id=campaign.pipeline_id).filter(
        PipelineStage.name.ilike(f"%{target_stage_name}%")
    ).first()

    if stage:
        lead.pipeline_id = campaign.pipeline_id
        lead.pipeline_stage_id = stage.id


@prospecting_bp.route('/prospecting')
@login_required
def index():
    allowed, error = check_prospecting_access()
    if not allowed:
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('prospecting.dashboard'))


@prospecting_bp.route('/prospecting/discover')
@login_required
def discover():
    allowed, error = check_prospecting_access()
    if not allowed:
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))
    return render_template('prospecting/discover.html')


@prospecting_bp.route('/prospecting/dashboard')
@login_required
def dashboard():
    if not current_user.company_id:
        return redirect(url_for('dashboard.home'))

    company_id = current_user.company_id

    try:
        # Reset stale prospecting_status: leads with status but zero messages in prospection tables
        from models import ProspectingMessage, MessageQueue
        all_prospecting_leads = Lead.query.filter(
            Lead.company_id == company_id,
            Lead.prospecting_status.isnot(None)
        ).all()
        all_ids = [l.id for l in all_prospecting_leads]
        if all_ids:
            has_msgs = {r[0] for r in db.session.query(ProspectingMessage.lead_id).filter(
                ProspectingMessage.lead_id.in_(all_ids)
            ).distinct().all()}
            has_queue = {r[0] for r in db.session.query(MessageQueue.lead_id).filter(
                MessageQueue.lead_id.in_(all_ids)
            ).distinct().all()}
            truly_stale = [lid for lid in all_ids if lid not in has_msgs and lid not in has_queue]
            if truly_stale:
                Lead.query.filter(Lead.id.in_(truly_stale)).update(
                    {'prospecting_status': None, 'next_action_at': None, 'in_execution': False},
                    synchronize_session=False
                )
                db.session.commit()

        # Aguardando aprovação from prospecting_messages table
        approval_count = db.session.query(func.count(func.distinct(ProspectingMessage.lead_id))).filter(
            ProspectingMessage.company_id == company_id,
            ProspectingMessage.status.in_([MessageStatus.AGUARDANDO_APROVACAO, MessageStatus.PENDING_APPROVAL])
        ).scalar() or 0

        # Message queue pending count
        queue_count = db.session.query(func.count(func.distinct(MessageQueue.id))).filter(
            MessageQueue.company_id == company_id,
            MessageQueue.status == 'pending'
        ).scalar() or 0

        # Lead-based status counts (only leads still with status after stale reset)
        status_counts = db.session.query(
            Lead.prospecting_status,
            func.count(Lead.id).label('count')
        ).filter(
            Lead.company_id == company_id,
            Lead.prospecting_status.isnot(None)
        ).group_by(Lead.prospecting_status).all()

        counts = {row.prospecting_status: row.count for row in status_counts}
        total_leads = sum(counts.values())
        aguardando = counts.get(ProspectingStatus.NOVO, 0)
        em_execucao = counts.get(ProspectingStatus.EM_EXECUCAO, 0)
        aguardando_aprovacao = approval_count
        contatados = counts.get(ProspectingStatus.CONTATADO, 0) + counts.get(ProspectingStatus.SENT, 0) + counts.get(ProspectingStatus.APPROVED, 0)
        responderam = counts.get(ProspectingStatus.RESPONDEU, 0)
        interessados = counts.get(ProspectingStatus.INTERESSADO, 0)
        reunioes = counts.get(ProspectingStatus.REUNIAO, 0)
        clientes = counts.get(ProspectingStatus.CLIENTE, 0)
        sem_resposta = counts.get(ProspectingStatus.SEM_RESPOSTA, 0)
        erro_envio = counts.get(ProspectingStatus.ERRO, 0) + counts.get(ProspectingStatus.FAILED, 0)

        campaigns = ProspectingCampaign.query.filter_by(company_id=company_id, is_active=True).all()
    except Exception as e:
        print(f"Error in dashboard: {e}")
        total_leads = aguardando = em_execucao = aguardando_aprovacao = contatados = 0
        responderam = interessados = reunioes = clientes = sem_resposta = erro_envio = 0
        campaigns = []

    return render_template('prospecting/dashboard.html',
                           total_leads=total_leads,
                           aguardando=aguardando,
                           em_execucao=em_execucao,
                           aguardando_aprovacao=aguardando_aprovacao,
                           contatados=contatados,
                           responderam=responderam,
                           interessados=interessados,
        reunioes=reunioes,
        clientes=clientes,
        sem_resposta=sem_resposta,
                           erro_envio=erro_envio,
                           campaigns=campaigns)


@prospecting_bp.route('/prospecting/approvals')
@login_required
def approvals():
    if not current_user.company_id:
        return redirect(url_for('dashboard.home'))

    company_id = current_user.company_id

    pending_messages = ProspectingMessage.query.filter(
        ProspectingMessage.company_id == company_id,
        ProspectingMessage.status.in_([MessageStatus.AGUARDANDO_APROVACAO, MessageStatus.PENDING_APPROVAL])
    ).options(
        db.joinedload(ProspectingMessage.lead),
        db.joinedload(ProspectingMessage.campaign)
    ).order_by(ProspectingMessage.created_at.desc()).all()

    return render_template('prospecting/approvals.html', messages=pending_messages)


@prospecting_bp.route('/prospecting/leads')
@login_required
def leads():
    allowed, error = check_prospecting_access()
    if not allowed:
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))

    company_id = current_user.company_id

    filters = {
        'empresa': request.args.get('empresa'),
        'responsavel': request.args.get('responsavel'),
        'segmento': request.args.get('segmento'),
        'status': request.args.get('status'),
        'canal': request.args.get('canal'),
        'campanha': request.args.get('campanha')
    }

    query = Lead.query.filter_by(company_id=company_id).filter(
        Lead.prospecting_status.isnot(None)
    )

    if filters.get('status'):
        query = query.filter(Lead.prospecting_status == filters['status'])
    if filters.get('canal'):
        query = query.filter(Lead.preferred_channel == filters['canal'])
    if filters.get('campanha'):
        query = query.filter(Lead.prospecting_campaign_id == filters['campanha'])
    if filters.get('segmento'):
        query = query.filter(Lead.interest == filters['segmento'])

    leads_list = query.order_by(Lead.created_at.desc()).limit(100).all()

    campaigns = ProspectingCampaign.query.filter_by(company_id=company_id).all()
    users = current_user.company.users

    return render_template('prospecting/leads.html',
                           leads=leads_list,
                           campaigns=campaigns,
                           users=users,
                           filters=filters)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>')
@login_required
def lead_detail(lead_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    messages = ProspectingMessage.query.filter_by(lead_id=lead_id).order_by(ProspectingMessage.created_at.desc()).all()
    interactions = Interaction.query.filter_by(lead_id=lead_id).order_by(Interaction.created_at.desc()).limit(20).all()

    campaigns = ProspectingCampaign.query.filter_by(company_id=current_user.company_id, is_active=True).all()

    return render_template('prospecting/lead_detail.html',
                           lead=lead,
                           messages=messages,
                           interactions=interactions,
                           campaigns=campaigns)


@prospecting_bp.route('/prospecting/campaigns')
@login_required
def campaigns():
    if not current_user.company_id:
        return redirect(url_for('dashboard.home'))

    company_id = current_user.company_id

    try:
        campaigns_list = ProspectingCampaign.query.filter_by(company_id=company_id).order_by(ProspectingCampaign.created_at.desc()).all()
    except Exception as e:
        print(f"Error loading campaigns: {e}")
        campaigns_list = []

    return render_template('prospecting/campaigns.html', campaigns=campaigns_list)


@prospecting_bp.route('/prospecting/campaign/create', methods=['POST'])
@login_required
def create_campaign():
    if not current_user.company_id:
        return api_response(success=False, error='Acesso negado', status=403)

    data = request.json
    company_id = current_user.company_id

    try:
        from models import Pipeline, PipelineStage
        
        # Criar funil correspondente para a campanha
        new_pipeline = Pipeline(
            name=f"Prospecção: {data.get('name')}",
            company_id=company_id
        )
        db.session.add(new_pipeline)
        db.session.flush() # Obter o id do pipeline

        # Criar etapas padrão do funil de prospecção
        stages = [
            "Lista Fria",
            "Aguardando Aprovação",
            "Contatado",
            "Respondeu",
            "Reunião Agendada",
            "Descartado"
        ]
        for i, s_name in enumerate(stages):
            stage = PipelineStage(
                name=s_name,
                pipeline_id=new_pipeline.id,
                company_id=company_id,
                order=i
            )
            db.session.add(stage)
        db.session.flush()

        campaign = ProspectingCampaign(
            company_id=company_id,
            name=data.get('name'),
            description=data.get('description'),
            target_segment=data.get('target_segment'),
            objective=data.get('objective'),
            tone_of_voice=data.get('tone_of_voice'),
            offer=data.get('offer'),
            main_angle=data.get('main_angle'),
            default_cta=data.get('default_cta'),
            restrictions=data.get('restrictions'),
            max_attempts=data.get('max_attempts', 3),
            followup_interval_days=data.get('followup_interval_days', 3),
            status=CampaignStatus.RASCUNHO,
            is_active=True,
            pipeline_id=new_pipeline.id
        )

        db.session.add(campaign)
        db.session.commit()

        return api_response(data={'id': campaign.id, 'name': campaign.name})
    except Exception as e:
        print(f"Error creating campaign: {e}")
        db.session.rollback()
        return api_response(success=False, error='Erro ao criar campanha', status=500)


@prospecting_bp.route('/prospecting/campaign/<int:campaign_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def manage_campaign(campaign_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=current_user.company_id).first_or_404()

    if request.method == 'GET':
        # Contar leads da campanha
        lead_count = Lead.query.filter_by(prospecting_campaign_id=campaign.id).count()
        
        return api_response(data={
            'id': campaign.id,
            'name': campaign.name,
            'description': campaign.description,
            'target_segment': campaign.target_segment,
            'objective': campaign.objective,
            'tone_of_voice': campaign.tone_of_voice,
            'offer': campaign.offer,
            'main_angle': campaign.main_angle,
            'default_cta': campaign.default_cta,
            'restrictions': campaign.restrictions,
            'max_attempts': campaign.max_attempts,
            'followup_interval_days': campaign.followup_interval_days,
            'status': campaign.status,
            'is_active': campaign.is_active,
            'stats': {
                'total_leads': lead_count
            }
        })

    if request.method == 'PUT':
        data = request.json
        old_name = campaign.name
        campaign.name = data.get('name', campaign.name)
        campaign.description = data.get('description', campaign.description)
        campaign.target_segment = data.get('target_segment', campaign.target_segment)
        campaign.objective = data.get('objective', campaign.objective)
        campaign.tone_of_voice = data.get('tone_of_voice', campaign.tone_of_voice)
        campaign.offer = data.get('offer', campaign.offer)
        campaign.main_angle = data.get('main_angle', campaign.main_angle)
        campaign.default_cta = data.get('default_cta', campaign.default_cta)
        campaign.restrictions = data.get('restrictions', campaign.restrictions)
        campaign.max_attempts = data.get('max_attempts', campaign.max_attempts)
        campaign.followup_interval_days = data.get('followup_interval_days', campaign.followup_interval_days)
        campaign.status = data.get('status', campaign.status)
        campaign.is_active = data.get('is_active', campaign.is_active)

        # Atualizar nome do pipeline correspondente se o nome da campanha mudou
        if campaign.name != old_name and campaign.pipeline_id:
            from models import Pipeline
            p = Pipeline.query.get(campaign.pipeline_id)
            if p:
                p.name = f"Prospecção: {campaign.name}"

        db.session.commit()
        return api_response(success=True)

    if request.method == 'DELETE':
        if campaign.pipeline_id:
            from models import Pipeline
            p = Pipeline.query.get(campaign.pipeline_id)
            if p:
                # Desassociar os leads desse pipeline/estágios para evitar violação de integridade referencial
                Lead.query.filter_by(pipeline_id=p.id).update({
                    'pipeline_id': None,
                    'pipeline_stage_id': None
                }, synchronize_session=False)
                db.session.delete(p)
        db.session.delete(campaign)
        db.session.commit()
        return api_response(success=True)


@prospecting_bp.route('/prospecting/campaign/<int:campaign_id>/details')
@login_required
def campaign_details(campaign_id):
    """Retorna os detalhes da campanha com contatos e mensagens"""
    if not current_user.company_id:
        return api_response(success=False, error='Acesso negado', status=403)
    
    campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=current_user.company_id).first()
    if not campaign:
        return api_response(success=False, error='Campanha não encontrada', status=404)
    
    # Subquery: última mensagem por lead nesta campanha
    last_msg_subq = db.session.query(
        ProspectingMessage.lead_id,
        func.max(ProspectingMessage.id).label('max_id')
    ).filter(
        ProspectingMessage.campaign_id == campaign_id
    ).group_by(ProspectingMessage.lead_id).subquery()

    last_msgs = db.session.query(ProspectingMessage).join(
        last_msg_subq,
        ProspectingMessage.id == last_msg_subq.c.max_id
    ).all()

    msg_by_lead = {m.lead_id: m for m in last_msgs}

    leads = Lead.query.filter_by(prospecting_campaign_id=campaign_id).all()
    leads_data = []
    for lead in leads:
        last_msg = msg_by_lead.get(lead.id)
        leads_data.append({
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone,
            'status': lead.prospecting_status,
            'preferred_channel': lead.preferred_channel,
            'message': {
                'id': last_msg.id if last_msg else None,
                'status': last_msg.status if last_msg else None,
                'channel': last_msg.channel if last_msg else None,
                'content': last_msg.content[:200] + '...' if last_msg and last_msg.content and len(last_msg.content) > 200 else last_msg.content if last_msg else None,
                'created_at': last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None
            } if last_msg else None
        })
    
    # Buscar mensagens aguardando aprovação
    pending_messages = ProspectingMessage.query.filter(
        ProspectingMessage.campaign_id == campaign_id,
        ProspectingMessage.status.in_([MessageStatus.AGUARDANDO_APROVACAO, MessageStatus.PENDING_APPROVAL])
    ).order_by(ProspectingMessage.created_at.desc()).all()
    
    pending_data = []
    for msg in pending_messages:
        pending_data.append({
            'id': msg.id,
            'lead_id': msg.lead_id,
            'lead_name': msg.lead.name if msg.lead else 'Lead não encontrado',
            'lead_phone': msg.lead.phone if msg.lead else None,
            'lead_email': msg.lead.email if msg.lead else None,
            'channel': msg.channel,
            'content': msg.content,
            'created_at': msg.created_at.isoformat() if msg.created_at else None
        })
    
    # Contar status das mensagens
    sent_count = ProspectingMessage.query.filter(
        ProspectingMessage.campaign_id == campaign_id,
        ProspectingMessage.status.in_([MessageStatus.ENVIADA, MessageStatus.SENT, ProspectingStatus.APPROVED])
    ).count()
    error_count = ProspectingMessage.query.filter(
        ProspectingMessage.campaign_id == campaign_id,
        ProspectingMessage.status.in_([MessageStatus.ERRO, MessageStatus.FAILED])
    ).count()
    
    # Funnel data: leads grouped by prospecting status
    funnel_groups = {
        ProspectingStatus.RESPONDEU: [],
        ProspectingStatus.INTERESSADO: [],
        ProspectingStatus.REUNIAO: [],
        ProspectingStatus.CLIENTE: [],
        ProspectingStatus.SEM_RESPOSTA: [],
        ProspectingStatus.DESCARTADO: []
    }
    for lead in leads:
        status = lead.prospecting_status
        if status == ProspectingStatus.RESPONDEU:
            funnel_groups[ProspectingStatus.RESPONDEU].append(lead.id)
        if status == ProspectingStatus.INTERESSADO:
            funnel_groups[ProspectingStatus.INTERESSADO].append(lead.id)
        if status == ProspectingStatus.REUNIAO:
            funnel_groups[ProspectingStatus.REUNIAO].append(lead.id)
        if status == ProspectingStatus.CLIENTE:
            funnel_groups[ProspectingStatus.CLIENTE].append(lead.id)
        if status == ProspectingStatus.SEM_RESPOSTA:
            funnel_groups[ProspectingStatus.SEM_RESPOSTA].append(lead.id)
        if status in (ProspectingStatus.DESCARTADO, ProspectingStatus.ERRO, ProspectingStatus.FAILED):
            funnel_groups[ProspectingStatus.DESCARTADO].append(lead.id)
    
    funnel = {
        'total': len(leads),
        'responderam': len(funnel_groups[ProspectingStatus.RESPONDEU]),
        'interessados': len(funnel_groups[ProspectingStatus.INTERESSADO]),
        'reunioes': len(funnel_groups[ProspectingStatus.REUNIAO]),
        'clientes': len(funnel_groups[ProspectingStatus.CLIENTE]),
        'sem_resposta': len(funnel_groups[ProspectingStatus.SEM_RESPOSTA]),
        'descartados': len(funnel_groups[ProspectingStatus.DESCARTADO]),
        'restante': len(leads) - sum(len(v) for v in funnel_groups.values())
    }
    
    return api_response(data={
        'campaign': {
            'id': campaign.id,
            'name': campaign.name,
            'status': campaign.status,
            'stats': {
                'total_leads': len(leads),
                'total_queued': 0,
                'total_sent': sent_count,
                'total_delivered': 0,
                'total_failed': error_count,
                'pending_approval': len(pending_messages)
            },
            'funnel': funnel
        },
        'leads': leads_data,
        'pending_messages': pending_data
    })



@prospecting_bp.route('/prospecting/messages')
@login_required
def messages():
    allowed, error = check_prospecting_access()
    if not allowed:
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))

    company_id = current_user.company_id

    status_filter = request.args.get('status')
    channel_filter = request.args.get('channel')

    query = ProspectingMessage.query.filter_by(company_id=company_id)

    if status_filter:
        query = query.filter(ProspectingMessage.status == status_filter)
    if channel_filter:
        query = query.filter(ProspectingMessage.channel == channel_filter)

    messages_list = query.order_by(ProspectingMessage.created_at.desc()).limit(100).all()

    return render_template('prospecting/messages.html', messages=messages_list)


@prospecting_bp.route('/prospecting/settings')
@login_required
def settings():
    allowed, error = check_prospecting_access()
    if not allowed:
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))

    setting = ProspectingSetting.query.filter_by(company_id=current_user.company_id).first()

    if not setting:
        setting = ProspectingSetting(
            company_id=current_user.company_id,
            manual_approval_required=True,
            default_ai_model='gpt-4.1-mini',
            default_tone='profissional'
        )
        db.session.add(setting)
        db.session.commit()

    return render_template('prospecting/settings.html', setting=setting)


@prospecting_bp.route('/prospecting/settings/update', methods=['POST'])
@login_required
def update_settings():
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    data = request.json
    company_id = current_user.company_id

    setting = ProspectingSetting.query.filter_by(company_id=company_id).first()

    if not setting:
        setting = ProspectingSetting(company_id=company_id)
        db.session.add(setting)

    setting.generate_message_webhook_url = data.get('generate_message_webhook_url') or data.get('webhook_generate_message')
    setting.send_whatsapp_webhook_url = data.get('send_whatsapp_webhook_url') or data.get('webhook_send_whatsapp')
    setting.send_email_webhook_url = data.get('send_email_webhook_url') or data.get('webhook_send_email')
    setting.daily_send_limit = data.get('daily_send_limit', 50)
    setting.sending_start_time = data.get('sending_start_time', '09:00')
    setting.sending_end_time = data.get('sending_end_time', '18:00')
    setting.manual_approval_required = data.get('manual_approval_required', True)
    setting.default_ai_model = data.get('default_ai_model', 'gpt-4.1-mini')
    setting.default_tone = data.get('default_tone', 'profissional')

    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/api/prospecting/watchdog/reset-stuck', methods=['POST'])
@login_required
def reset_stuck_leads():
    """
    Reseta leads travados com in_execution=True por mais de 15 minutos.
    Chamado pelo próprio CRM (botão no dashboard) ou pelo n8n a cada hora.
    """
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    company_id = current_user.company_id
    threshold = datetime.utcnow() - timedelta(minutes=15)

    stuck_leads = Lead.query.filter(
        Lead.company_id == company_id,
        Lead.in_execution == True,
        Lead.updated_at < threshold
    ).all()

    reset_count = 0
    for lead in stuck_leads:
        lead.in_execution = False
        lead.prospecting_status = ProspectingStatus.NOVO
        reset_count += 1

    db.session.commit()

    return api_response(data={
        'reset_count': reset_count,
        'message': f'{reset_count} lead(s) travado(s) foram resetados.'
    })


def _save_message(lead, channel, content, angle, model, step_number=None):
    """Cria um registro ProspectingMessage com step_number calculado."""
    if step_number is None:
        existing_count = ProspectingMessage.query.filter(
            ProspectingMessage.lead_id == lead.id,
            ProspectingMessage.campaign_id == lead.prospecting_campaign_id,
            ProspectingMessage.type == MessageType.OUTBOUND,
            ProspectingMessage.status.in_([MessageStatus.SENT, MessageStatus.ENVIADA])
        ).count()
        step_number = existing_count + 1

    try:
        step_number = int(step_number)
    except (TypeError, ValueError):
        step_number = 1

    first_msg = ProspectingMessage.query.filter_by(
        lead_id=lead.id,
        campaign_id=lead.prospecting_campaign_id,
        type=MessageType.OUTBOUND
    ).order_by(ProspectingMessage.created_at.asc()).first()

    cadence_day = 0
    try:
        if first_msg and step_number > 1:
            delta = datetime.utcnow() - first_msg.created_at
            cadence_day = delta.days
    except TypeError:
        cadence_day = 0

    msg = ProspectingMessage(
        company_id=lead.company_id,
        lead_id=lead.id,
        campaign_id=lead.prospecting_campaign_id,
        channel=channel,
        type=MessageType.OUTBOUND,
        status=MessageStatus.PENDING_APPROVAL,
        content=content,
        ai_model=model,
        step_number=step_number,
        cadence_day=cadence_day,
        created_at=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.flush()
    return {'channel': channel, 'message_id': msg.id, 'content': content, 'status': MessageStatus.PENDING_APPROVAL,
            'angle': angle, 'model': model, 'step_number': step_number, 'cadence_day': cadence_day}


def _generate_single_message(lead, setting, channel, feedback=None, step_number=None):
    """Gera uma mensagem para um lead em um canal específico."""
    payload = {
        'action': 'generate_message',
        'tenant_id': lead.company_id,
        'lead_id': lead.id,
        'campaign_id': lead.prospecting_campaign_id,
        'channel': channel
    }
    if feedback:
        payload['feedback'] = feedback

    success, response_payload, error_msg = send_outbound_webhook(
        tenant_id=lead.company_id,
        lead_id=lead.id,
        action='generate_message',
        webhook_url=setting.generate_message_webhook_url,
        payload=payload
    )

    if not success:
        raise Exception(error_msg or "Erro ao chamar o webhook do n8n")

    message_text = response_payload.get('message', '') if response_payload else ''
    if message_text:
        angle = response_payload.get('angle', 'Atrair')
        model = response_payload.get('model', 'llama-3.1-8b-instant')
        return _save_message(lead, channel, message_text, angle, model, step_number=step_number)

    return {'channel': channel, 'status': 'processing'}


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/generate-message', methods=['POST'])
@login_required
def generate_message(lead_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    if lead.in_execution or lead.prospecting_status == ProspectingStatus.EM_EXECUCAO:
        return api_response(success=False, error='Já existe uma mensagem sendo gerada para este lead', status=400)

    setting = ProspectingSetting.query.filter_by(company_id=current_user.company_id).first()
    if not setting or not setting.generate_message_webhook_url:
        return api_response(success=False, error='Webhook de geração de mensagem não configurado', status=400)

    channel = lead.preferred_channel or LeadChannel.WHATSAPP
    if request.is_json:
        channel = request.json.get('channel', channel)

    results = []
    any_success = False
    last_error = None

    lead.in_execution = True
    lead.prospecting_status = ProspectingStatus.EM_EXECUCAO
    sync_prospecting_stage(lead, ProspectingStatus.EM_EXECUCAO)
    db.session.commit()

    try:
        result = _generate_single_message(lead, setting, LeadChannel.WHATSAPP)
        results.append(result)

        if result.get('status') == MessageStatus.PENDING_APPROVAL:
            any_success = True
            content = result.get('content', '')
            angle = result.get('angle')
            model = result.get('model')

            if channel == LeadChannel.EMAIL:
                email_result = _save_message(lead, LeadChannel.EMAIL, content, angle, model)
                results = [email_result]
            elif channel == LeadChannel.AMBOS:
                # Duplica a mesma mensagem para email (n8n gera 1x)
                email_result = _save_message(lead, LeadChannel.EMAIL, content, angle, model)
                results = [result, email_result]
                logger.info(f"[AMBOS] Duplicated message for lead {lead.id}: "
                            f"whatsapp_id={result['message_id']}, email_id={email_result['message_id']}")
        elif channel in (LeadChannel.EMAIL, LeadChannel.AMBOS):
            # n8n retornou processing ou vazio
            if not last_error:
                last_error = f"n8n retornou status {result.get('status')} para whatsapp"
    except Exception as e:
        last_error = str(e)
        results.append({'channel': LeadChannel.WHATSAPP, 'status': ProspectingStatus.FAILED, 'error': str(e)})

    lead.in_execution = False
    if any_success:
        lead.prospecting_status = ProspectingStatus.PENDING_APPROVAL
    elif last_error:
        lead.prospecting_status = ProspectingStatus.FAILED
    else:
        lead.prospecting_status = ProspectingStatus.NOVO
    sync_prospecting_stage(lead, lead.prospecting_status)
    db.session.commit()

    return api_response(data={'results': results})


@prospecting_bp.route('/prospecting/campaign/<int:campaign_id>/generate-messages', methods=['POST'])
@login_required
def generate_campaign_messages(campaign_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=current_user.company_id).first_or_404()
    data = request.json or {}
    lead_ids = data.get('lead_ids', [])
    channel = data.get('channel', LeadChannel.WHATSAPP)

    if not lead_ids:
        # Generate for all leads in campaign
        leads = Lead.query.filter_by(prospecting_campaign_id=campaign_id, company_id=current_user.company_id).all()
        lead_ids = [l.id for l in leads]

    setting = ProspectingSetting.query.filter_by(company_id=current_user.company_id).first()
    if not setting or not setting.generate_message_webhook_url:
        return api_response(success=False, error='Webhook de geração não configurado', status=400)

    triggered = 0
    errors = []

    def _generate_for_lead(lid, ch):
        nonlocal triggered
        lead = Lead.query.filter_by(id=lid, company_id=current_user.company_id).first()
        if not lead:
            return
        if lead.in_execution or lead.prospecting_status == ProspectingStatus.EM_EXECUCAO:
            errors.append(f'Lead {lid} ({ch}): já em execução')
            return

        try:
            lead.in_execution = True
            lead.prospecting_status = ProspectingStatus.EM_EXECUCAO
            sync_prospecting_stage(lead, ProspectingStatus.EM_EXECUCAO)
            db.session.commit()

            payload = {
                'action': 'generate_message',
                'tenant_id': current_user.company_id,
                'lead_id': lead.id,
                'campaign_id': lead.prospecting_campaign_id,
                'channel': ch
            }

            success, response_payload, error_msg = send_outbound_webhook(
                tenant_id=current_user.company_id,
                lead_id=lead.id,
                action='generate_message',
                webhook_url=setting.generate_message_webhook_url,
                payload=payload
            )

            if success:
                message_text = response_payload.get('message', '') if response_payload else ''
                if message_text:
                    angle = response_payload.get('angle', 'Atrair')
                    model = response_payload.get('model', 'llama-3.1-8b-instant')
                    _save_message(lead, ch, message_text, angle, model)
                    lead.prospecting_status = ProspectingStatus.PENDING_APPROVAL
                    lead.last_angle = angle
                else:
                    lead.prospecting_status = ProspectingStatus.NOVO
                lead.in_execution = False
                db.session.commit()
                triggered += 1
            else:
                raise Exception(error_msg or 'Erro webhook')

        except Exception as e:
            lead.in_execution = False
            lead.prospecting_status = ProspectingStatus.FAILED
            sync_prospecting_stage(lead, ProspectingStatus.FAILED)
            db.session.commit()
            errors.append(f'Lead {lid} ({ch}): {str(e)}')

    channels = [LeadChannel.WHATSAPP, LeadChannel.EMAIL] if channel == LeadChannel.AMBOS else [channel]

    for lid in lead_ids:
        for ch in channels:
            _generate_for_lead(lid, ch)

    return api_response(data={
        'triggered': triggered,
        'errors': errors,
        'total': len(lead_ids) * len(channels)
    })


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/approve-message/<int:message_id>', methods=['POST'])
@login_required
def approve_message(lead_id, message_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    message = ProspectingMessage.query.filter_by(id=message_id, lead_id=lead_id).first_or_404()

    if message.status not in [MessageStatus.PENDENTE, MessageStatus.AGUARDANDO_APROVACAO, MessageStatus.PENDING_APPROVAL]:
        return api_response(success=False, error='Mensagem não pode ser aprovada neste status', status=400)

    setting = ProspectingSetting.query.filter_by(company_id=current_user.company_id).first()

    webhook_url = None
    action = None
    if message.channel == LeadChannel.WHATSAPP:
        webhook_url = setting.send_whatsapp_webhook_url if setting else None
        action = 'send_whatsapp'
    elif message.channel == LeadChannel.EMAIL:
        webhook_url = (setting.send_email_webhook_url or setting.send_whatsapp_webhook_url) if setting else None
        action = 'send_email'

    if not webhook_url:
        return api_response(success=False, error=f'Webhook de envio por {message.channel} não configurado', status=400)

    payload = {
        'action': action,
        'tenant_id': current_user.company_id,
        'lead_id': lead.id,
        'message_id': message.id,
        'channel': message.channel,
        'content': message.content,
        'lead_name': lead.name,
        'lead_email': lead.email,
        'lead_phone': lead.phone
    }

    try:
        success, response_payload, error_msg = send_outbound_webhook(
            tenant_id=current_user.company_id,
            lead_id=lead.id,
            action=action,
            webhook_url=webhook_url,
            payload=payload
        )

        if success:
            message.status = MessageStatus.SENT
            message.approved_by = current_user.id
            message.approved_at = datetime.utcnow()
            message.sent_at = datetime.utcnow()

            if message.channel == LeadChannel.WHATSAPP:
                lead.wa_attempts = (lead.wa_attempts or 0) + 1
            elif message.channel == LeadChannel.EMAIL:
                lead.email_attempts = (lead.email_attempts or 0) + 1

            lead.last_contact_at = datetime.utcnow()
            lead.prospecting_status = ProspectingStatus.CONTATADO
            sync_prospecting_stage(lead, ProspectingStatus.CONTATADO)

            if lead.prospecting_campaign_id:
                campaign = ProspectingCampaign.query.get(lead.prospecting_campaign_id)
                if campaign and campaign.followup_interval_days:
                    lead.next_action_at = datetime.utcnow() + timedelta(days=campaign.followup_interval_days)

            interaction = Interaction(
                lead_id=lead.id,
                company_id=current_user.company_id,
                user_id=current_user.id,
                type=message.channel,
                content=message.content
            )
            db.session.add(interaction)
            db.session.commit()

            return api_response(data={'status': MessageStatus.SENT, 'sent_at': message.sent_at.isoformat()})
        else:
            raise Exception(error_msg or "Webhook retornou erro")

    except Exception as e:
        message.status = MessageStatus.FAILED
        message.error_message = str(e)
        db.session.commit()

        lead.prospecting_status = ProspectingStatus.FAILED
        db.session.commit()

        return api_response(success=False, error=f'Erro ao enviar mensagem: {str(e)}', status=500)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/reject-message/<int:message_id>', methods=['POST'])
@login_required
def reject_message(lead_id, message_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    message = ProspectingMessage.query.filter_by(id=message_id, lead_id=lead_id).first_or_404()

    feedback = None
    save_to_campaign = False

    if request.is_json:
        data = request.json or {}
        feedback = data.get('feedback')
        save_to_campaign = data.get('save_to_campaign', False)

    message.status = MessageStatus.REJEITADA
    db.session.commit()

    if feedback:
        if save_to_campaign and lead.prospecting_campaign:
            campaign = lead.prospecting_campaign
            if campaign.restrictions:
                campaign.restrictions = f"{campaign.restrictions}\n- {feedback}"
            else:
                campaign.restrictions = f"- {feedback}"
            db.session.commit()

        setting = ProspectingSetting.query.filter_by(company_id=current_user.company_id).first()
        if not setting or not setting.generate_message_webhook_url:
            return api_response(success=False, error='Webhook de geração de mensagem não configurado', status=400)

        channel = message.channel or lead.preferred_channel or LeadChannel.WHATSAPP

        lead.in_execution = True
        lead.prospecting_status = ProspectingStatus.EM_EXECUCAO
        sync_prospecting_stage(lead, ProspectingStatus.EM_EXECUCAO)
        db.session.commit()

        try:
            result = _generate_single_message(lead, setting, channel, feedback=feedback, step_number=message.step_number)

            lead.in_execution = False
            lead.prospecting_status = ProspectingStatus.PENDING_APPROVAL
            sync_prospecting_stage(lead, ProspectingStatus.PENDING_APPROVAL)
            db.session.commit()

            return api_response(data={'regenerated': True, 'result': result})
        except Exception as e:
            lead.in_execution = False
            lead.prospecting_status = ProspectingStatus.FAILED
            sync_prospecting_stage(lead, ProspectingStatus.FAILED)
            db.session.commit()
            return api_response(success=False, error=f'Erro ao regenerar mensagem: {str(e)}', status=500)
    else:
        lead.prospecting_status = ProspectingStatus.NOVO
        lead.in_execution = False
        sync_prospecting_stage(lead, ProspectingStatus.NOVO)
        db.session.commit()

        return api_response(success=True)


@prospecting_bp.route('/prospecting/message/<int:message_id>/edit', methods=['PUT'])
@login_required
def edit_message(message_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    message = ProspectingMessage.query.filter_by(id=message_id, company_id=current_user.company_id).first_or_404()

    if message.status not in [MessageStatus.PENDENTE, MessageStatus.AGUARDANDO_APROVACAO, MessageStatus.PENDING_APPROVAL]:
        return api_response(success=False, error='Só é possível editar mensagens pendentes', status=400)

    data = request.json or {}
    new_content = data.get('content')
    if not new_content or not new_content.strip():
        return api_response(success=False, error='Conteúdo não pode ficar vazio', status=400)

    message.content = new_content.strip()
    db.session.commit()

    return api_response(data={'message_id': message.id, 'content': message.content})


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/update-status', methods=['POST'])
@login_required
def update_lead_status(lead_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    data = request.json

    lead.prospecting_status = data.get('status', lead.prospecting_status)
    lead.preferred_channel = data.get('preferred_channel', lead.preferred_channel)
    lead.lead_score = data.get('score', lead.lead_score)

    new_campaign_id = data.get('campaign_id')
    if new_campaign_id and new_campaign_id != lead.prospecting_campaign_id:
        campaign = ProspectingCampaign.query.get(new_campaign_id)
        if campaign and campaign.company_id == current_user.company_id:
            lead.prospecting_campaign_id = campaign.id
            if campaign.pipeline_id:
                lead.pipeline_id = campaign.pipeline_id
                from models import PipelineStage
                first_stage = PipelineStage.query.filter_by(pipeline_id=campaign.pipeline_id).order_by(PipelineStage.order).first()
                if first_stage:
                    lead.pipeline_stage_id = first_stage.id

    sync_prospecting_stage(lead, lead.prospecting_status)
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/pause', methods=['POST'])
@login_required
def pause_lead(lead_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    lead.prospecting_status = ProspectingStatus.PAUSADO
    lead.in_execution = False
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/resume', methods=['POST'])
@login_required
def resume_lead(lead_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    lead.prospecting_status = ProspectingStatus.NOVO
    sync_prospecting_stage(lead, ProspectingStatus.NOVO)
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/discard', methods=['POST'])
@login_required
def discard_lead(lead_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    lead.prospecting_status = ProspectingStatus.DESCARTADO
    lead.in_execution = False
    sync_prospecting_stage(lead, ProspectingStatus.DESCARTADO)
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/add-to-campaign', methods=['POST'])
@login_required
def add_to_campaign(lead_id):
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    data = request.json

    campaign_id = data.get('campaign_id')
    if campaign_id:
        campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=current_user.company_id).first_or_404()
        lead.prospecting_campaign_id = campaign_id
        lead.prospecting_status = ProspectingStatus.NOVO
        
        # Associar o lead ao pipeline e primeiro estágio correspondente
        if campaign.pipeline_id:
            lead.pipeline_id = campaign.pipeline_id
            from models import PipelineStage
            first_stage = PipelineStage.query.filter_by(pipeline_id=campaign.pipeline_id).order_by(PipelineStage.order).first()
            if first_stage:
                lead.pipeline_stage_id = first_stage.id
        
        db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/api/prospecting/base-leads')
@login_required
def list_base_leads():
    """Lista leads da base do CRM disponíveis para adicionar a uma campanha."""
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    search = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 30
    only_without_campaign = request.args.get('only_free', 'false').lower() == 'true'

    query = Lead.query.filter_by(company_id=current_user.company_id)

    # Filtro: apenas leads sem campanha associada
    if only_without_campaign:
        query = query.filter(Lead.prospecting_campaign_id.is_(None))

    # Busca por nome, empresa ou telefone
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                Lead.name.ilike(like),
                Lead.email.ilike(like),
                Lead.phone.ilike(like)
            )
        )

    total = query.count()
    leads = query.order_by(Lead.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    data = []
    for l in leads:
        data.append({
            'id': l.id,
            'name': l.name,
            'email': l.email or '',
            'phone': l.phone or l.whatsapp or '',
            'interest': l.interest or '',
            'status': l.status or '',
            'has_campaign': l.prospecting_campaign_id is not None,
            'campaign_id': l.prospecting_campaign_id,
            'preferred_channel': l.preferred_channel or LeadChannel.WHATSAPP,
        })

    return api_response(data={'leads': data, 'total': total, 'page': page, 'per_page': per_page})


@prospecting_bp.route('/api/prospecting/bulk-add-to-campaign', methods=['POST'])
@login_required
def bulk_add_to_campaign():
    """Adiciona múltiplos leads da base a uma campanha de prospecção."""
    allowed, error = check_prospecting_access()
    if not allowed:
        return api_response(success=False, error=error, status=403)

    data = request.json or {}
    campaign_id = data.get('campaign_id')
    lead_ids = data.get('lead_ids', [])
    preferred_channel = data.get('preferred_channel', LeadChannel.WHATSAPP)

    if not campaign_id or not lead_ids:
        return api_response(success=False, error='Informe a campanha e ao menos um lead.', status=400)

    campaign = ProspectingCampaign.query.filter_by(
        id=campaign_id, company_id=current_user.company_id
    ).first_or_404()

    from models import PipelineStage
    first_stage = None
    if campaign.pipeline_id:
        first_stage = PipelineStage.query.filter_by(
            pipeline_id=campaign.pipeline_id
        ).order_by(PipelineStage.order).first()

    added = 0
    already_in = 0
    for lead_id in lead_ids:
        lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first()
        if not lead:
            continue

        if lead.prospecting_campaign_id and lead.prospecting_campaign_id == campaign_id:
            already_in += 1
            continue

        lead.prospecting_campaign_id = campaign_id
        lead.prospecting_status = ProspectingStatus.NOVO
        if not lead.preferred_channel:
            lead.preferred_channel = preferred_channel

        if campaign.pipeline_id:
            lead.pipeline_id = campaign.pipeline_id
            if first_stage:
                lead.pipeline_stage_id = first_stage.id

        added += 1

    db.session.commit()

    return api_response(data={
        'added': added,
        'already_in': already_in,
        'message': f'{added} lead(s) adicionado(s) à campanha "{campaign.name}".'
    })



@prospecting_bp.route('/api/prospecting/search')
@login_required
def search_places():
    query = request.args.get('query')
    city = request.args.get('city')
    state = request.args.get('state')
    radius = request.args.get('radius', type=int)
    min_rating = request.args.get('min_rating', type=float)
    min_reviews = request.args.get('min_reviews', type=int)
    pagetoken = request.args.get('pagetoken')

    if not query and not pagetoken:
        return api_response(success=False, error='Query or pagetoken is required', status=400)

    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    api_key = integration.api_key if integration and integration.is_active else None

    if not api_key:
        return api_response(success=False, error='API Key not configured', status=500)

    all_results = []
    next_page_token = None

    try:
        import time

        if pagetoken:
            # Paginação explícita (Load More) - retorna apenas a próxima página
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                'pagetoken': pagetoken,
                'key': api_key
            }
            time.sleep(0.5)
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            all_results = data.get('results', [])
            next_page_token = data.get('next_page_token')
        else:
            cities = [c.strip() for c in city.split(',')] if city else [None]
            for current_city in cities:
                search_query = query
                if current_city: search_query += f", {current_city}"
                if state: search_query += f", {state}"
                search_query += ", Brasil"

                url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                params = {
                    'query': search_query,
                    'key': api_key,
                    'language': 'pt-BR'
                }

                if radius and current_city:
                    geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
                    geo_params = {'address': f"{current_city}, {state or ''}, Brasil", 'key': api_key}
                    geo_resp = requests.get(geo_url, params=geo_params).json()
                    if geo_resp.get('status') == 'OK':
                        loc = geo_resp['results'][0]['geometry']['location']
                        params['location'] = f"{loc['lat']},{loc['lng']}"
                        params['radius'] = radius * 1000

                # Paginação lazy: retorna 1 página por vez com next_page_token.
                # O frontend chama novamente com pagetoken para carregar mais resultados.
                # Isso evita timeout no Vercel (max 30s por função serverless).
                city_token = None
                page_count = 0
                while page_count < 1:
                    this_params = params.copy()
                    if city_token:
                        this_params = {'pagetoken': city_token, 'key': api_key}
                        time.sleep(0.5)

                    response = requests.get(url, params=this_params, timeout=10)
                    data = response.json()

                    if data.get('status') != 'OK':
                        break

                    all_results.extend(data.get('results', []))
                    city_token = data.get('next_page_token')

                    # Capturar o token da primeira cidade para o Load More
                    if city_token and not next_page_token:
                        next_page_token = city_token

                    page_count += 1
                    if not city_token:
                        break

        # Para múltiplas cidades, desabilitar o "Load More" pois o token
        # só se refere à primeira cidade
        if city and ',' in city:
            next_page_token = None

        unique_results = {p['place_id']: p for p in all_results}.values()
        existing_place_ids = {l.google_place_id for l in Lead.query.filter_by(company_id=current_user.company_id).filter(Lead.google_place_id != None).all()}

        final_results = []
        for place in unique_results:
            rating = place.get('rating', 0)
            reviews = place.get('user_ratings_total', 0)

            if min_rating and rating < min_rating: continue
            if min_reviews and reviews < min_reviews: continue

            place_id = place.get('place_id')
            is_duplicate = place_id in existing_place_ids

            final_results.append({
                'place_id': place_id,
                'name': place.get('name'),
                'formatted_address': place.get('formatted_address'),
                'rating': rating,
                'user_ratings_total': reviews,
                'types': place.get('types', []),
                'is_duplicate': is_duplicate,
                'phone': place.get('formatted_phone_number'),
                'website': place.get('website')
            })

        return api_response(data={
            'results': final_results,
            'count': len(final_results),
            'next_page_token': next_page_token
        })

    except Exception as e:
        return api_response(success=False, error=str(e), status=500)


@prospecting_bp.route('/api/prospecting/search-cnae')
@login_required
def search_cnae():
    cnae = request.args.get('cnae')
    city = request.args.get('city')
    state = request.args.get('state')

    if not cnae:
        return api_response(success=False, error='CNAE is required', status=400)

    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='cnpja').first()
    api_key = integration.api_key if integration and integration.is_active else None

    if not api_key:
        return api_response(success=False, error='A busca por CNAE requer integração com CNPJA ativa.', status=400)

    try:
        results = CNPJAService.search_by_cnae(cnae, city, state, api_key)

        if isinstance(results, dict) and "error" in results:
            return api_response(success=False, error=results.get('error'), status=500)

        existing_tax_ids = {l.cnpj.replace('.', '').replace('/', '').replace('-', '') for l in Lead.query.filter(Lead.company_id == current_user.company_id, Lead.cnpj != None).all()}

        final_results = []
        for r in results:
            tax_id_clean = r.get('tax_id', '').replace('.', '').replace('/', '').replace('-', '')
            addr = r.get('address', {})
            formatted_addr = f"{addr.get('street', '')}, {addr.get('number', 'S/N')} - {addr.get('district', '')}, {addr.get('city', '')}/{addr.get('state', '')}"

            final_results.append({
                'place_id': r.get('tax_id'),
                'name': r.get('name'),
                'formatted_address': formatted_addr,
                'rating': 0,
                'user_ratings_total': 0,
                'types': [r.get('mainActivity', {}).get('text', 'Empresa')],
                'is_duplicate': tax_id_clean in existing_tax_ids,
                'phone': None,
                'website': None,
                'tax_id': r.get('tax_id')
            })

        return api_response(data={
            'results': final_results,
            'count': len(final_results),
            'next_page_token': None
        })
    except Exception as e:
        return api_response(success=False, error=str(e), status=500)


@prospecting_bp.route('/api/prospecting/favorites', methods=['GET', 'POST'])
@login_required
def handle_favorites():
    if request.method == 'POST':
        data = request.json
        new_fav = ProspectingSearch(
            name=data.get('name'),
            query=data.get('query'),
            city=data.get('city'),
            state=data.get('state'),
            radius=data.get('radius'),
            min_rating=data.get('min_rating'),
            min_reviews=data.get('min_reviews'),
            company_id=current_user.company_id
        )
        db.session.add(new_fav)
        db.session.commit()
        return api_response(data={'id': new_fav.id})
    else:
        favs = ProspectingSearch.query.filter_by(company_id=current_user.company_id).order_by(ProspectingSearch.created_at.desc()).all()
        return api_response(data=[{
            'id': f.id, 'name': f.name, 'query': f.query, 'city': f.city,
            'state': f.state, 'radius': f.radius, 'min_rating': f.min_rating, 'min_reviews': f.min_reviews
        } for f in favs])


@prospecting_bp.route('/api/prospecting/favorites/<int:fav_id>', methods=['DELETE'])
@login_required
def delete_favorite(fav_id):
    fav = ProspectingSearch.query.filter_by(id=fav_id, company_id=current_user.company_id).first_or_404()
    db.session.delete(fav)
    db.session.commit()
    return api_response(success=True)


@prospecting_bp.route('/api/prospecting/history')
@login_required
def get_import_history():
    history = Lead.query.filter(
        Lead.company_id == current_user.company_id,
        Lead.google_place_id != None
    ).order_by(Lead.created_at.desc()).limit(50).all()

    return jsonify({
        'success': True,
        'data': [{
            'id': l.id,
            'name': l.name,
            'imported_at': l.created_at.isoformat() if l.created_at else None
        } for l in history]
    })


@prospecting_bp.route('/api/prospecting/pipelines')
@login_required
def get_prospecting_pipelines():
    from models import Pipeline, PipelineStage
    pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
    result = []
    for p in pipelines:
        stages = PipelineStage.query.filter_by(pipeline_id=p.id).order_by(PipelineStage.order).all()
        result.append({
            'id': p.id,
            'name': p.name,
            'stages': [{'id': s.id, 'name': s.name} for s in stages]
        })
    return jsonify({'success': True, 'data': result})


@prospecting_bp.route('/api/prospecting/import', methods=['POST'])
@login_required
def import_lead():
    data = request.json
    places = data.get('places', [])
    stage_id = data.get('stage_id')

    if not places and data.get('place_id'):
        places = [data]

    if not places:
        return api_response(success=False, error='places is required', status=400)

    from models import Pipeline, PipelineStage
    target_stage_id = stage_id
    target_pipeline_id = None

    if target_stage_id:
        s = PipelineStage.query.get(target_stage_id)
        if s: target_pipeline_id = s.pipeline_id

    if not target_stage_id or not target_pipeline_id:
        default_p = Pipeline.query.filter_by(company_id=current_user.company_id).first()
        if default_p:
            target_pipeline_id = default_p.id
            first_s = PipelineStage.query.filter_by(pipeline_id=default_p.id).order_by(PipelineStage.order).first()
            if first_s: target_stage_id = first_s.id

    # Verificar se o pipeline de destino pertence a alguma campanha de prospecção
    campaign = ProspectingCampaign.query.filter_by(pipeline_id=target_pipeline_id, company_id=current_user.company_id).first()
    target_segment = campaign.target_segment if campaign else None

    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    api_key = integration.api_key if integration and integration.is_active else None

    from utils.segment_validation import is_segment_match

    imported_count = 0
    rejected_segment = 0
    duplicate_count = 0
    errors = []
    new_lead_ids = []

    for p in places:
        place_id = p.get('place_id')
        if not place_id: continue

        # Validação de segmento
        if target_segment and not is_segment_match(p, target_segment):
            logger.info(f"Segment mismatch: {p.get('name')} não corresponde ao segmento '{target_segment}'")
            rejected_segment += 1
            continue

        phone = p.get('phone')
        website = p.get('website')

        if api_key and not phone:
            try:
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_params = {
                    'place_id': place_id,
                    'fields': 'formatted_phone_number,international_phone_number,website',
                    'key': api_key
                }
                res = requests.get(details_url, params=details_params, timeout=5).json()
                if res.get('status') == 'OK':
                    result_data = res.get('result', {})
                    phone = result_data.get('international_phone_number') or result_data.get('formatted_phone_number') or phone
                    website = result_data.get('website') or website
            except:
                pass

        try:
            if Lead.query.filter_by(company_id=current_user.company_id, google_place_id=place_id).first():
                duplicate_count += 1
                continue

            # Checagem de duplicata por telefone
            if phone:
                phone_clean = ''.join(filter(str.isdigit, phone))
                if phone_clean:
                    existing_by_phone = Lead.query.filter(
                        Lead.company_id == current_user.company_id,
                        db.or_(
                            Lead.phone.contains(phone_clean[-8:]),
                            Lead.whatsapp.contains(phone_clean[-8:])
                        )
                    ).first()
                    if existing_by_phone:
                        errors.append(f"Lead '{p.get('name')}' pulado: telefone já existe (lead #{existing_by_phone.id})")
                        continue

            with db.session.begin_nested():
                name_val = p.get('name') or 'Sem Nome'
                new_lead = Lead(
                    name=name_val[:100],
                    company_id=current_user.company_id,
                    assigned_to_id=current_user.id,
                    status='new',
                    pipeline_id=target_pipeline_id,
                    pipeline_stage_id=target_stage_id,
                    source='google_maps',
                    phone=phone[:50] if phone else None,
                    website=website[:200] if website else None,
                    address=p.get('formatted_address')[:255] if p.get('formatted_address') else None,
                    google_place_id=place_id[:100] if place_id else None,
                    gmb_rating=p.get('rating', 0),
                    gmb_reviews=p.get('user_ratings_total', 0),
                    notes=f"Importado via Google Maps em {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}",
                    prospecting_status=ProspectingStatus.NOVO,
                    prospecting_campaign_id=campaign.id if campaign else None
                )
                db.session.add(new_lead)
                db.session.flush()
                new_lead_ids.append(new_lead.id)
            imported_count += 1
        except Exception as e:
            errors.append(f"Error {p.get('name')}: {str(e)}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errors.append(f"Commit error: {str(e)}")
    return api_response(data={
        'imported_count': imported_count,
        'lead_ids': new_lead_ids,
        'rejected_segment': rejected_segment,
        'duplicate_count': duplicate_count,
        'errors': errors
    })


@prospecting_bp.route('/api/prospecting/backfill-phones', methods=['POST'])
@login_required
def backfill_phones():
    from models import Integration, Lead
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    api_key = integration.api_key if integration and integration.is_active else None

    if not api_key:
        return api_response(success=False, error='API Key not configured', status=500)

    data = request.json or {}
    lead_ids = data.get('lead_ids', [])

    query = Lead.query.filter(
        Lead.company_id == current_user.company_id,
        Lead.google_place_id != None,
        (Lead.phone == None) | (Lead.phone == '')
    )

    if lead_ids:
        query = query.filter(Lead.id.in_(lead_ids))

    leads = query.all()

    import requests
    import time

    updated_count = 0
    errors = []

    for lead in leads:
        try:
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                'place_id': lead.google_place_id,
                'fields': 'formatted_phone_number,international_phone_number,website',
                'key': api_key
            }
            res = requests.get(details_url, params=details_params, timeout=10).json()
            if res.get('status') == 'OK':
                result_data = res.get('result', {})
                phone = result_data.get('international_phone_number') or result_data.get('formatted_phone_number')
                website = result_data.get('website')

                if phone:
                    lead.phone = phone
                    updated_count += 1
                if website and not lead.website:
                    lead.website = website

            time.sleep(0.3)
        except Exception as e:
            errors.append(f"Error {lead.id}: {str(e)}")

    db.session.commit()
    return api_response(data={'updated_count': updated_count, 'errors': errors, 'total_scanned': len(leads)})


@prospecting_bp.route('/prospecting/niches', methods=['GET'])
@login_required
def niches_page():
    from models import ProspectingNiche, ProspectingCampaign

    niches = ProspectingNiche.query.filter_by(
        company_id=current_user.company_id
    ).order_by(ProspectingNiche.name).all()

    campaigns = ProspectingCampaign.query.filter_by(
        company_id=current_user.company_id,
        is_active=True
    ).order_by(ProspectingCampaign.name).all()

    return render_template('prospecting/niches.html', niches=niches, campaigns=campaigns)


@prospecting_bp.route('/api/prospecting/niche/today', methods=['GET'])
@login_required
def get_niche_today():
    from datetime import datetime
    from models import ProspectingNiche

    company_id = current_user.company_id
    today_weekday = datetime.utcnow().weekday()

    niches = ProspectingNiche.query.filter_by(
        company_id=company_id,
        is_active=True
    ).all()

    today_niche = None
    for niche in niches:
        weekdays = niche.active_weekdays or []
        if today_weekday in weekdays:
            today_niche = niche
            break

    if not today_niche and niches:
        today_niche = niches[0]

    if not today_niche:
        return api_response(success=False, error='Nenhum nicho configurado.')

    return api_response(data={
        'niche': {
            'id': today_niche.id,
            'name': today_niche.name,
            'search_query': today_niche.search_query,
            'cities': today_niche.cities or [],
            'city': today_niche.city,
            'state': today_niche.state,
            'min_rating': today_niche.min_rating,
            'min_reviews': today_niche.min_reviews,
            'default_campaign_id': today_niche.default_campaign_id,
            'tenant_id': company_id
        }
    })


@prospecting_bp.route('/api/prospecting/niches', methods=['GET'])
@login_required
def list_niches():
    from models import ProspectingNiche
    niches = ProspectingNiche.query.filter_by(
        company_id=current_user.company_id
    ).order_by(ProspectingNiche.name).all()

    return api_response(data={'niches': [{
        'id': n.id,
        'name': n.name,
        'search_query': n.search_query,
        'cities': n.cities or [],
        'city': n.city,
        'state': n.state,
        'min_rating': n.min_rating,
        'min_reviews': n.min_reviews,
        'active_weekdays': n.active_weekdays or [],
        'default_campaign_id': n.default_campaign_id,
        'is_active': n.is_active
    } for n in niches]})


@prospecting_bp.route('/api/prospecting/niches', methods=['POST'])
@login_required
def create_niche():
    from models import ProspectingNiche
    data = request.json or {}

    if not data.get('search_query') or not data.get('cities'):
        return api_response(success=False, error='search_query e cities são obrigatórios', status=400)

    niche = ProspectingNiche(
        company_id=current_user.company_id,
        name=data.get('name') or data['search_query'],
        search_query=data['search_query'],
        cities=data['cities'],
        state=data.get('state', 'PR'),
        min_rating=float(data.get('min_rating', 3.5)),
        min_reviews=int(data.get('min_reviews', 5)),
        active_weekdays=data.get('active_weekdays', [0, 1, 2, 3, 4]),
        default_campaign_id=data.get('default_campaign_id'),
        is_active=True
    )
    db.session.add(niche)
    db.session.commit()

    return api_response(data={'id': niche.id, 'name': niche.name})


@prospecting_bp.route('/api/prospecting/niches/<int:niche_id>', methods=['PUT'])
@login_required
def update_niche(niche_id):
    from models import ProspectingNiche
    niche = ProspectingNiche.query.filter_by(
        id=niche_id, company_id=current_user.company_id
    ).first_or_404()

    data = request.json or {}
    for field in ['name', 'search_query', 'cities', 'state', 'min_rating',
                  'min_reviews', 'active_weekdays', 'default_campaign_id', 'is_active']:
        if field in data:
            setattr(niche, field, data[field])

    db.session.commit()
    return api_response(data={'id': niche.id, 'updated': True})


@prospecting_bp.route('/api/prospecting/niches/<int:niche_id>', methods=['DELETE'])
@login_required
def delete_niche(niche_id):
    from models import ProspectingNiche
    niche = ProspectingNiche.query.filter_by(
        id=niche_id, company_id=current_user.company_id
    ).first_or_404()
    niche.is_active = False
    db.session.commit()
    return api_response(data={'deleted': True})