"""O webhook configurado no Asaas precisa levar o authToken que o CRM exige."""
from unittest.mock import MagicMock, patch


def _resp(status=200, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.text = ''
    return r


def test_create_webhook_sends_auth_token(app, monkeypatch):
    monkeypatch.setenv('ASAAS_WEBHOOK_TOKEN', 'tok_test_1234567890abcdef1234567890')
    app.config['ASAAS_WEBHOOK_TOKEN'] = 'tok_test_1234567890abcdef1234567890'
    from services import asaas_service

    with patch.object(asaas_service.requests, 'get', return_value=_resp(200, {'data': []})), \
         patch.object(asaas_service.requests, 'post', return_value=_resp(200, {'id': 'wh_1', 'authToken': 'tok_test_1234567890abcdef1234567890'})) as post:
        data, err = asaas_service.create_webhook('https://crm.example/api/webhooks/asaas/1', 'a@b.com', api_key='k')

    assert err is None
    sent = post.call_args.kwargs['json']
    assert sent['authToken'] == 'tok_test_1234567890abcdef1234567890'
    assert sent['interrupted'] is False
    assert 'authToken' not in data  # o token não volta para a tela


def test_create_webhook_updates_only_crm_webhook(app, monkeypatch):
    app.config['ASAAS_WEBHOOK_TOKEN'] = 'tok_test_1234567890abcdef1234567890'
    from services import asaas_service
    existing = {'data': [
        {'id': 'wh_outro', 'name': 'Outro sistema', 'url': 'https://outro.example/hook'},
        {'id': 'wh_crm', 'name': 'NorthWay CRM Integration', 'url': 'https://crm.example/api/webhooks/asaas/1'},
    ]}
    with patch.object(asaas_service.requests, 'get', return_value=_resp(200, existing)), \
         patch.object(asaas_service.requests, 'put', return_value=_resp(200, {'id': 'wh_crm'})) as put, \
         patch.object(asaas_service.requests, 'post') as post:
        _, err = asaas_service.create_webhook('https://crm.example/api/webhooks/asaas/1', 'a@b.com', api_key='k')

    assert err is None
    assert put.call_args.args[0].endswith('/webhooks/wh_crm')
    post.assert_not_called()


def test_create_webhook_without_token_does_not_call_asaas(app, monkeypatch):
    monkeypatch.delenv('ASAAS_WEBHOOK_TOKEN', raising=False)
    app.config['ASAAS_WEBHOOK_TOKEN'] = None
    from services import asaas_service
    with patch.object(asaas_service.requests, 'get') as get, patch.object(asaas_service.requests, 'post') as post:
        data, err = asaas_service.create_webhook('https://crm.example/x', 'a@b.com', api_key='k')
    assert data is None and 'ASAAS_WEBHOOK_TOKEN' in err
    get.assert_not_called()
    post.assert_not_called()
