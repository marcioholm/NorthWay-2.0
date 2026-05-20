from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import requests
from models import db, Lead, Interaction, ProspectingSearch, Company, ProspectingCampaign, ProspectingMessage, ProspectingSetting, TenantAICredential, ProspectingIntegration
from datetime import datetime, timedelta
from services.cnpj_service import CNPJAService
from utils.crypto import encrypt_api_key, decrypt_api_key

prospecting_bp = Blueprint('prospecting', __name__)


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
        'novo': 'Lista Fria',
        'em_execucao': 'Lista Fria',
        'aguardando_aprovacao': 'Aguardando Aprovação',
        'contatado': 'Contatado',
        'respondeu': 'Respondeu',
        'interessado': 'Respondeu',
        'reuniao': 'Reunião Agendada',
        'descartado': 'Descartado'
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
    if not current_user.company.has_feature('prospecting'):
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('prospecting.dashboard'))


@prospecting_bp.route('/prospecting/discover')
@login_required
def discover():
    if not current_user.company.has_feature('prospecting'):
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
        total_leads = Lead.query.filter_by(company_id=company_id).filter(
            Lead.prospecting_status.isnot(None)
        ).count()

        aguardando = Lead.query.filter_by(company_id=company_id, prospecting_status='novo').count()
        em_execucao = Lead.query.filter_by(company_id=company_id, prospecting_status='em_execucao').count()
        aguardando_aprovacao = Lead.query.filter_by(company_id=company_id, prospecting_status='aguardando_aprovacao').count()
        contatados = Lead.query.filter_by(company_id=company_id, prospecting_status='contatado').count()
        responderam = Lead.query.filter_by(company_id=company_id, prospecting_status='respondeu').count()
        interessados = Lead.query.filter_by(company_id=company_id, prospecting_status='interessado').count()
        reunioes = Lead.query.filter_by(company_id=company_id, prospecting_status='reuniao').count()
        sem_resposta = Lead.query.filter_by(company_id=company_id, prospecting_status='sem_resposta').count()
        erro_envio = Lead.query.filter_by(company_id=company_id, prospecting_status='erro').count()

        campaigns = ProspectingCampaign.query.filter_by(company_id=company_id, is_active=True).all()
    except Exception as e:
        print(f"Error in dashboard: {e}")
        total_leads = aguardando = em_execucao = aguardando_aprovacao = contatados = 0
        responderam = interessados = reunioes = sem_resposta = erro_envio = 0
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
                           sem_resposta=sem_resposta,
                           erro_envio=erro_envio,
                           campaigns=campaigns)


@prospecting_bp.route('/prospecting/leads')
@login_required
def leads():
    if not current_user.company.has_feature('prospecting'):
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
    if not current_user.company.has_feature('prospecting'):
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
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    data = request.json
    company_id = current_user.company_id

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
        status='rascunho',
        is_active=True,
        pipeline_id=new_pipeline.id
    )

    db.session.add(campaign)
    db.session.commit()

    return api_response(data={'id': campaign.id, 'name': campaign.name})


@prospecting_bp.route('/prospecting/campaign/<int:campaign_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def manage_campaign(campaign_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

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


@prospecting_bp.route('/prospecting/campaign/<int:campaign_id>/details')
@login_required
def campaign_details(campaign_id):
    """Retorna os detalhes da campanha com contatos e mensagens"""
    if not current_user.company_id:
        return api_response(success=False, error='Acesso negado', status=403)
    
    campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=current_user.company_id).first()
    if not campaign:
        return api_response(success=False, error='Campanha não encontrada', status=404)
    
    # Buscar leads da campanha
    leads = Lead.query.filter_by(prospecting_campaign_id=campaign_id).all()
    leads_data = []
    for lead in leads:
        # Buscar última mensagem do lead
        last_msg = ProspectingMessage.query.filter_by(lead_id=lead.id, campaign_id=campaign_id).order_by(ProspectingMessage.created_at.desc()).first()
        
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
    pending_messages = ProspectingMessage.query.filter_by(
        campaign_id=campaign_id, 
        status='aguardando_aprovacao'
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
    sent_count = ProspectingMessage.query.filter_by(campaign_id=campaign_id, status='enviada').count()
    error_count = ProspectingMessage.query.filter_by(campaign_id=campaign_id, status='erro').count()
    
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
            }
        },
        'leads': leads_data,
        'pending_messages': pending_data
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
            from models import Pipeline, Lead
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


@prospecting_bp.route('/prospecting/messages')
@login_required
def messages():
    if not current_user.company.has_feature('prospecting'):
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
    if not current_user.company.has_feature('prospecting'):
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
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    data = request.json
    company_id = current_user.company_id

    setting = ProspectingSetting.query.filter_by(company_id=company_id).first()

    if not setting:
        setting = ProspectingSetting(company_id=company_id)
        db.session.add(setting)

    setting.generate_message_webhook_url = data.get('generate_message_webhook_url')
    setting.send_whatsapp_webhook_url = data.get('send_whatsapp_webhook_url')
    setting.send_email_webhook_url = data.get('send_email_webhook_url')
    setting.daily_send_limit = data.get('daily_send_limit', 50)
    setting.sending_start_time = data.get('sending_start_time', '09:00')
    setting.sending_end_time = data.get('sending_end_time', '18:00')
    setting.manual_approval_required = data.get('manual_approval_required', True)
    setting.default_ai_model = data.get('default_ai_model', 'gpt-4.1-mini')
    setting.default_tone = data.get('default_tone', 'profissional')

    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/generate-message', methods=['POST'])
@login_required
def generate_message(lead_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    if lead.in_execution or lead.prospecting_status == 'em_execucao':
        return api_response(success=False, error='Já existe uma mensagem sendo gerada para este lead', status=400)

    setting = ProspectingSetting.query.filter_by(company_id=current_user.company_id).first()

    if not setting or not setting.generate_message_webhook_url:
        return api_response(success=False, error='Webhook de geração de mensagem não configurado', status=400)

    lead.in_execution = True
    lead.prospecting_status = 'em_execucao'
    sync_prospecting_stage(lead, 'em_execucao')
    db.session.commit()

    campaign = ProspectingCampaign.query.get(lead.prospecting_campaign_id) if lead.prospecting_campaign_id else None

    payload = {
        'company_id': current_user.company_id,
        'lead_id': lead.id,
        'company_name': current_user.company.name,
        'responsible_name': current_user.name,
        'sender_name': current_user.name,
        'phone': lead.phone,
        'email': lead.email,
        'lead_name': lead.name,
        'segment': lead.interest,
        'preferred_channel': lead.preferred_channel or 'whatsapp',
        'last_angle': lead.last_angle,
        'system_prompt_rule': "Nunca use placeholders como [Seu Nome], [Empresa], [Nome da Empresa] ou similares. Use sempre os dados reais do remetente e da empresa fornecidos no contexto.",
        'campaign': {
            'name': campaign.name if campaign else 'Sem campanha',
            'objective': campaign.objective if campaign else '',
            'tone_of_voice': campaign.tone_of_voice if campaign else 'profissional',
            'offer': campaign.offer if campaign else '',
            'main_angle': campaign.main_angle if campaign else '',
            'default_cta': campaign.default_cta if campaign else 'Agende uma conversa',
            'restrictions': (campaign.restrictions if campaign else '') + "\nREGRA OBRIGATÓRIA: Nunca use placeholders como [Seu Nome], [Empresa], [Nome da Empresa] ou similares. Use sempre os dados reais."
        }
    }

    try:
        response = requests.post(
            setting.generate_message_webhook_url,
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            result = response.json()
            message_text = result.get('message', '')
            angle = result.get('angle', 'Atrair')
            model = result.get('model', 'gpt-4.1-mini')

            prospecting_msg = ProspectingMessage(
                company_id=current_user.company_id,
                lead_id=lead.id,
                campaign_id=lead.prospecting_campaign_id,
                channel=lead.preferred_channel or 'whatsapp',
                type='outbound',
                status='aguardando_aprovacao',
                content=message_text,
                ai_model=model,
                created_at=datetime.utcnow()
            )
            db.session.add(prospecting_msg)

            lead.prospecting_status = 'aguardando_aprovacao'
            lead.last_angle = angle
            lead.in_execution = False
            sync_prospecting_stage(lead, 'aguardando_aprovacao')

            db.session.commit()

            return api_response(data={
                'message_id': prospecting_msg.id,
                'content': message_text,
                'status': 'aguardando_aprovacao'
            })
        else:
            raise Exception(f"Webhook retornou status {response.status_code}")

    except Exception as e:
        lead.in_execution = False
        lead.prospecting_status = 'erro'
        db.session.commit()

        prospecting_msg = ProspectingMessage(
            company_id=current_user.company_id,
            lead_id=lead.id,
            campaign_id=lead.prospecting_campaign_id,
            channel=lead.preferred_channel or 'whatsapp',
            type='outbound',
            status='erro',
            content='',
            error_message=str(e)
        )
        db.session.add(prospecting_msg)
        db.session.commit()

        return api_response(success=False, error=f'Erro ao gerar mensagem: {str(e)}', status=500)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/approve-message/<int:message_id>', methods=['POST'])
@login_required
def approve_message(lead_id, message_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    message = ProspectingMessage.query.filter_by(id=message_id, lead_id=lead_id).first_or_404()

    if message.status not in ['pendente', 'aguardando_aprovacao']:
        return api_response(success=False, error='Mensagem não pode ser aprovada neste status', status=400)

    setting = ProspectingSetting.query.filter_by(company_id=current_user.company_id).first()

    webhook_url = None
    if message.channel == 'whatsapp':
        webhook_url = setting.send_whatsapp_webhook_url if setting else None
    elif message.channel == 'email':
        webhook_url = setting.send_email_webhook_url if setting else None

    if not webhook_url:
        return api_response(success=False, error=f'Webhook de envio por {message.channel} não configurado', status=400)

    payload = {
        'lead_id': lead.id,
        'message_id': message.id,
        'channel': message.channel,
        'phone': lead.phone,
        'email': lead.email,
        'content': message.content,
        'company_id': current_user.company_id
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            result = response.json()

            if result.get('success'):
                message.status = 'enviada'
                message.approved_by = current_user.id
                message.approved_at = datetime.utcnow()
                message.sent_at = datetime.utcnow()

                if message.channel == 'whatsapp':
                    lead.wa_attempts = (lead.wa_attempts or 0) + 1
                elif message.channel == 'email':
                    lead.email_attempts = (lead.email_attempts or 0) + 1

                lead.last_contact_at = datetime.utcnow()
                lead.prospecting_status = 'contatado'
                sync_prospecting_stage(lead, 'contatado')

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

                return api_response(data={'status': 'enviada', 'sent_at': message.sent_at.isoformat()})
            else:
                raise Exception(result.get('error', 'Erro desconhecido'))
        else:
            raise Exception(f"Webhook retornou status {response.status_code}")

    except Exception as e:
        message.status = 'erro'
        message.error_message = str(e)
        db.session.commit()

        lead.prospecting_status = 'erro'
        db.session.commit()

        return api_response(success=False, error=f'Erro ao enviar mensagem: {str(e)}', status=500)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/reject-message/<int:message_id>', methods=['POST'])
@login_required
def reject_message(lead_id, message_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    message = ProspectingMessage.query.filter_by(id=message_id, lead_id=lead_id).first_or_404()

    message.status = 'rejeitada'
    db.session.commit()

    lead.prospecting_status = 'novo'
    lead.in_execution = False
    sync_prospecting_stage(lead, 'novo')
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/update-status', methods=['POST'])
@login_required
def update_lead_status(lead_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

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
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    lead.prospecting_status = 'pausado'
    lead.in_execution = False
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/resume', methods=['POST'])
@login_required
def resume_lead(lead_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    lead.prospecting_status = 'novo'
    sync_prospecting_stage(lead, 'novo')
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/discard', methods=['POST'])
@login_required
def discard_lead(lead_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()

    lead.prospecting_status = 'descartado'
    lead.in_execution = False
    sync_prospecting_stage(lead, 'descartado')
    db.session.commit()

    return api_response(success=True)


@prospecting_bp.route('/prospecting/lead/<int:lead_id>/add-to-campaign', methods=['POST'])
@login_required
def add_to_campaign(lead_id):
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    data = request.json

    campaign_id = data.get('campaign_id')
    if campaign_id:
        campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=current_user.company_id).first_or_404()
        lead.prospecting_campaign_id = campaign_id
        lead.prospecting_status = 'novo'
        
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
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

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
            'preferred_channel': l.preferred_channel or 'whatsapp',
        })

    return api_response(data={'leads': data, 'total': total, 'page': page, 'per_page': per_page})


@prospecting_bp.route('/api/prospecting/bulk-add-to-campaign', methods=['POST'])
@login_required
def bulk_add_to_campaign():
    """Adiciona múltiplos leads da base a uma campanha de prospecção."""
    if not current_user.company.has_feature('prospecting'):
        return api_response(success=False, error='Acesso negado', status=403)

    data = request.json or {}
    campaign_id = data.get('campaign_id')
    lead_ids = data.get('lead_ids', [])
    preferred_channel = data.get('preferred_channel', 'whatsapp')

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
        lead.prospecting_status = 'novo'
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
        if pagetoken:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                'pagetoken': pagetoken,
                'key': api_key
            }
            import time
            time.sleep(1.5)
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

                response = requests.get(url, params=params, timeout=10)
                data = response.json()

                if data.get('status') == 'OK':
                    all_results.extend(data.get('results', []))
                    if not next_page_token:
                        next_page_token = data.get('next_page_token')

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

    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    api_key = integration.api_key if integration and integration.is_active else None

    imported_count = 0
    errors = []

    for p in places:
        place_id = p.get('place_id')
        if not place_id: continue

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
                    prospecting_status='novo',
                    prospecting_campaign_id=campaign.id if campaign else None
                )
                db.session.add(new_lead)
            imported_count += 1
        except Exception as e:
            errors.append(f"Error {p.get('name')}: {str(e)}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errors.append(f"Commit error: {str(e)}")
    return api_response(data={'imported_count': imported_count, 'errors': errors})


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