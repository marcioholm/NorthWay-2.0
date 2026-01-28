from flask import Blueprint, request, current_app, url_for
from flask_login import login_required, current_user
from models import db, Integration, FinancialEvent, Transaction, Contract
from services.asaas_service import AsaasService
from services.facebook_capi_service import FacebookCapiService
from utils import api_response, retry_request
import json
import requests

integrations_bp = Blueprint('integrations_bp', __name__)

@integrations_bp.route('/api/integrations/asaas/save', methods=['POST'])
@login_required
def save_asaas_config():
    if not current_user.company_id:
        return api_response(success=False, error='Usuário sem empresa vinculada', status=403)

    data = request.json
    api_key = data.get('api_key')
    environment = data.get('environment', 'sandbox')
    
    if not api_key:
        return api_response(success=False, error='API Key is required', status=400)

    # Use strict filter
    integration = Integration.query.filter(Integration.company_id == current_user.company_id, Integration.service == 'asaas').first()
    
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
    
    return api_response(success=True)

@integrations_bp.route('/api/integrations/asaas/test', methods=['POST'])
@login_required
def test_asaas_connection():
    if not current_user.company_id:
        return api_response(success=False, error='Usuário sem empresa vinculada', status=403)

    # Use the saved key or the one provided in request (for testing before save)
    # But for security, usually we use the saved one or temporary one.
    # Let's use the one in request if provided, else saved.
    data = request.json
    api_key = data.get('api_key')
    environment = data.get('environment', 'sandbox')
    
    if not api_key:
        # Try to fetch from DB
        existing = Integration.query.filter(Integration.company_id == current_user.company_id, Integration.service == 'asaas').first()
        if existing and existing.api_key:
            api_key = existing.api_key
            if existing.config_json:
                try:
                    conf = json.loads(existing.config_json)
                    environment = conf.get('environment', environment)
                except: pass
        else:
            return api_response(success=False, error='API Key missing', status=400)

    # Test by listing customers (limit 1)
    base_url = AsaasService.get_base_url(environment)
    headers = AsaasService.get_headers(api_key)
    
    try:
        @retry_request(retries=2)
        def perform_test():
            return requests.get(f"{base_url}/customers?limit=1", headers=headers, timeout=10)
        
        res = perform_test()
        if res.status_code == 200:
            return api_response(success=True, data={'message': 'Conexão estabelecida com sucesso!'})
        elif res.status_code == 401:
            return api_response(success=False, error='Chave API inválida.', status=401)
        else:
            return api_response(success=False, error=f"Erro ASAAS: {res.text}", status=400)
    except Exception as e:
        return api_response(success=False, error=str(e), status=500)

@integrations_bp.route('/api/integrations/asaas/setup-webhook', methods=['POST'])
@login_required
def setup_asaas_webhook():
    if not current_user.company_id:
         return api_response(success=False, error='Usuário sem empresa vinculada', status=403)

    webhook_url = f"{request.url_root.rstrip('/')}/api/webhooks/asaas/{current_user.company_id}"
    try:
        AsaasService.configure_webhook(current_user.company_id, webhook_url)
        return api_response(success=True)
    except Exception as e:
        return api_response(success=False, error=str(e), status=500)

@integrations_bp.route('/api/integrations/google-maps/test', methods=['POST'])
@login_required
def test_google_maps():
    if not current_user.company_id:
         return api_response(success=False, error='Usuário sem empresa vinculada', status=403)

    api_key = request.json.get('api_key')
    if not api_key:
        return api_response(success=False, error='API Key is required', status=400)
    
    # Test by doing a simple search (e.g., "Google") using Legacy API
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        'query': 'Google',
        'key': api_key
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get('status') == 'OK':
            return api_response(success=True)
        else:
            err = data.get('error_message', data.get('status', 'Unknown Error'))
            return api_response(success=False, error=f"Google Error: {err}")
    except Exception as e:
        return api_response(success=False, error=str(e))

# WEBHOOK
@integrations_bp.route('/api/webhooks/asaas/<int:company_id>', methods=['POST'])
def asaas_webhook(company_id):
    # Retrieve payload
    payload = request.json
    event = payload.get('event')
    payment_data = payload.get('payment')
    
    if not event or not payment_data:
        return api_response(success=False, error='Invalid payload', status=400)

    # Log Event
    # Check if transaction exists via externalReference or asaas_id
    transaction = None
    if payment_data.get('externalReference'):
        transaction = Transaction.query.get(payment_data['externalReference'])
    
    # If not found by external ref, try by asaas_id
    if not transaction and payment_data.get('id'):
         transaction = Transaction.query.filter_by(asaas_id=payment_data['id']).first()

    try:
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
                
                # --- FACEBOOK CAPI TRIGGER ---
                try:
                    # Resolve user (payer)
                    user = None
                    if transaction.client and transaction.client.account_manager:
                         # Fallback: attribute to account manager or try to find a contact?
                         # Ideally we need the actual payer person. For now, let's use the company owner or client email if available.
                         # Assuming transaction.client has contact info or linked user.
                         # Simplification: Use the first user found or the account manager as proxy for testing 
                         # (In prod, we should store payer_email/phone on transaction)
                         user = transaction.client.account_manager 
                    
                    if user:
                        capi = FacebookCapiService()
                        capi.send_purchase(
                            user=user, 
                            amount=payment_data.get('value', 0), 
                            transaction_id=transaction.id
                        )
                except Exception as capi_e:
                    current_app.logger.error(f"CAPI Trigger Error: {capi_e}")
                # -----------------------------
            elif event == 'PAYMENT_OVERDUE':
                transaction.status = 'overdue'
            elif event in ['PAYMENT_REFUNDED', 'PAYMENT_REVERSED']:
                transaction.status = 'cancelled' # or refunded
                
            # Potentially update Contract status if all paid? (Out of scope for now)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Asaas Webhook Error: {e}")
        return api_response(success=False, error=str(e), status=500)
    
    return api_response(data={'received': True})
