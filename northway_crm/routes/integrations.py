from flask import Blueprint, request, jsonify, current_app, url_for
from flask_login import login_required, current_user
from models import db, Integration, FinancialEvent, Transaction, Contract
from services.asaas_service import AsaasService
import json

integrations_bp = Blueprint('integrations_bp', __name__)

@integrations_bp.route('/api/integrations/asaas/save', methods=['POST'])
@login_required
def save_asaas_config():
    data = request.json
    api_key = data.get('api_key')
    environment = data.get('environment', 'sandbox')
    
    if not api_key:
        return jsonify({'error': 'API Key is required'}), 400

    integration = Integration.query.filter_by(company_id=current_user.company_id, service='asaas').first()
    
    if not integration:
        integration = Integration(
            company_id=current_user.company_id,
            service='asaas',
            is_active=True
        )
        db.session.add(integration)
    
    integration.api_key = api_key
    # Store environment in config_json
    integration.config_json = json.dumps({'environment': environment})
    integration.updated_at = db.func.now()
    
    db.session.commit()
    
    return jsonify({'success': True})

@integrations_bp.route('/api/integrations/asaas/test', methods=['POST'])
@login_required
def test_asaas_connection():
    # Use the saved key or the one provided in request (for testing before save)
    # But for security, usually we use the saved one or temporary one.
    # Let's use the one in request if provided, else saved.
    data = request.json
    api_key = data.get('api_key')
    environment = data.get('environment', 'sandbox')
    
    if not api_key:
        # Try to fetch from DB
        existing = Integration.query.filter_by(company_id=current_user.company_id, service='asaas').first()
        if existing and existing.api_key:
            api_key = existing.api_key
            if existing.config_json:
                try:
                    conf = json.loads(existing.config_json)
                    environment = conf.get('environment', environment)
                except: pass
        else:
            return jsonify({'error': 'API Key missing'}), 400

    # Test by listing customers (limit 1)
    base_url = AsaasService.get_base_url(environment)
    headers = AsaasService.get_headers(api_key)
    
    try:
        import requests
        res = requests.get(f"{base_url}/customers?limit=1", headers=headers, timeout=10)
        if res.status_code == 200:
            return jsonify({'success': True, 'message': 'Conexão estabelecida com sucesso!'})
        elif res.status_code == 401:
             return jsonify({'error': 'Chave API inválida.'}), 401
        else:
             return jsonify({'error': f"Erro ASAAS: {res.text}"}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# WEBHOOK
@integrations_bp.route('/api/webhooks/asaas/<int:company_id>', methods=['POST'])
def asaas_webhook(company_id):
    # Retrieve payload
    payload = request.json
    event = payload.get('event')
    payment_data = payload.get('payment')
    
    if not event or not payment_data:
        return jsonify({'error': 'Invalid payload'}), 400

    # Log Event
    # Check if transaction exists via externalReference or asaas_id
    transaction = None
    if payment_data.get('externalReference'):
        transaction = Transaction.query.get(payment_data['externalReference'])
    
    # If not found by external ref, try by asaas_id
    if not transaction and payment_data.get('id'):
         transaction = Transaction.query.filter_by(asaas_id=payment_data['id']).first()

    # Create Event Log
    log = FinancialEvent(
        company_id=company_id,
        payment_id=transaction.id if transaction else None,
        event_type=event,
        payload=payload
    )
    db.session.add(log) # Add log regardless of matching transaction
    
    if transaction:
        # Verify company mismatch? (Should not happen if URL is correct but good to check)
        if transaction.company_id != company_id:
            current_app.logger.warning(f"Webhook Company Mismatch: URL {company_id} vs Trans {transaction.company_id}")
        
        # Update Status
        if event == 'PAYMENT_RECEIVED' or event == 'PAYMENT_CONFIRMED':
            transaction.status = 'paid'
            transaction.paid_date = db.func.current_date()
        elif event == 'PAYMENT_OVERDUE':
            transaction.status = 'overdue'
        elif event in ['PAYMENT_REFUNDED', 'PAYMENT_REVERSED']:
            transaction.status = 'cancelled' # or refunded
            
        # Potentially update Contract status if all paid? (Out of scope for now)
    
    db.session.commit()
    
    return jsonify({'received': True})
