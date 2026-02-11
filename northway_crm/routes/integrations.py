from flask import Blueprint, request, current_app, url_for, redirect, render_template, flash, jsonify
from datetime import datetime
from flask_login import login_required, current_user
from models import db, Integration, FinancialEvent, Transaction, Contract

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
    return api_response(success=False, error='Manutenção da Integração Asaas (v2)', status=503)

@integrations_bp.route('/api/integrations/asaas/setup-webhook', methods=['POST'])
@login_required
def setup_asaas_webhook():
    if not current_user.company_id:
        return api_response(success=False, error='Usuário sem empresa.', status=403)

    integration = Integration.query.filter_by(company_id=current_user.company_id, service='asaas', is_active=True).first()
    if not integration or not integration.api_key:
         return api_response(success=False, error='Integração Asaas não configurada.', status=400)
    
    # Generate Webhook URL
    webhook_url = url_for('integrations_bp.asaas_webhook', company_id=current_user.company_id, _external=True)
    
    # Use current user email or company email
    email = current_user.email
    
    from services.asaas_service import create_webhook
    
    config, err = create_webhook(webhook_url, email, integration.api_key)
    
    if config:
        return api_response(success=True, data=config)
    else:
        return api_response(success=False, error=f"Erro Asaas: {err}", status=500)

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

# --- GOOGLE DRIVE INTEGRATION ---
from models import TenantIntegration

@integrations_bp.route('/api/integrations/google-drive/connect')
@login_required
def connect_google_drive():
    try:
        from services.google_drive_service import GoogleDriveService
        service = GoogleDriveService(company_id=current_user.company_id)
        auth_url, state = service.get_auth_url()
        # Save state in session if needed for CSRF protection
        return redirect(auth_url)
    except Exception as e:
        return api_response(success=False, error=str(e), status=500)

@integrations_bp.route('/api/integrations/google-drive/callback')
@login_required
def google_drive_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return render_template('integrations/drive_error.html', error=error)
        
    if not code:
        return render_template('integrations/drive_error.html', error="No code received")
        
    try:
        from services.google_drive_service import GoogleDriveService
        service = GoogleDriveService(company_id=current_user.company_id)
        tokens = service.fetch_token(code)
        
        # Save to DB
        integration = TenantIntegration.query.filter_by(
            company_id=current_user.company_id, 
            provider='google_drive'
        ).first()
        
        if not integration:
            integration = TenantIntegration(
                company_id=current_user.company_id,
                provider='google_drive'
            )
            db.session.add(integration)
            
        integration.status = 'connected'
        integration.access_token = tokens['token']
        integration.refresh_token_encrypted = tokens['refresh_token']
        integration.token_expiry_at = datetime.fromisoformat(tokens['expiry'].replace('Z', '')) if tokens['expiry'] else None
        integration.updated_at = datetime.utcnow()
        # We could fetch email too using googleapis/oauth2/v2/userinfo
        
        db.session.commit()
        
        # Redirect to settings to configure root folder
        flash('Google Drive conectado com sucesso! Configure a pasta raiz.', 'success')
        return redirect(url_for('integrations_bp.drive_settings_page'))
        
    except Exception as e:
        current_app.logger.error(f"Drive Callback Error: {e}")
        return render_template('integrations/drive_error.html', error=str(e))

@integrations_bp.route('/start/settings/drive')
@login_required
def drive_settings_page():
    # Render settings page
    integration = TenantIntegration.query.filter_by(
        company_id=current_user.company_id, 
        provider='google_drive'
    ).first()
    
    templates = DriveFolderTemplate.query.filter_by(company_id=current_user.company_id, scope='tenant').all()
    if not templates and integration: # Seed if connected but no templates
        seed_drive_templates()
        templates = DriveFolderTemplate.query.filter_by(company_id=current_user.company_id, scope='tenant').all()
    
    # Allowed Global Templates
    global_templates = []
    if current_user.company and current_user.company.allowed_global_template_ids:
        global_templates = DriveFolderTemplate.query.filter(
            DriveFolderTemplate.id.in_(current_user.company.allowed_global_template_ids),
            DriveFolderTemplate.scope == 'global'
        ).all()
        
    return render_template('settings_drive.html', 
                          integration=integration, 
                          templates=templates,
                          global_templates=global_templates)

@integrations_bp.route('/api/integrations/drive/templates/duplicate/<int:id>', methods=['POST'])
@login_required
def duplicate_global_template(id):
    if not current_user.company_id:
        return api_response(success=False, error='Usuário sem empresa vinculada', status=403)
        
    global_template = DriveFolderTemplate.query.get_or_404(id)
    
    # Security: Check if allowed
    allowed_ids = current_user.company.allowed_global_template_ids or []
    if id not in allowed_ids and not current_user.is_super_admin:
        return api_response(success=False, error='Acesso negado a este template global', status=403)
        
    try:
        new_template = DriveFolderTemplate(
            company_id=current_user.company_id,
            name=f"{global_template.name} (Cópia)",
            structure_json=global_template.structure_json,
            scope='tenant'
        )
        db.session.add(new_template)
        db.session.commit()
        return api_response(success=True, data={'id': new_template.id})
    except Exception as e:
        db.session.rollback()
        return api_response(success=False, error=str(e))

@integrations_bp.route('/api/integrations/google-drive/root-folder', methods=['POST'])
@login_required
def save_drive_root_folder():
    folder_url = request.form.get('root_folder_url')
    # Simple extraction of ID from URL
    # https://drive.google.com/drive/folders/1234567890abcdef
    folder_id = None
    if 'folders/' in folder_url:
        folder_id = folder_url.split('folders/')[-1].split('?')[0] # Basic parsing
    else:
        folder_id = folder_url # Assume ID was pasted
        
    if not folder_id:
        flash('ID da pasta inválido', 'error')
        return redirect(url_for('integrations_bp.drive_settings_page'))
        
    integration = TenantIntegration.query.filter_by(
        company_id=current_user.company_id, 
        provider='google_drive'
    ).first()
    
    if integration:
        integration.root_folder_id = folder_id
        integration.root_folder_url = folder_url
        db.session.commit()
        flash('Pasta raiz configurada!', 'success')
        
    return redirect(url_for('integrations_bp.drive_settings_page'))

@integrations_bp.route('/api/integrations/google-drive/disconnect', methods=['POST'])
@login_required
def disconnect_google_drive():
    integration = TenantIntegration.query.filter_by(
        company_id=current_user.company_id, 
        provider='google_drive'
    ).first()
    
    if integration:
        db.session.delete(integration)
        db.session.commit()
        flash('Google Drive desconectado.', 'info')
        
    return redirect(url_for('integrations_bp.drive_settings_page'))
    return redirect(url_for('integrations_bp.drive_settings_page'))

# --- DRIVE TEMPLATES ---
from models import DriveFolderTemplate

@integrations_bp.route('/api/integrations/drive/templates', methods=['GET'])
@login_required
def list_drive_templates():
    templates = DriveFolderTemplate.query.filter_by(company_id=current_user.company_id).all()
    
    # If no templates, seed defaults
    if not templates:
        seed_drive_templates()
        templates = DriveFolderTemplate.query.filter_by(company_id=current_user.company_id).all()
        
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'structure': t.structure_json,
        'is_default': t.is_default
    } for t in templates])

@integrations_bp.route('/api/integrations/drive/templates/save', methods=['POST'])
@login_required
def save_drive_template():
    data = request.json
    template_id = data.get('id')
    name = data.get('name')
    structure_text = data.get('structure_text') # Indentation-based text
    
    if not name or not structure_text:
        return api_response(success=False, error='Nome e Estrutura são obrigatórios')
        
    # Parse Structure
    try:
        from services.google_drive_service import GoogleDriveService
        structure_list = GoogleDriveService.parse_structure_text(structure_text)
        structure_json = json.dumps(structure_list)
    except Exception as e:
        return api_response(success=False, error=f'Erro ao processar estrutura: {str(e)}')
        
    if template_id:
        template = DriveFolderTemplate.query.filter_by(id=template_id, company_id=current_user.company_id).first()
        if not template:
            return api_response(success=False, error='Template não encontrado')
        template.name = name
        template.structure_json = structure_json
    else:
        template = DriveFolderTemplate(
            company_id=current_user.company_id,
            name=name,
            structure_json=structure_json
        )
        db.session.add(template)
        
    db.session.commit()
    return api_response(success=True)

@integrations_bp.route('/api/integrations/drive/templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_drive_template(id):
    template = DriveFolderTemplate.query.filter_by(id=id, company_id=current_user.company_id).first()
    if template:
        db.session.delete(template)
        db.session.commit()
    return api_response(success=True)

def seed_drive_templates():
    """Seeds the 7 default templates for the current user's company."""
    defaults = [
        ("Universal / Simples", """
01 - Contratos & Financeiro
02 - Onboarding
03 - Materiais do Cliente
04 - Entregas
05 - Relatórios
        """),
        ("Agência de Marketing", """
01 - Contrato & Briefing
02 - Branding
    Logo
    Identidade Visual
    Manual de Marca
03 - Social Media
    Planejamento
    Criativos
        Feed
        Stories
        Reels
    Copies
    Aprovados
04 - Tráfego Pago
    Criativos
    Copies
    Relatórios
05 - Relatórios
06 - Arquivos Finais
        """),
        ("Consultoria / Estratégia", """
01 - Contrato & Escopo
02 - Diagnóstico
    Questionários
    Análises
    Insights
03 - Planejamento
    Estratégia
    Roadmap
    KPIs
04 - Execução
05 - Relatórios
06 - Reuniões & Atas
        """),
        ("TI / Software", """
01 - Contrato & Proposta
02 - Levantamento de Requisitos
03 - Documentação Técnica
    APIs
    Diagramas
    Credenciais
04 - Desenvolvimento
05 - Homologação
06 - Produção
07 - Relatórios & Logs
        """),
        ("Jurídico / Contábil", """
01 - Contrato & Procuração
02 - Documentos do Cliente
03 - Processos
04 - Petições & Protocolos
05 - Pareceres
06 - Financeiro
        """),
        ("Obras / Engenharia", """
01 - Contrato & Escopo
02 - Projeto
    Plantas
    3D / Render
    Aprovações
03 - Execução
    Cronograma
    Fotos de Obra
    Medições
04 - Fornecedores
05 - Relatórios
06 - Entrega Final
        """),
        ("Educação / Mentoria", """
01 - Contrato & Inscrição
02 - Materiais
    Aulas
    Slides
    Apostilas
03 - Exercícios
04 - Certificados
05 - Feedback & Avaliações
        """)
    ]
    
    from services.google_drive_service import GoogleDriveService
    
    for name, text in defaults:
        try:
            structure = GoogleDriveService.parse_structure_text(text)
            t = DriveFolderTemplate(
                company_id=current_user.company_id,
                name=name,
                structure_json=json.dumps(structure),
                is_default=False # User can edit, so treat as copies
            )
            db.session.add(t)
        except: pass
        
    db.session.commit()
