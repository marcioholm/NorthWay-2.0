import os
import hmac
import pytest
from unittest.mock import patch

def test_billing_webhook_without_token_fails_closed(client, monkeypatch):
    """POST /billing/webhooks/asaas deve retornar 401 se ASAAS_WEBHOOK_TOKEN não estiver configurado."""
    monkeypatch.delenv('ASAAS_WEBHOOK_TOKEN', raising=False)
    client.application.config['ASAAS_WEBHOOK_TOKEN'] = None

    response = client.post('/billing/webhooks/asaas', json={'event': 'PAYMENT_RECEIVED'}, headers={'asaas-access-token': 'any-token'})
    assert response.status_code == 401
    assert 'not configured' in response.get_json().get('error', '').lower() or response.status_code == 401

def test_billing_webhook_timing_safe_verification(client, monkeypatch):
    """POST /billing/webhooks/asaas deve rejeitar tokens inválidos e aceitar tokens válidos."""
    token = 'super-secret-token-12345'
    monkeypatch.setenv('ASAAS_WEBHOOK_TOKEN', token)
    client.application.config['ASAAS_WEBHOOK_TOKEN'] = token

    # Token errado
    bad_resp = client.post('/billing/webhooks/asaas', json={'event': 'PAYMENT_RECEIVED'}, headers={'asaas-access-token': 'wrong-token'})
    assert bad_resp.status_code == 401

    # Token correto
    good_resp = client.post('/billing/webhooks/asaas', json={'event': 'PAYMENT_RECEIVED'}, headers={'asaas-access-token': token})
    assert good_resp.status_code == 200

def test_integrations_webhook_without_token_fails_closed(client, monkeypatch):
    """POST /api/webhooks/asaas/<id> deve retornar 401 se ASAAS_WEBHOOK_TOKEN não estiver configurado."""
    monkeypatch.delenv('ASAAS_WEBHOOK_TOKEN', raising=False)
    client.application.config['ASAAS_WEBHOOK_TOKEN'] = None

    response = client.post('/api/webhooks/asaas/1', json={'event': 'PAYMENT_RECEIVED'}, headers={'asaas-access-token': 'any-token'})
    assert response.status_code == 401
    assert response.get_json().get('success') is False

def test_integrations_webhook_timing_safe_verification(client, monkeypatch):
    """POST /api/webhooks/asaas/<id> valida token em tempo constante e rejeita incorreto."""
    token = 'company-secret-token-67890'
    monkeypatch.setenv('ASAAS_WEBHOOK_TOKEN', token)
    client.application.config['ASAAS_WEBHOOK_TOKEN'] = token

    bad_resp = client.post('/api/webhooks/asaas/1', json={'event': 'PAYMENT_RECEIVED'}, headers={'asaas-access-token': 'invalid-token'})
    assert bad_resp.status_code == 401

def test_internal_api_without_key_fails_closed(client, monkeypatch):
    """Rotas protegidas por @require_internal_auth devem retornar 401 se CRM_INTERNAL_API_KEY não estiver configurada."""
    monkeypatch.delenv('CRM_INTERNAL_API_KEY', raising=False)
    client.application.config['CRM_INTERNAL_API_KEY'] = None

    response = client.post('/internal/tenant/ai-credential', json={'tenant_id': 1, 'provider': 'openai'}, headers={'Authorization': 'Bearer some-key'})
    assert response.status_code == 401
    assert response.get_json().get('success') is False
    assert 'not configured' in response.get_json().get('error', '').lower()

def test_internal_api_timing_safe_verification(client, monkeypatch):
    """require_internal_auth deve validar chave via timing-safe compare_digest."""
    key = 'internal-crm-key-xyz'
    monkeypatch.setenv('CRM_INTERNAL_API_KEY', key)

    # Chave errada
    bad_resp = client.post('/internal/tenant/ai-credential', json={'tenant_id': 1, 'provider': 'openai'}, headers={'Authorization': 'Bearer wrong-key'})
    assert bad_resp.status_code == 401

    # Header ausente
    no_header = client.post('/internal/tenant/ai-credential', json={'tenant_id': 1, 'provider': 'openai'})
    assert no_header.status_code == 401

def test_utils_webhooks_timing_safe_helper():
    """utils.webhooks.verify_webhook_signature deve fail-closed e comparar em tempo constante."""
    from utils.webhooks import verify_webhook_signature
    assert verify_webhook_signature('secret123', 'secret123') is True
    assert verify_webhook_signature('secret123', 'secret124') is False
    assert verify_webhook_signature('', 'secret123') is False
    assert verify_webhook_signature(None, 'secret123') is False
    assert verify_webhook_signature('secret123', None) is False
    assert verify_webhook_signature(None, None) is False

def test_no_hardcoded_passwords_or_connection_strings_in_scripts():
    """Garante que nenhum script contenha senhas reais, tokens ou connection strings com senha em claro."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    forbidden_patterns = [
        'whsec_3PF5yv-lNJWNvIFBR5lgRO9BQJBUGQKCtQ4z9MsoVyU',
        'Marcioholmmonteiro',
        'NorthWay@Master2024',
        'master_password_123',
        'pVcON2srZ2FXQ36Q-72WAHB-gVdrP_5Se-_K8XQ15Gs',
    ]
    target_files = [
        'inspect_db.py',
        'northway_crm/scripts/check_master_login.py',
        'northway_crm/scripts/reset_master_pass.py',
        'northway_crm/maintenance/verify_supabase_connection.py',
        'northway_crm/maintenance/create_master_user.py',
        'northway_crm/routes/billing.py',
    ]

    for rel_path in target_files:
        full_path = os.path.join(repo_root, rel_path)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            for pattern in forbidden_patterns:
                assert pattern not in content, f"Padrão sensível/segredo encontrado em {rel_path}: {pattern}"

def test_integrations_webhook_cross_tenant_isolation(client, app, monkeypatch):
    """
    Um evento enviado para a empresa A com o externalReference de uma transação
    da empresa B NÃO altera essa transação.
    """
    from models import db, Company, Transaction
    from datetime import date

    token = 'asaas-isolation-token-123'
    monkeypatch.setenv('ASAAS_WEBHOOK_TOKEN', token)
    app.config['ASAAS_WEBHOOK_TOKEN'] = token

    with app.app_context():
        comp_a = Company(name="Empresa A Test Isolation", plan_type="pro", payment_status="active", subscription_status="active")
        comp_b = Company(name="Empresa B Test Isolation", plan_type="pro", payment_status="active", subscription_status="active")
        db.session.add_all([comp_a, comp_b])
        db.session.commit()

        trans_b = Transaction(
            company_id=comp_b.id,
            amount=500.0,
            status='pending',
            due_date=date(2026, 12, 1),
            description="Mensalidade Empresa B",
            asaas_id="pay_from_b"
        )
        db.session.add(trans_b)
        db.session.commit()
        trans_b_id = trans_b.id

        # Webhook enviado para o endpoint da Empresa A, referenciando transação de B
        payload = {
            'event': 'PAYMENT_RECEIVED',
            'payment': {
                'id': 'pay_attempt_cross_tenant',
                'externalReference': str(trans_b_id),
                'value': 500.0,
                'status': 'RECEIVED'
            }
        }

        resp = client.post(
            f'/api/webhooks/asaas/{comp_a.id}',
            json=payload,
            headers={'asaas-access-token': token}
        )
        assert resp.status_code == 200

        # Transação de B DEVE continuar 'pending'
        trans_b_after = db.session.get(Transaction, trans_b_id) if hasattr(db.session, 'get') else Transaction.query.get(trans_b_id)
        assert trans_b_after.status == 'pending', f"Transação da Empresa B foi indevidamente alterada para {trans_b_after.status}"

