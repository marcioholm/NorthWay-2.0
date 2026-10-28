import os
import pytest
from models import db, Company, WhatsappInstance, WhatsappConversation, WhatsappMessage

def test_evolution_webhook_get_returns_405(client):
    """GET /api/webhooks/evolution deve retornar 405 Method Not Allowed."""
    resp = client.get('/api/webhooks/evolution')
    assert resp.status_code == 405

def test_evolution_webhook_without_token_fails_closed(client, monkeypatch):
    """POST /api/webhooks/evolution sem EVOLUTION_WEBHOOK_TOKEN configurado deve retornar 401 (fail-closed)."""
    monkeypatch.delenv('EVOLUTION_WEBHOOK_TOKEN', raising=False)
    client.application.config['EVOLUTION_WEBHOOK_TOKEN'] = None

    resp = client.post(
        '/api/webhooks/evolution',
        json={'event': 'CONNECTION_UPDATE', 'instance': 'inst-1', 'data': {'state': 'open'}},
        headers={'apikey': 'any-token'}
    )
    assert resp.status_code == 401
    assert 'not configured' in resp.get_json().get('error', '').lower()

def test_evolution_webhook_invalid_token_returns_401(client, monkeypatch):
    """POST /api/webhooks/evolution com token inválido deve retornar 401."""
    monkeypatch.setenv('EVOLUTION_WEBHOOK_TOKEN', 'valid-secret-token')
    client.application.config['EVOLUTION_WEBHOOK_TOKEN'] = 'valid-secret-token'

    # Sem header
    resp_no_header = client.post(
        '/api/webhooks/evolution',
        json={'event': 'CONNECTION_UPDATE', 'instance': 'inst-1', 'data': {'state': 'open'}}
    )
    assert resp_no_header.status_code == 401

    # Header apikey incorreto
    resp_bad = client.post(
        '/api/webhooks/evolution',
        json={'event': 'CONNECTION_UPDATE', 'instance': 'inst-1', 'data': {'state': 'open'}},
        headers={'apikey': 'wrong-token'}
    )
    assert resp_bad.status_code == 401

def test_evolution_webhook_valid_token_processes_event(client, app, monkeypatch):
    """POST /api/webhooks/evolution com token válido deve autenticar e processar normalmente."""
    token = 'evolution-token-xyz'
    monkeypatch.setenv('EVOLUTION_WEBHOOK_TOKEN', token)
    app.config['EVOLUTION_WEBHOOK_TOKEN'] = token

    with app.app_context():
        comp = Company(name="Evolution Test Co", plan_type="pro", payment_status="active", subscription_status="active")
        db.session.add(comp)
        db.session.commit()

        inst = WhatsappInstance(company_id=comp.id, instance_name="minha-instancia", status="disconnected")
        db.session.add(inst)
        db.session.commit()
        inst_id = inst.id

        # 1. Test CONNECTION_UPDATE
        payload_conn = {
            'event': 'CONNECTION_UPDATE',
            'instance': 'minha-instancia',
            'data': {'state': 'open'}
        }
        resp = client.post(
            '/api/webhooks/evolution',
            json=payload_conn,
            headers={'apikey': token}
        )
        assert resp.status_code == 200

        inst_updated = db.session.get(WhatsappInstance, inst_id)
        assert inst_updated.status == 'open'

def test_evolution_webhook_does_not_dump_to_tmp(client, app, monkeypatch):
    """Garante que payloads de webhook não sejam despejados em arquivos no /tmp."""
    token = 'evolution-token-xyz'
    monkeypatch.setenv('EVOLUTION_WEBHOOK_TOKEN', token)
    app.config['EVOLUTION_WEBHOOK_TOKEN'] = token

    # Remove arquivos de teste prévios se existirem
    for tmp_file in ['/tmp/evolution_webhook_debug.json', '/tmp/last_whatsapp_webhook_error.json']:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass

    with app.app_context():
        # Webhook para instância desconhecida
        resp = client.post(
            '/api/webhooks/evolution',
            json={'event': 'CONNECTION_UPDATE', 'instance': 'non-existent-inst', 'secret_payload': 'sensivel'},
            headers={'apikey': token}
        )
        assert resp.status_code == 200

        # Verifica que nenhum dump foi criado no /tmp
        assert not os.path.exists('/tmp/last_whatsapp_webhook_error.json'), "/tmp/last_whatsapp_webhook_error.json foi criado"
        assert not os.path.exists('/tmp/evolution_webhook_debug.json'), "/tmp/evolution_webhook_debug.json foi criado"

def test_evolution_webhook_does_not_call_query_all(client, app, monkeypatch):
    """Garante que a busca de instância seja pontual e nunca use WhatsappInstance.query.all()."""
    token = 'evolution-token-xyz'
    monkeypatch.setenv('EVOLUTION_WEBHOOK_TOKEN', token)
    app.config['EVOLUTION_WEBHOOK_TOKEN'] = token

    def mock_all(*args, **kwargs):
        raise AssertionError("WhatsappInstance.query.all() NÃO deve ser chamado no webhook!")

    monkeypatch.setattr("models.WhatsappInstance.query.__class__.all", mock_all)

    with app.app_context():
        comp = Company(name="Evolution Co Test", plan_type="pro", payment_status="active", subscription_status="active")
        db.session.add(comp)
        db.session.commit()

        inst = WhatsappInstance(company_id=comp.id, instance_name="instancia-direta", status="disconnected")
        db.session.add(inst)
        db.session.commit()

        resp = client.post(
            '/api/webhooks/evolution',
            json={'event': 'CONNECTION_UPDATE', 'instance': 'instancia-direta', 'data': {'state': 'open'}},
            headers={'apikey': token}
        )
        assert resp.status_code == 200
        inst_updated = db.session.get(WhatsappInstance, inst.id)
        assert inst_updated.status == 'open'

