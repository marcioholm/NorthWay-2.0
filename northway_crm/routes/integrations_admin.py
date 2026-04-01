from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, IntegrationApiKey, IntegrationWebhook, IntegrationLog
from services.integrations_service import IntegrationsService
import secrets
import uuid

integrations_admin_bp = Blueprint('integrations_admin', __name__)

@integrations_admin_bp.route('/integrations/hub')
@login_required
def hub():
    """
    Renders the Integrations Hub dashboard for the current company.
    """
    company_id = current_user.company_id
    
    # Fetch Data with strict tenant filter
    api_keys = IntegrationApiKey.query.filter_by(company_id=company_id).all()
    webhooks = IntegrationWebhook.query.filter_by(company_id=company_id).all()
    
    # Recent Logs
    logs = IntegrationLog.query.filter_by(company_id=company_id)\
        .order_by(IntegrationLog.created_at.desc())\
        .limit(20).all()
        
    return render_template('integrations/hub.html', 
                          api_keys=api_keys, 
                          webhooks=webhooks, 
                          logs=logs)

@integrations_admin_bp.route('/api/integrations/keys', methods=['POST'])
@login_required
def create_api_key():
    """Generates a new API Key for the tenant."""
    data = request.json
    name = data.get('name', 'Nova Chave API')
    scopes = data.get('scopes', [])
    
    try:
        raw_key = IntegrationsService.generate_api_key(current_user.company_id, name, scopes)
        return jsonify({
            "success": True, 
            "api_key": raw_key,
            "message": "CUIDADO: Esta chave só será mostrada uma única vez."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@integrations_admin_bp.route('/api/integrations/keys/<int:id>/revoke', methods=['POST'])
@login_required
def revoke_api_key(id):
    """Revokes an existing API Key."""
    key = IntegrationApiKey.query.filter_by(id=id, company_id=current_user.company_id).first()
    if not key:
        return jsonify({"success": False, "error": "Chave não encontrada."}), 404
        
    key.status = 'revoked'
    db.session.commit()
    return jsonify({"success": True})

@integrations_admin_bp.route('/api/integrations/webhooks', methods=['POST'])
@login_required
def create_webhook():
    """Registers a new outbound webhook."""
    data = request.json
    name = data.get('name')
    url = data.get('url')
    events = data.get('events', [])
    
    if not url:
        return jsonify({"success": False, "error": "URL é obrigatória."}), 400
        
    try:
        webhook = IntegrationWebhook(
            company_id=current_user.company_id,
            name=name or f"Webhook para {url}",
            url=url,
            events=events,
            secret=secrets.token_urlsafe(32),
            status='active'
        )
        db.session.add(webhook)
        db.session.commit()
        return jsonify({"success": True, "webhook_id": webhook.id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@integrations_admin_bp.route('/api/integrations/webhooks/<int:id>', methods=['PATCH'])
@login_required
def update_webhook(id):
    """Updates or toggles a webhook."""
    webhook = IntegrationWebhook.query.filter_by(id=id, company_id=current_user.company_id).first()
    if not webhook:
        return jsonify({"success": False, "error": "Webhook não encontrado."}), 404
        
    data = request.json
    if 'status' in data:
        webhook.status = data['status']
    if 'events' in data:
        webhook.events = data['events']
    if 'url' in data:
        webhook.url = data['url']
        
    db.session.commit()
    return jsonify({"success": True})

@integrations_admin_bp.route('/api/integrations/webhooks/<int:id>', methods=['DELETE'])
@login_required
def delete_webhook(id):
    """Deletes a webhook."""
    webhook = IntegrationWebhook.query.filter_by(id=id, company_id=current_user.company_id).first()
    if not webhook:
        return jsonify({"success": False, "error": "Webhook não encontrado."}), 404
        
    db.session.delete(webhook)
    db.session.commit()
    return jsonify({"success": True})

@integrations_admin_bp.route('/api/integrations/logs/clear', methods=['POST'])
@login_required
def clear_logs():
    """Clears integration logs for the company."""
    IntegrationLog.query.filter_by(company_id=current_user.company_id).delete()
    db.session.commit()
    return jsonify({"success": True})
