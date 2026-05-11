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

    # Build the flattened response as requested by the user
    response = {
        'success': True,
        'tenant_id': tenant_id,
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
        }
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

    return jsonify({
        'success': True,
        'tenant_id': tenant_id,
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone
        },
        'message': {
            'id': message.id,
            'content': message.content
        },
        'integration': {
            'api_base_url': integration.api_base_url if integration else None,
            'instance_name': integration.instance_name if integration else None,
            'api_key': decrypt_api_key(integration.api_key_encrypted) if integration and integration.api_key_encrypted else None
        } if integration else None
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


@internal_api_bp.route('/prospecting/inbound-context', methods=['POST'])
@require_internal_auth
def get_prospecting_inbound_context():
    data = request.json
    tenant_id = data.get('tenant_id')
    phone = data.get('phone')
    
    if not tenant_id or not phone:
        return jsonify({'success': False, 'error': 'tenant_id and phone are required'}), 400

    lead = Lead.query.filter_by(company_id=tenant_id, phone=phone).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead não encontrado'}), 404

    return jsonify({
        'success': True,
        'tenant_id': tenant_id,
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'prospecting_status': lead.prospecting_status,
            'last_angle': lead.last_angle
        }
    })


@internal_api_bp.route('/prospecting/inbound-result', methods=['POST'])
@require_internal_auth
def prospecting_inbound_result():
    data = request.json
    tenant_id = data.get('tenant_id')
    lead_id = data.get('lead_id')
    new_status = data.get('status')
    
    if not tenant_id or not lead_id:
        return jsonify({'success': False, 'error': 'tenant_id and lead_id are required'}), 400

    lead = Lead.query.filter_by(id=lead_id, company_id=tenant_id).first()
    if not lead:
        return jsonify({'success': False, 'error': 'Lead não encontrado'}), 404

    if new_status:
        lead.prospecting_status = new_status
    
    db.session.commit()
    return jsonify({'success': True})


@internal_api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'internal-api'})