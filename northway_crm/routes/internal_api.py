import os
import requests
from flask import Blueprint, request, jsonify
from functools import wraps
from models import db, Lead, ProspectingCampaign, ProspectingMessage, ProspectingSetting, TenantAICredential, ProspectingIntegration, Interaction
from datetime import datetime, timedelta
from utils.crypto import decrypt_api_key

internal_api_bp = Blueprint('internal_api', __name__, url_prefix='/api/internal')


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

    if not tenant_id or not provider:
        return jsonify({'success': False, 'error': 'tenant_id and provider are required'}), 400

    credential = TenantAICredential.query.filter_by(
        company_id=tenant_id,
        provider=provider,
        status='active'
    ).first()

    if not credential:
        return jsonify({'success': False, 'error': 'Credential not found or inactive'}), 404

    decrypted_key = decrypt_api_key(credential.api_key_encrypted)

    return jsonify({
        'success': True,
        'data': {
            'provider': credential.provider,
            'api_key': decrypted_key,
            'default_model': credential.default_model
        }
    })


@internal_api_bp.route('/prospecting/context', methods=['POST'])
@require_internal_auth
def get_prospecting_context():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    campaign_id = data.get('campaign_id')

    if not tenant_id or not lead_id:
        return jsonify({'success': False, 'error': 'tenant_id and lead_id are required'}), 400

    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

    campaign = None
    if campaign_id or lead.prospecting_campaign_id:
        campaign = ProspectingCampaign.query.get(campaign_id or lead.prospecting_campaign_id)

    settings = ProspectingSetting.query.filter_by(company_id=tenant_id).first()

    context = {
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email,
            'interest': lead.interest,
            'preferred_channel': lead.preferred_channel or 'whatsapp',
            'last_angle': lead.last_angle,
            'notes': lead.notes
        },
        'campaign': None,
        'settings': None
    }

    if campaign:
        context['campaign'] = {
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
        }

    if settings:
        context['settings'] = {
            'default_ai_model': settings.default_ai_model,
            'default_tone': settings.default_tone,
            'manual_approval_required': settings.manual_approval_required
        }

    return jsonify({'success': True, 'data': context})


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
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

    if success:
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
            'data': {
                'message_id': prospecting_msg.id,
                'lead_status': lead.prospecting_status
            }
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
            'data': {
                'lead_status': lead.prospecting_status,
                'error': error
            }
        })


@internal_api_bp.route('/prospecting/send-context', methods=['POST'])
@require_internal_auth
def get_send_context():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    message_id = data.get('message_id')
    channel = data.get('channel', 'whatsapp')

    if not tenant_id or not lead_id or not message_id:
        return jsonify({'success': False, 'error': 'tenant_id, lead_id and message_id are required'}), 400

    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

    message = ProspectingMessage.query.filter_by(id=message_id, lead_id=lead_id).first()
    if not message:
        return jsonify({'success': False, 'error': 'Message not found'}), 404

    campaign = None
    if lead.prospecting_campaign_id:
        campaign = ProspectingCampaign.query.get(lead.prospecting_campaign_id)

    integration = None
    if channel == 'whatsapp':
        integration = ProspectingIntegration.query.filter_by(
            company_id=tenant_id,
            provider='evolution_api',
            status='active'
        ).first()

        if integration:
            integration_data = {
                'provider': integration.provider,
                'api_base_url': integration.api_base_url,
                'instance_name': integration.instance_name,
                'api_key': decrypt_api_key(integration.api_key_encrypted) if integration.api_key_encrypted else None
            }
        else:
            integration_data = None
    elif channel == 'email':
        integration = ProspectingIntegration.query.filter_by(
            company_id=tenant_id,
            provider='smtp',
            status='active'
        ).first()

        if integration:
            integration_data = {
                'provider': integration.provider,
                'api_base_url': integration.api_base_url,
                'api_key': decrypt_api_key(integration.api_key_encrypted) if integration.api_key_encrypted else None
            }
        else:
            integration_data = None
    else:
        integration_data = None

    context = {
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email
        },
        'message': {
            'id': message.id,
            'content': message.content,
            'channel': message.channel
        },
        'campaign': None,
        'integration': integration_data
    }

    if campaign:
        context['campaign'] = {
            'name': campaign.name,
            'tone_of_voice': campaign.tone_of_voice
        }

    return jsonify({'success': True, 'data': context})


@internal_api_bp.route('/prospecting/send-result', methods=['POST'])
@require_internal_auth
def send_result():
    data = request.json
    tenant_id = data.get('tenant_id')
    message_id = data.get('message_id')
    success = data.get('success', False)
    error = data.get('error')
    sent_at = data.get('sent_at')

    if not tenant_id or not message_id:
        return jsonify({'success': False, 'error': 'tenant_id and message_id are required'}), 400

    message = ProspectingMessage.query.filter_by(id=message_id).first()
    if not message:
        return jsonify({'success': False, 'error': 'Message not found'}), 404

    lead = Lead.query.filter_by(id=message.lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

    if success:
        message.status = 'enviada'
        message.sent_at = datetime.fromisoformat(sent_at.replace('Z', '+00:00')) if sent_at else datetime.utcnow()
        message.updated_at = datetime.utcnow()

        if message.channel == 'whatsapp':
            lead.wa_attempts = (lead.wa_attempts or 0) + 1
        elif message.channel == 'email':
            lead.email_attempts = (lead.email_attempts or 0) + 1

        lead.last_contact_at = datetime.utcnow()
        lead.prospecting_status = 'contatado'

        campaign = ProspectingCampaign.query.get(lead.prospecting_campaign_id) if lead.prospecting_campaign_id else None
        if campaign and campaign.followup_interval_days:
            lead.next_action_at = datetime.utcnow() + timedelta(days=campaign.followup_interval_days)

        interaction = Interaction(
            lead_id=lead.id,
            company_id=tenant_id,
            user_id=None,
            type=message.channel,
            content=message.content
        )
        db.session.add(interaction)

        db.session.commit()

        return jsonify({
            'success': True,
            'data': {
                'message_status': message.status,
                'lead_status': lead.prospecting_status
            }
        })
    else:
        message.status = 'erro'
        message.error_message = error
        message.updated_at = datetime.utcnow()

        lead.prospecting_status = 'erro'
        lead.in_execution = False
        db.session.commit()

        return jsonify({
            'success': True,
            'data': {
                'message_status': message.status,
                'lead_status': lead.prospecting_status,
                'error': error
            }
        })


@internal_api_bp.route('/prospecting/inbound-context', methods=['POST'])
@require_internal_auth
def get_inbound_context():
    data = request.json
    tenant_id = data.get('tenant_id')
    inbound = data.get('inbound', {})

    if not tenant_id:
        return jsonify({'success': False, 'error': 'tenant_id is required'}), 400

    phone = inbound.get('phone')
    email = inbound.get('email')

    lead = None
    if phone:
        lead = Lead.query.filter_by(company_id=tenant_id, phone=phone).first()
    if not lead and email:
        lead = Lead.query.filter_by(company_id=tenant_id, email=email).first()

    if not lead:
        return jsonify({'success': True, 'data': {'lead': None}})

    recent_interactions = Interaction.query.filter_by(lead_id=lead.id).order_by(
        Interaction.created_at.desc()
    ).limit(10).all()

    recent_messages = ProspectingMessage.query.filter_by(lead_id=lead.id).order_by(
        ProspectingMessage.created_at.desc()
    ).limit(5).all()

    return jsonify({
        'success': True,
        'data': {
            'lead': {
                'id': lead.id,
                'name': lead.name,
                'phone': lead.phone,
                'email': lead.email,
                'interest': lead.interest,
                'prospecting_status': lead.prospecting_status,
                'lead_score': lead.lead_score
            },
            'recent_interactions': [
                {
                    'type': i.type,
                    'content': i.content,
                    'created_at': i.created_at.isoformat() if i.created_at else None
                } for i in recent_interactions
            ],
            'recent_messages': [
                {
                    'channel': m.channel,
                    'status': m.status,
                    'created_at': m.created_at.isoformat() if m.created_at else None
                } for m in recent_messages
            ]
        }
    })


@internal_api_bp.route('/prospecting/inbound-result', methods=['POST'])
@require_internal_auth
def inbound_result():
    data = request.json
    tenant_id = data.get('tenant_id')
    inbound = data.get('inbound', {})
    suggested_status = data.get('suggested_status')
    lead_score_delta = data.get('lead_score_delta', 0)
    summary = data.get('summary')
    suggested_reply = data.get('suggested_reply')

    if not tenant_id:
        return jsonify({'success': False, 'error': 'tenant_id is required'}), 400

    phone = inbound.get('phone')
    email = inbound.get('email')
    content = inbound.get('content', '')

    lead = None
    if phone:
        lead = Lead.query.filter_by(company_id=tenant_id, phone=phone).first()
    if not lead and email:
        lead = Lead.query.filter_by(company_id=tenant_id, email=email).first()

    if not lead:
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

    channel = 'whatsapp' if phone else 'email'

    interaction = Interaction(
        lead_id=lead.id,
        company_id=tenant_id,
        user_id=None,
        type=channel,
        content=content
    )
    db.session.add(interaction)

    if suggested_status:
        status_map = {
            'respondeu': 'respondeu',
            'interessado': 'interessado',
            'reuniao': 'reuniao',
            'sem_resposta': 'sem_resposta',
            'pausado': 'pausado'
        }
        if suggested_status in status_map:
            lead.prospecting_status = status_map[suggested_status]

    if lead_score_delta != 0:
        current_score = lead.lead_score or 0
        lead.lead_score = max(0, current_score + lead_score_delta)

    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'lead_id': lead.id,
            'lead_status': lead.prospecting_status,
            'lead_score': lead.lead_score
        }
    })


@internal_api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'internal-api'})