import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, TenantAICredential, ProspectingIntegration
from utils.crypto import encrypt_api_key, decrypt_api_key
from datetime import datetime
import logging
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)

ai_settings_bp = Blueprint('ai_settings', __name__)


@ai_settings_bp.route('/settings/ai')
@login_required
def index():
    if not current_user.company.has_feature('prospecting'):
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))

    company_id = current_user.company_id

    credentials = TenantAICredential.query.filter_by(company_id=company_id).all()
    integrations = ProspectingIntegration.query.filter_by(company_id=company_id).all()

    # Serialize credentials (securely, no keys)
    credentials_data = []
    for c in credentials:
        credentials_data.append({
            "id": str(c.id),
            "company_id": c.company_id,
            "provider": c.provider,
            "api_key_last4": c.api_key_last4,
            "base_url": c.base_url,
            "model": c.model,
            "status": c.status,
            "last_test_at": c.last_test_at.isoformat() if c.last_test_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        })

    # Serialize integrations
    integrations_data = []
    for i in integrations:
        integrations_data.append({
            "id": str(i.id),
            "company_id": i.company_id,
            "provider": i.provider,
            "api_base_url": i.api_base_url,
            "instance_name": i.instance_name,
            "display_name": i.display_name,
            "api_key_last4": i.api_key_last4,
            "status": i.status,
            "smtp_host": getattr(i, 'smtp_host', None),
            "smtp_port": getattr(i, 'smtp_port', None),
            "smtp_user": getattr(i, 'smtp_user', None),
            "sender_name": getattr(i, 'sender_name', None),
            "sender_email": getattr(i, 'sender_email', None),
            "ssl_tls": getattr(i, 'ssl_tls', True),
            "created_at": i.created_at.isoformat() if hasattr(i, 'created_at') and i.created_at else None,
            "updated_at": i.updated_at.isoformat() if hasattr(i, 'updated_at') and i.updated_at else None
        })

    return render_template('settings_ai.html',
                           credentials=credentials_data,
                           integrations=integrations_data)


@ai_settings_bp.route('/settings/ai/credential/save', methods=['POST'])
@login_required
def save_credential():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')
    api_key = data.get('api_key')
    model = data.get('model')
    base_url = data.get('base_url')

    if not provider or not api_key:
        return jsonify({'success': False, 'error': 'Provider e API Key são obrigatórios'}), 400

    try:
        encrypted, last4 = encrypt_api_key(api_key)
        
        logger.info(f"[AI_SAVE] Attempting to save credential for company_id={company_id}, provider={provider}")

        credential = TenantAICredential.query.filter_by(
            company_id=company_id,
            provider=provider
        ).first()

        if credential:
            credential.api_key_encrypted = encrypted
            credential.api_key_last4 = last4
            credential.model = model
            credential.base_url = base_url
            credential.status = 'active'
            credential.updated_at = datetime.utcnow()
        else:
            credential = TenantAICredential(
                company_id=company_id,
                provider=provider,
                api_key_encrypted=encrypted,
                api_key_last4=last4,
                model=model,
                base_url=base_url,
                status='active'
            )
            db.session.add(credential)

        db.session.commit()
        
        # Validate persistence
        db.session.refresh(credential)
        saved_check = TenantAICredential.query.get(credential.id)
        if not saved_check:
            logger.error(f"[AI_SAVE] Failed to verify persistence for provider={provider}, company_id={company_id}")
            return jsonify({'success': False, 'error': 'Falha na persistência dos dados no banco de dados.'}), 500
            
        logger.info(f"[AI_SAVE] Successfully saved and verified credential for provider={provider}")
        return jsonify({'success': True, 'data': {'last4': last4}})

    except Exception as e:
        logger.error(f"[AI_SAVE] Error saving credential: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Erro interno ao salvar: {str(e)}'}), 500


@ai_settings_bp.route('/settings/ai/credential/test', methods=['POST'])
@login_required
def test_credential():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')
    api_key_from_form = data.get('api_key')
    base_url_from_form = data.get('base_url')

    logger.info(f"[AI_TEST] Testing connection for provider={provider}, company_id={company_id}")

    # Flow: Prefer form data if available (allows testing before saving), fallback to DB
    api_key = api_key_from_form
    test_url = base_url_from_form

    if not api_key:
        logger.info(f"[AI_TEST] No API key in form, looking up saved credential")
        credential = TenantAICredential.query.filter_by(
            company_id=company_id,
            provider=provider
        ).first()

        if not credential:
            return jsonify({'success': False, 'error': 'Nenhuma chave fornecida e nenhuma credencial salva encontrada.'}), 404
        
        api_key = decrypt_api_key(credential.api_key_encrypted)
        test_url = test_url or credential.base_url
        if not api_key:
             return jsonify({'success': False, 'error': 'Falha ao descriptografar a chave salva.'}), 500

    # Standardize Provider URLs
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    if provider == 'openai':
        test_url = test_url or 'https://api.openai.com/v1/chat/completions'
        test_payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
        method = 'POST'
    elif provider == 'groq':
        test_url = test_url or 'https://api.groq.com/openai/v1/chat/completions'
        test_payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
        method = 'POST'
    elif provider == 'openrouter':
        test_url = test_url or 'https://openrouter.ai/api/v1/chat/completions'
        headers['HTTP-Referer'] = 'https://crm.northwaycompany.com.br'
        headers['X-Title'] = 'NorthWay CRM'
        test_payload = {"model": "google/gemini-pro-1.5", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
        method = 'POST'
    elif provider == 'anthropic':
        test_url = test_url or 'https://api.anthropic.com/v1/messages'
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }
        test_payload = {"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
        method = 'POST'
    elif provider == 'google':
        # Gemini test
        test_url = test_url or f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
        headers = {'Content-Type': 'application/json'}
        test_payload = {"contents": [{"parts": [{"text": "ping"}]}]}
        method = 'POST'
    else:
        return jsonify({'success': False, 'error': f'Provider {provider} não suportado para teste automático.'}), 400

    try:
        logger.info(f"[AI_TEST] Sending {method} request to {test_url}")
        if method == 'POST':
            response = requests.post(test_url, headers=headers, json=test_payload, timeout=15)
        else:
            response = requests.get(test_url, headers=headers, timeout=15)

        logger.info(f"[AI_TEST] Response status: {response.status_code}")

        if response.status_code in [200, 201]:
            # Success! Update last_test_at if we have a saved credential
            saved_cred = TenantAICredential.query.filter_by(company_id=company_id, provider=provider).first()
            if saved_cred:
                saved_cred.last_test_at = datetime.utcnow()
                db.session.commit()
            return jsonify({'success': True, 'data': {'status': 'connected'}})
        else:
            error_data = response.text
            try:
                error_json = response.json()
                if 'error' in error_json:
                    error_data = error_json['error'].get('message', error_data)
            except:
                pass
            logger.error(f"[AI_TEST] API Error: {response.status_code} - {error_data}")
            return jsonify({'success': False, 'error': f'Erro na API ({response.status_code}): {error_data[:200]}'}), 400

    except Exception as e:
        logger.error(f"[AI_TEST] Connection exception: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'Falha de conexão: {str(e)}'}), 500

@ai_settings_bp.route('/settings/ai/debug', methods=['GET'])
@login_required
def debug_info():
    if not current_user.is_super_admin:
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
    company_id = current_user.company_id
    credentials = TenantAICredential.query.filter_by(company_id=company_id).all()
    
    debug_data = []
    for cred in credentials:
        debug_data.append({
            'provider': cred.provider,
            'model': cred.model,
            'base_url': cred.base_url,
            'has_api_key': bool(cred.api_key_encrypted),
            'last4': cred.api_key_last4,
            'status': cred.status,
            'last_test': str(cred.last_test_at) if cred.last_test_at else None
        })
        
    return jsonify({
        'success': True,
        'tenant_id': company_id,
        'credentials': debug_data
    })


@ai_settings_bp.route('/settings/ai/credential/delete', methods=['POST'])
@login_required
def delete_credential():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')

    credential = TenantAICredential.query.filter_by(
        company_id=company_id,
        provider=provider
    ).first()

    if credential:
        db.session.delete(credential)
        db.session.commit()

    return jsonify({'success': True})


@ai_settings_bp.route('/settings/ai/integration/save', methods=['POST'])
@login_required
def save_integration():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')
    api_base_url = data.get('api_base_url')
    instance_name = data.get('instance_name')
    display_name = data.get('display_name')
    api_key = data.get('api_key')

    if not provider:
        return jsonify({'success': False, 'error': 'Provider é obrigatório'}), 400

    # Evolution API Instance Name Validation
    if provider == 'evolution_api' and instance_name:
        import re
        if not re.match(r'^[a-z0-9_-]+$', instance_name):
            return jsonify({
                'success': False, 
                'error': 'O nome técnico da instância deve conter apenas letras minúsculas, números, hífen ou underline.'
            }), 400

    encrypted = None
    last4 = None
    if api_key:
        encrypted, last4 = encrypt_api_key(api_key)

    integration = ProspectingIntegration.query.filter_by(
        company_id=company_id,
        provider=provider
    ).first()

    if not integration:
        integration = ProspectingIntegration(company_id=company_id, provider=provider)
        db.session.add(integration)

    # Common fields
    integration.api_base_url = api_base_url
    integration.instance_name = instance_name
    integration.display_name = display_name
    if encrypted:
        integration.api_key_encrypted = encrypted
        integration.api_key_last4 = last4
    
    # SMTP specific fields
    if provider == 'smtp':
        integration.smtp_host = data.get('smtp_host')
        try:
            integration.smtp_port = int(data.get('smtp_port')) if data.get('smtp_port') else None
        except:
            pass
        integration.smtp_user = data.get('smtp_user')
        integration.sender_name = data.get('sender_name')
        integration.sender_email = data.get('sender_email')
        integration.ssl_tls = data.get('ssl_tls', True)

    integration.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True})


@ai_settings_bp.route('/settings/ai/integration/test', methods=['POST'])
@login_required
def test_integration():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')

    integration = ProspectingIntegration.query.filter_by(
        company_id=company_id,
        provider=provider
    ).first()

    if not integration:
        return jsonify({'success': False, 'error': 'Integração não encontrada'}), 404

    if provider == 'evolution_api':
        try:
            api_key = decrypt_api_key(integration.api_key_encrypted) if integration.api_key_encrypted else None
            if not api_key or not integration.api_base_url or not integration.instance_name:
                return jsonify({'success': False, 'error': 'Configuração incompleta'}), 400

            response = requests.get(
                f"{integration.api_base_url}/instance/connectionState/{integration.instance_name}",
                headers={'apikey': api_key},
                timeout=10
            )

            if response.status_code == 200:
                integration.status = 'active'
                integration.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'success': True, 'data': {'status': 'connected', 'instance': integration.instance_name}})
            else:
                integration.status = 'error'
                db.session.commit()
                return jsonify({'success': False, 'error': f'API retornou erro: {response.status_code}'}), 400
        except Exception as e:
            integration.status = 'error'
            db.session.commit()
            return jsonify({'success': False, 'error': str(e)}), 500

    elif provider == 'smtp':
        try:
            password = decrypt_api_key(integration.api_key_encrypted) if integration.api_key_encrypted else None
            host = integration.smtp_host
            port = integration.smtp_port
            user = integration.smtp_user
            
            if not host or not port or not user or not password:
                 return jsonify({'success': False, 'error': 'Configuração SMTP incompleta'}), 400
            
            # Test e-mail content
            msg = EmailMessage()
            msg.set_content(f"Este é um e-mail de teste do NorthWay CRM para validar suas configurações SMTP.\n\nEnviado em: {datetime.utcnow().isoformat()} UTC")
            msg['Subject'] = 'NorthWay CRM - Teste de Conexão SMTP'
            
            sender_display = integration.sender_name or "NorthWay CRM"
            sender_addr = integration.sender_email or user
            msg['From'] = f"{sender_display} <{sender_addr}>"
            msg['To'] = sender_addr
            
            logger.info(f"[SMTP_TEST] Connecting to {host}:{port} (SSL: {integration.ssl_tls})")
            
            if integration.ssl_tls:
                # SSL (Port 465)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                    server.login(user, password)
                    server.send_message(msg)
            else:
                # STARTTLS (Port 587) or Plain
                with smtplib.SMTP(host, port, timeout=15) as server:
                    try:
                        server.starttls(context=ssl.create_default_context())
                    except Exception as stls_err:
                        logger.warning(f"STARTTLS failed (might be plain connection): {stls_err}")
                    server.login(user, password)
                    server.send_message(msg)
            
            integration.status = 'active'
            integration.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'data': {'status': 'connected', 'message': 'E-mail de teste enviado!'}})
            
        except Exception as e:
            logger.error(f"SMTP Test Error: {str(e)}", exc_info=True)
            integration.status = 'error'
            db.session.commit()
            return jsonify({'success': False, 'error': f'Erro SMTP: {str(e)}'}), 500

    return jsonify({'success': False, 'error': 'Provider não suportado para teste'}), 400


@ai_settings_bp.route('/settings/ai/integration/delete', methods=['POST'])
@login_required
def delete_integration():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')

    integration = ProspectingIntegration.query.filter_by(
        company_id=company_id,
        provider=provider
    ).first()

    if integration:
        db.session.delete(integration)
        db.session.commit()

    return jsonify({'success': True})


@ai_settings_bp.route('/settings/ai/integration/toggle', methods=['POST'])
@login_required
def toggle_integration():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')
    active = data.get('active', False)

    integration = ProspectingIntegration.query.filter_by(
        company_id=company_id,
        provider=provider
    ).first()

    if integration:
        integration.status = 'active' if active else 'inactive'
        integration.updated_at = datetime.utcnow()
        db.session.commit()

    return jsonify({'success': True})