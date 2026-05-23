import os
import time
import requests
from flask import Blueprint, request, jsonify
from functools import wraps
from models import db, Lead, ProspectingCampaign, ProspectingMessage, ProspectingSetting, TenantAICredential, ProspectingIntegration, Interaction, CrmConversation, CrmConversationMessage, CrmConversationMemory, CrmAiLog, CrmChannelIntegration
from datetime import datetime, timedelta
from utils.crypto import decrypt_api_key
from utils.phone import phone_variants
from utils.crypto import decrypt_api_key
import logging

logger = logging.getLogger(__name__)

internal_api_bp = Blueprint('internal_api', __name__, url_prefix='/api/internal')


def model_to_dict(obj):
    """Helper to convert SQLAlchemy model to dict, handling datetime objects."""
    if not obj:
        return None
    d = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        if isinstance(val, (datetime, timedelta)):
            val = str(val)
        d[c.name] = val
    return d


def require_internal_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        expected_key = os.environ.get('CRM_INTERNAL_API_KEY', '')

        if not expected_key:
            return jsonify({'success': False, 'error': 'Internal API not configured'}), 500

        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header[7:]
        if token != expected_key:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 401

        return f(*args, **kwargs)
    return decorated


@internal_api_bp.route('/tenant/ai-credential', methods=['POST'])
@require_internal_auth
def get_ai_credential():
    data = request.json
    tenant_id = data.get('tenant_id')
    provider = data.get('provider')

    logger.info(f"[INTERNAL_AI] Fetching credential: tenant_id={tenant_id}, provider={provider}")

    if not tenant_id or not provider:
        logger.warning(f"[INTERNAL_AI] Missing required fields: tenant_id={tenant_id}, provider={provider}")
        return jsonify({'success': False, 'error': 'tenant_id and provider are required'}), 400

    try:
        credential = TenantAICredential.query.filter_by(
            company_id=tenant_id,
            provider=provider,
            status='active'
        ).first()

        if not credential:
            logger.warning(f"[INTERNAL_AI] Credential not found or inactive for tenant_id={tenant_id}, provider={provider}")
            return jsonify({'success': False, 'error': f'Credential not found or inactive for {provider}'}), 404

        logger.info(f"[INTERNAL_AI] Credential found (ID={credential.id}). Decrypting key...")
        
        decrypted_key = decrypt_api_key(credential.api_key_encrypted)
        
        if not decrypted_key:
            logger.error(f"[INTERNAL_AI] Decryption failed for credential ID={credential.id}")
            return jsonify({'success': False, 'error': 'Failed to decrypt API key'}), 500

        logger.info(f"[INTERNAL_AI] Successfully retrieved and decrypted credential for {provider}")
        
        return jsonify({
            'success': True,
            'data': {
                'provider': credential.provider,
                'api_key': decrypted_key,
                'model': credential.model,
                'base_url': credential.base_url
            }
        })
    except Exception as e:
        logger.error(f"[INTERNAL_AI] Critical error fetching credential: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'}), 500


@internal_api_bp.route('/prospecting/context', methods=['POST'])
@require_internal_auth
def get_prospecting_context():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    campaign_id = data.get('campaign_id')
    action = data.get('action', 'generate_message')

    if not tenant_id or not lead_id:
        return jsonify({'success': False, 'error': 'tenant_id and lead_id are required'}), 400

    # In this CRM, company_id is the tenant_id
    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead não encontrado'}), 404

    # Get campaign: requested, or from lead, or default for company
    campaign = None
    if campaign_id:
        campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=tenant_id).first()
    
    if not campaign and lead.prospecting_campaign_id:
        campaign = ProspectingCampaign.query.get(lead.prospecting_campaign_id)
        
    if not campaign:
        # Fallback to the first active campaign for this company
        campaign = ProspectingCampaign.query.filter_by(company_id=tenant_id, is_active=True).first()

    settings = ProspectingSetting.query.filter_by(company_id=tenant_id).first()

    # Building context for the requested action
    is_automated = action == 'generate_and_send_whatsapp'
    
    # Get AI Credentials if automated
    ai_creds = None
    if is_automated:
        # Try to get the provider from settings or default to openai
        provider = settings.default_ai_model.split('-')[0] if settings and settings.default_ai_model else 'openai'
        if 'gpt' in provider: provider = 'openai'
        elif 'claude' in provider: provider = 'anthropic'
        elif 'gemini' in provider: provider = 'google'
        
        credential = TenantAICredential.query.filter_by(
            company_id=tenant_id,
            provider=provider,
            status='active'
        ).first()
        
        if credential:
            ai_creds = {
                'provider': credential.provider,
                'api_key': decrypt_api_key(credential.api_key_encrypted),
                'model': credential.model or settings.default_ai_model,
                'base_url': credential.base_url
            }

    # Get WhatsApp Integration if automated
    whatsapp_integration = None
    if is_automated:
        integration = ProspectingIntegration.query.filter_by(
            company_id=tenant_id, 
            provider='evolution_api', 
            status='active'
        ).first()
        
        if integration:
            whatsapp_integration = {
                'api_base_url': integration.api_base_url,
                'instance_name': integration.instance_name,
                'display_name': integration.display_name,
                'sender_name': integration.sender_name or integration.display_name,
                'api_key': decrypt_api_key(integration.api_key_encrypted)
            }

    # Get Company Name
    from models import Company
    company_obj = Company.query.get(tenant_id)

    # Build the flattened response as requested by the user
    response = {
        'success': True,
        'tenant_id': tenant_id,
        'company_name': company_obj.name if company_obj else "NorthWay",
        'action': action,
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email,
            'interest': lead.interest,
            'preferred_channel': lead.preferred_channel or 'whatsapp',
            'last_angle': lead.last_angle,
            'notes': lead.notes,
            'prospecting_status': lead.prospecting_status
        },
        'campaign': {
            'id': campaign.id,
            'name': campaign.name,
            'objective': campaign.objective,
            'tone_of_voice': campaign.tone_of_voice,
            'offer': campaign.offer,
            'main_angle': campaign.main_angle,
            'default_cta': campaign.default_cta,
            'restrictions': campaign.restrictions,
            'max_attempts': campaign.max_attempts,
            'followup_interval_days': campaign.followup_interval_days
        } if campaign else None,
        'settings': {
            'default_ai_model': settings.default_ai_model if settings else 'gpt-4o-mini',
            'default_tone': settings.default_tone if settings else 'profissional',
            'manual_approval_required': settings.manual_approval_required if settings else True
        },
        # Full Context for Automation
        'ai_credentials': ai_creds,
        'whatsapp_integration': whatsapp_integration,
        'evolution_base_url': whatsapp_integration['api_base_url'] if whatsapp_integration else None,
        'evolution_api_key': whatsapp_integration['api_key'] if whatsapp_integration else None,
        'evolution_instance': whatsapp_integration['instance_name'] if whatsapp_integration else None
    }

    return jsonify(response)

@internal_api_bp.route('/prospecting/message-generated', methods=['POST'])
@require_internal_auth
def message_generated():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    success = data.get('success', False)
    message = data.get('message', '')
    angle = data.get('angle')
    model = data.get('model')
    error = data.get('error')

    if not tenant_id or not lead_id:
        return jsonify({'success': False, 'error': 'tenant_id and lead_id are required'}), 400

    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead não encontrado'}), 404

    if success:
        # Evitar duplicatas: se já existe uma mensagem pendente para este lead, não criar outra
        existing = ProspectingMessage.query.filter(
            ProspectingMessage.lead_id == lead_id,
            ProspectingMessage.status.in_(['aguardando_aprovacao', 'pending_approval'])
        ).first()

        if existing:
            # Atualizar a mensagem existente com o conteúdo gerado
            existing.content = message
            if model:
                existing.ai_model = model
            db.session.commit()

            lead.prospecting_status = 'aguardando_aprovacao'
            if angle:
                lead.last_angle = angle
            lead.in_execution = False
            db.session.commit()

            return jsonify({
                'success': True,
                'message_id': existing.id,
                'lead_status': lead.prospecting_status,
                'updated': True
            })

        prospecting_msg = ProspectingMessage(
            company_id=tenant_id,
            lead_id=lead_id,
            campaign_id=lead.prospecting_campaign_id,
            channel=lead.preferred_channel or 'whatsapp',
            type='outbound',
            status='aguardando_aprovacao',
            content=message,
            ai_model=model,
            created_at=datetime.utcnow()
        )
        db.session.add(prospecting_msg)

        lead.prospecting_status = 'aguardando_aprovacao'
        if angle:
            lead.last_angle = angle
        lead.in_execution = False
        db.session.commit()

        return jsonify({
            'success': True,
            'message_id': prospecting_msg.id,
            'lead_status': lead.prospecting_status
        })
    else:
        lead.prospecting_status = 'erro'
        lead.in_execution = False

        prospecting_msg = ProspectingMessage(
            company_id=tenant_id,
            lead_id=lead_id,
            campaign_id=lead.prospecting_campaign_id,
            channel=lead.preferred_channel or 'whatsapp',
            type='outbound',
            status='erro',
            content='',
            error_message=error
        )
        db.session.add(prospecting_msg)
        db.session.commit()

        return jsonify({
            'success': True,
            'lead_status': lead.prospecting_status,
            'error': error
        })


@internal_api_bp.route('/prospecting/send-context', methods=['POST'])
@require_internal_auth
def get_send_context():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    message_id = data.get('message_id')
    
    if not tenant_id or not lead_id or not message_id:
        return jsonify({'success': False, 'error': 'tenant_id, lead_id and message_id are required'}), 400

    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    message = ProspectingMessage.query.filter_by(id=message_id, company_id=tenant_id).first()
    
    if not lead or not message:
        return jsonify({'success': False, 'error': 'Lead or Message not found'}), 404

    # Get integration for WhatsApp (Evolution API)
    integration = ProspectingIntegration.query.filter_by(
        company_id=tenant_id, 
        provider='evolution_api', 
        status='active'
    ).first()

    # Get Sender/Owner Info
    # If message was approved, use the approver's name. Fallback to Lead's assigned user.
    owner = None
    if message.approved_by:
        from models import User
        owner = User.query.get(message.approved_by)
    elif lead.assigned_to_id:
        from models import User
        owner = User.query.get(lead.assigned_to_id)
    
    owner_name = owner.name if owner else "Equipe NorthWay"
    company_name = lead.company.name if lead.company else "NorthWay"

    return jsonify({
        'success': True,
        'tenant_id': tenant_id,
        'owner_name': owner_name,
        'company_name': company_name,
        'sender_name': integration.sender_name if (integration and integration.sender_name) else (integration.display_name if integration else owner_name),
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email
        },
        'message': {
            'id': message.id,
            'content': message.content
        },
        'integration': {
            'api_base_url': integration.api_base_url if integration else None,
            'instance_name': integration.instance_name if integration else None,
            'display_name': integration.display_name if integration else None,
            'api_key': decrypt_api_key(integration.api_key_encrypted) if integration and integration.api_key_encrypted else None
        } if integration else None,
        # Standardized for N8N as requested
        'evolution_base_url': integration.api_base_url if integration else None,
        'evolution_api_key': decrypt_api_key(integration.api_key_encrypted) if integration and integration.api_key_encrypted else None,
        'evolution_instance': integration.instance_name if integration else None
    })


@internal_api_bp.route('/prospecting/send-result', methods=['POST'])
@require_internal_auth
def prospecting_send_result():
    data = request.json
    tenant_id = data.get('tenant_id')
    message_id = data.get('message_id')
    success = data.get('success', False)
    error = data.get('error')

    if not tenant_id or not message_id:
        return jsonify({'success': False, 'error': 'tenant_id and message_id are required'}), 400

    message = ProspectingMessage.query.filter_by(id=message_id, company_id=tenant_id).first()
    if not message:
        return jsonify({'success': False, 'error': 'Message not found'}), 404

    lead = Lead.query.get(message.lead_id)

    if success:
        message.status = 'enviada'
        message.sent_at = datetime.utcnow()
        if lead:
            lead.prospecting_status = 'contatado'
            lead.last_contact_at = datetime.utcnow()
            # Update next action based on campaign
            campaign = ProspectingCampaign.query.get(lead.prospecting_campaign_id)
            if campaign:
                lead.next_action_at = datetime.utcnow() + timedelta(days=campaign.followup_interval_days or 3)
    else:
        message.status = 'erro'
        message.error_message = error
        if lead:
            lead.prospecting_status = 'erro'

    db.session.commit()
    return jsonify({'success': True})


@internal_api_bp.route('/prospecting/save-automated-send', methods=['POST'])
@require_internal_auth
def save_automated_send():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    content = data.get('content')
    success = data.get('success', False)
    provider_message_id = data.get('provider_message_id')
    error = data.get('error')
    model = data.get('model')

    if not tenant_id or not lead_id or not content:
        return jsonify({'success': False, 'error': 'tenant_id, lead_id and content are required'}), 400

    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

    # Save the message
    prospecting_msg = ProspectingMessage(
        company_id=tenant_id,
        lead_id=lead_id,
        campaign_id=lead.prospecting_campaign_id,
        channel='whatsapp',
        type='outbound',
        status='enviada' if success else 'erro',
        content=content,
        ai_model=model,
        error_message=error if not success else None,
        sent_at=datetime.utcnow() if success else None,
        created_at=datetime.utcnow()
    )
    db.session.add(prospecting_msg)
    
    # Update Lead Status
    if success:
        lead.prospecting_status = 'contatado'
        lead.last_contact_at = datetime.utcnow()
        lead.in_execution = False
        
        # Update next action based on campaign
        campaign = ProspectingCampaign.query.get(lead.prospecting_campaign_id)
        if campaign:
            lead.next_action_at = datetime.utcnow() + timedelta(days=campaign.followup_interval_days or 3)
    else:
        lead.prospecting_status = 'erro'
        lead.in_execution = False

    db.session.commit()

    return jsonify({
        'success': True,
        'message_id': prospecting_msg.id,
        'provider_message_id': provider_message_id,
        'sent': success
    })


@internal_api_bp.route('/prospecting/inbound-context', methods=['POST'])
@require_internal_auth
def get_prospecting_inbound_context():
    start_time = time.time()
    logger.info("[INBOUND] started inbound-context")
    
    try:
        data = request.json
        tenant_id = data.get('tenant_id')
        provider = data.get('provider')
        instance_name = data.get('instance')
        phone = data.get('phone')
        phone_variants_list = data.get('phone_variants', [])
        message_id = data.get('message_id')
        inbound_data = data.get('inbound', {})
        
        if not phone:
            return jsonify({'success': False, 'error': 'phone is required'}), 400

        # Idempotency check
        if message_id:
            existing_msg = CrmConversationMessage.query.filter_by(message_id=message_id).first()
            if existing_msg:
                logger.info(f"[INBOUND] checked processed message in {time.time() - start_time:.3f}s: ignored")
                return jsonify({'ignored': True, 'reason': 'already processed'}), 200

        # 1. Resolve tenant_id
        integration_data = {}
        if not tenant_id:
            if not provider or not instance_name:
                return jsonify({'success': False, 'error': 'tenant_id OR (provider and instance) are required'}), 400
                
            integration = CrmChannelIntegration.query.filter_by(
                provider=provider,
                instance_name=instance_name,
                active=True
            ).first()
            
            if not integration:
                return jsonify({'success': False, 'error': 'No active integration found for this provider and instance'}), 404
                
            tenant_id = integration.tenant_id
            integration_data = {
                'provider': integration.provider,
                'instance_name': integration.instance_name
            }
        logger.info(f"[INBOUND] resolved tenant {tenant_id} in {time.time() - start_time:.3f}s")

        # 2. Find lead using phone variations
        search_phones = phone_variants_list if phone_variants_list else phone_variants(phone)
        if phone not in search_phones:
            search_phones.append(phone)
            
        lead = Lead.query.filter(
            Lead.company_id == tenant_id,
            db.or_(
                Lead.phone.in_(search_phones),
                Lead.whatsapp.in_(search_phones),
                Lead.mobile_phone.in_(search_phones)
            )
        ).first()

        if not lead:
            logger.info(f"[INBOUND] lead not found in {time.time() - start_time:.3f}s")
            return jsonify({'success': False, 'error': 'Lead não encontrado'}), 404

        logger.info(f"[INBOUND] found lead {lead.id} in {time.time() - start_time:.3f}s")

        # 3. Handle Conversation
        remote_jid = inbound_data.get('remote_jid') or f"{phone}@s.whatsapp.net"
        conversation = CrmConversation.query.filter_by(
            tenant_id=tenant_id,
            lead_id=lead.id,
            status='open'
        ).first()
        
        if not conversation:
            conversation = CrmConversation(
                tenant_id=tenant_id,
                lead_id=lead.id,
                channel='whatsapp',
                provider=provider,
                instance_name=instance_name,
                remote_jid=remote_jid,
                phone=phone,
                status='open',
                last_message_at=datetime.utcnow()
            )
            db.session.add(conversation)
            db.session.commit()
        else:
            conversation.last_message_at = datetime.utcnow()
            db.session.commit()
        logger.info(f"[INBOUND] upserted conversation {conversation.id} in {time.time() - start_time:.3f}s")

        # 4. Save Inbound Message
        inbound_msg = CrmConversationMessage(
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            lead_id=lead.id,
            direction='inbound',
            channel='whatsapp',
            provider=provider,
            instance_name=instance_name,
            remote_jid=remote_jid,
            phone=phone,
            message_id=message_id,
            message_type='text',
            text_content=inbound_data.get('text', ''),
            raw_payload=inbound_data
        )
        db.session.add(inbound_msg)
        db.session.commit()
        logger.info(f"[INBOUND] inserted message in {time.time() - start_time:.3f}s")

        # 5. Fetch History and Memory
        history = []
        messages = CrmConversationMessage.query.filter_by(conversation_id=conversation.id).order_by(CrmConversationMessage.created_at.asc()).limit(50).all()
        for m in messages:
            history.append({
                'direction': m.direction,
                'text': m.text_content,
                'timestamp': m.created_at.isoformat() if m.created_at else None
            })
        logger.info(f"[INBOUND] loaded history ({len(history)} items) in {time.time() - start_time:.3f}s")
            
        memory = CrmConversationMemory.query.filter_by(conversation_id=conversation.id).first()
        memory_data = {}
        if memory:
            memory_data = {
                'summary': memory.summary,
                'last_intention': memory.last_intention,
                'last_objection': memory.last_objection,
                'interest_level': memory.interest_level,
                'next_best_action': memory.next_best_action
            }
        logger.info(f"[INBOUND] loaded memory in {time.time() - start_time:.3f}s")

        # 6. Return full context
        response_data = {
            'success': True,
            'tenant_id': tenant_id,
            'lead': {
                'id': lead.id,
                'name': lead.name,
                'prospecting_status': lead.prospecting_status,
                'last_angle': lead.last_angle,
                'phone': lead.phone
            },
            'conversation': {
                'id': conversation.id,
                'status': conversation.status
            },
            'history': history,
            'memory': memory_data,
            'inbound': inbound_data,
            'integration': integration_data
        }
        
        logger.info(f"[INBOUND] returned response in {time.time() - start_time:.3f}s")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"[INBOUND] error in inbound-context after {time.time() - start_time:.3f}s: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@internal_api_bp.route('/prospecting/inbound-result', methods=['POST'])
@require_internal_auth
def prospecting_inbound_result():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    conversation_id = data.get('conversation_id')
    classification = data.get('classification')
    lead_score_delta = data.get('lead_score_delta', 0)
    suggested_status = data.get('suggested_status')
    summary = data.get('summary')
    
    # Optional fields for AI Log
    action = data.get('action')
    provider = data.get('provider')
    model_name = data.get('model')
    prompt = data.get('prompt')
    input_data = data.get('input')
    output_data = data.get('output')
    error = data.get('error')
    tokens_used = data.get('tokens_used')
    duration_ms = data.get('duration_ms')

    if not tenant_id or not lead_id:
        return jsonify({'success': False, 'error': 'tenant_id and lead_id are required'}), 400

    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead não encontrado'}), 404

    # 1. Update status — só avança no funil, não regride
    if suggested_status:
        order = {'novo': 0, 'em_execucao': 1, 'aguardando_aprovacao': 2, 'pending_approval': 2,
                 'contatado': 3, 'sent': 3, 'approved': 3,
                 'respondeu': 4, 'interessado': 5, 'reuniao': 6, 'cliente': 7,
                 'sem_resposta': 4, 'descartado': 0, 'erro': 0, 'failed': 0}
        current = order.get(lead.prospecting_status, 0)
        target = order.get(suggested_status, 0)
        if target > current:
            lead.prospecting_status = suggested_status
    if lead_score_delta:
        try:
            lead.lead_score = int(lead.lead_score or 0) + int(lead_score_delta)
        except ValueError:
            pass

    # 2. Update Memory
    if conversation_id and summary:
        memory = CrmConversationMemory.query.filter_by(conversation_id=conversation_id).first()
        if not memory:
            memory = CrmConversationMemory(
                tenant_id=tenant_id,
                lead_id=lead.id,
                conversation_id=conversation_id
            )
            db.session.add(memory)
        memory.summary = summary
        memory.last_intention = data.get('last_intention')
        memory.last_objection = data.get('last_objection')
        memory.interest_level = data.get('interest_level')
        memory.next_best_action = data.get('next_best_action')

    # 3. Save AI Log
    ai_log = CrmAiLog(
        tenant_id=tenant_id,
        lead_id=lead.id,
        conversation_id=conversation_id,
        action=action,
        provider=provider,
        model_name=model_name,
        prompt=prompt,
        input_data=input_data,
        output_data=output_data,
        classification=classification,
        error_message=error,
        tokens_used=tokens_used,
        duration_ms=duration_ms
    )
    db.session.add(ai_log)
    
    db.session.commit()
    return jsonify({'success': True})

@internal_api_bp.route('/prospecting/batch-completed', methods=['POST'])
@require_internal_auth
def prospecting_batch_completed():
    data = request.json
    tenant_id = data.get('tenant_id')
    campaign_id = data.get('campaign_id')
    processed_count = data.get('processed_count', 0)
    success_count = data.get('success_count', 0)

    if not tenant_id or not campaign_id:
        return jsonify({'success': False, 'error': 'tenant_id and campaign_id are required'}), 400

    from models import ProspectingCampaign, User
    from utils import create_notification

    campaign = ProspectingCampaign.query.filter_by(id=campaign_id, company_id=tenant_id).first()
    if not campaign:
        return jsonify({'success': False, 'error': 'Campanha não encontrada'}), 404

    # Enviar notificação de término para todos os usuários da empresa
    users = User.query.filter_by(company_id=tenant_id).all()
    for user in users:
        create_notification(
            user_id=user.id,
            company_id=tenant_id,
            type='campaign_end',
            title=f"Campanha '{campaign.name}' Concluída",
            message=f"O disparo diário para a campanha '{campaign.name}' foi concluído. {processed_count} contatos processados e {success_count} mensagens enviadas com sucesso."
        )

    return jsonify({'success': True})


@internal_api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'internal-api'})