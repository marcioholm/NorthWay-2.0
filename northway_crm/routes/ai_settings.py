import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, TenantAICredential, ProspectingIntegration
from utils.crypto import encrypt_api_key, decrypt_api_key
from datetime import datetime

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

    return render_template('settings_ai.html',
                           credentials=credentials,
                           integrations=integrations)


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

    encrypted, last4 = encrypt_api_key(api_key)

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

    return jsonify({'success': True, 'data': {'last4': last4}})


@ai_settings_bp.route('/settings/ai/credential/test', methods=['POST'])
@login_required
def test_credential():
    if not current_user.company.has_feature('prospecting'):
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403

    company_id = current_user.company_id
    data = request.json

    provider = data.get('provider')

    credential = TenantAICredential.query.filter_by(
        company_id=company_id,
        provider=provider,
        status='active'
    ).first()

    if not credential:
        return jsonify({'success': False, 'error': 'Credencial não encontrada'}), 404

    api_key = decrypt_api_key(credential.api_key_encrypted)

    test_url = credential.base_url
    headers = {'Authorization': f'Bearer {api_key}'}

    if provider == 'openai':
        test_url = test_url or 'https://api.openai.com/v1/models'
    elif provider == 'groq':
        test_url = test_url or 'https://api.groq.com/openai/v1/models'
    elif provider == 'openrouter':
        test_url = test_url or 'https://openrouter.ai/api/v1/models'
        headers['HTTP-Referer'] = 'https://crm.northwaycompany.com.br' # OpenRouter requirement
        headers['X-Title'] = 'NorthWay CRM'
    elif provider == 'anthropic':
        test_url = 'https://api.anthropic.com/v1/messages' # Anthropic test is harder, but we can try simple check
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }
        # Just a dummy check for Anthropic
        try:
             response = requests.post(test_url, headers=headers, json={"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}, timeout=10)
             if response.status_code in [200, 400]: # 400 might be just param error but auth worked
                 credential.last_test_at = datetime.utcnow()
                 db.session.commit()
                 return jsonify({'success': True, 'data': {'status': 'connected'}})
        except:
             pass
        return jsonify({'success': False, 'error': 'Anthropic verification failed'}), 400

    try:
        response = requests.get(test_url, headers=headers, timeout=10)
        if response.status_code == 200:
            credential.last_test_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'data': {'status': 'connected', 'models': response.json().get('data', [])[:5]}})
        else:
            return jsonify({'success': False, 'error': f'API retornou erro: {response.status_code} - {response.text[:100]}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
    api_key = data.get('api_key')

    if not provider:
        return jsonify({'success': False, 'error': 'Provider é obrigatório'}), 400

    encrypted = None
    last4 = None
    if api_key:
        encrypted, last4 = encrypt_api_key(api_key)

    integration = ProspectingIntegration.query.filter_by(
        company_id=company_id,
        provider=provider
    ).first()

    if integration:
        integration.api_base_url = api_base_url
        integration.instance_name = instance_name
        if encrypted:
            integration.api_key_encrypted = encrypted
            integration.api_key_last4 = last4
        integration.updated_at = datetime.utcnow()
    else:
        integration = ProspectingIntegration(
            company_id=company_id,
            provider=provider,
            api_base_url=api_base_url,
            instance_name=instance_name,
            api_key_encrypted=encrypted,
            api_key_last4=last4,
            status='inactive'
        )
        db.session.add(integration)

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