import pytest
import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from models import db, Lead, Company, Pipeline, PipelineStage, Interaction, WhatsappInstance, WhatsappConversation

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv('INTERNAL_API_KEY', 'test-internal-key')
    monkeypatch.setenv('CRM_INTERNAL_API_KEY', 'test-internal-key')
    monkeypatch.setenv('EVOLUTION_WEBHOOK_TOKEN', 'test-evo-token')


def test_privacidade_public_endpoint(client):
    """Garante que /privacidade responde publicamente com 200"""
    resp = client.get('/privacidade')
    assert resp.status_code == 200
    assert b"Pol\xc3\xadtica de Privacidade" in resp.data or b"Privacidade" in resp.data


def test_meta_pixel_rendered_on_raiox_page(client):
    """Garante que o código base do Meta Pixel com ID correto está presente em /raiox"""
    resp = client.get('/raiox')
    assert resp.status_code == 200
    assert b"2336445306916882" in resp.data
    assert b"fbq('init', '2336445306916882')" in resp.data
    assert b"fbq('track', 'PageView')" in resp.data
    assert b"https://www.facebook.com/tr?id=2336445306916882" in resp.data


def test_progresso_create_and_update(client, app):
    """Testa captura parcial via /raiox/progresso: criação e atualização"""
    with app.app_context():
        company = Company.query.first() or Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

    token = "test-token-prog-123"

    # 1. Envio de dados preliminares
    payload_dados = {
        "token": token,
        "etapa": "dados",
        "lead_info": {
            "nome": "Carlos Silva",
            "email": "carlos@empresa.com",
            "whatsapp": "(42) 99988-7766",
            "empresa": "Silva Distribuidora",
            "quantidade_funcionarios": "6-20",
            "faturamento_mensal": "30k-50k",
            "origem": "facebook",
            "utm_source": "meta_ads",
            "utm_campaign": "escala_nov2026"
        }
    }
    resp = client.post('/raiox/progresso', json=payload_dados)
    assert resp.status_code == 200
    assert resp.json == {'status': 'ok'}

    with app.app_context():
        lead = Lead.query.filter_by(raiox_token=token).first()
        assert lead is not None
        assert lead.name == "Carlos Silva"
        assert lead.email == "carlos@empresa.com"
        assert lead.source == "Raio-X Digital (parcial)"
        assert lead.raiox_status == "parcial_dados"
        assert lead.utm_source == "meta_ads"
        assert lead.pipeline_stage_id is None # Parcial não entra no pipeline

    # 2. Início do diagnóstico (etapa = 'iniciou')
    resp2 = client.post('/raiox/progresso', json={"token": token, "etapa": "iniciou"})
    assert resp2.status_code == 200

    with app.app_context():
        lead = Lead.query.filter_by(raiox_token=token).first()
        assert lead.raiox_status == "parcial_iniciou"
        assert lead.consentimento is True
        assert lead.consentimento_em is not None

    # 3. Resposta de perguntas progressivas
    answers = [2, 3, 1] + [None] * 17
    resp3 = client.post('/raiox/progresso', json={
        "token": token,
        "etapa": 3,
        "answers": answers
    })
    assert resp3.status_code == 200

    with app.app_context():
        lead = Lead.query.filter_by(raiox_token=token).first()
        assert lead.raiox_ultima_pergunta == 3
        assert lead.raiox_respostas_parciais[0] == 2
        assert lead.raiox_respostas_parciais[1] == 3


def test_retomada_via_token(client, app):
    """Testa abertura com ?retomar=<token> carregando dados"""
    token = "token-retomada-abc"
    with app.app_context():
        company = Company.query.first()
        if not company:
            company = Company(name="Test Co")
            db.session.add(company)
            db.session.commit()
        lead = Lead(
            company_id=company.id,
            name="Mariana Souza",
            email="mariana@teste.com",
            phone="42999112233",
            whatsapp="42999112233",
            legal_name="Souza Tech",
            raiox_token=token,
            raiox_status="parcial_iniciou",
            raiox_ultima_pergunta=5,
            raiox_respostas_parciais=[2, 2, 3, 1, 2] + [None] * 15
        )
        db.session.add(lead)
        db.session.commit()

    resp = client.get(f'/raiox?retomar={token}')
    assert resp.status_code == 200
    assert b"Mariana Souza" in resp.data
    assert b"Souza Tech" in resp.data
    assert b"token-retomada-abc" in resp.data


def test_submit_primeira_conclusao_vs_reenvio(client, app):
    """Testa se submit aloca no pipeline e dispara n8n apenas na primeira conclusão"""
    with app.app_context():
        company = Company.query.first()
        if not company:
            company = Company(name="Test Co")
            db.session.add(company)
            db.session.commit()

        pipeline = Pipeline(name="Vendas", company_id=company.id)
        db.session.add(pipeline)
        db.session.commit()
        stage = PipelineStage(name="Novo Lead", pipeline_id=pipeline.id, company_id=company.id, order=1)
        db.session.add(stage)
        db.session.commit()

    token = "token-submit-xyz"
    answers = [2] * 20
    payload = {
        "token": token,
        "lead_info": {
            "nome": "Fernando Dias",
            "email": "fernando@dias.com",
            "whatsapp": "42999778899",
            "empresa": "Dias Transportes",
            "quantidade_funcionarios": "21-50",
            "faturamento_mensal": "50k-100k",
            "origem": "google"
        },
        "answers": answers
    }

    with patch('routes.diagnostic_raiox.dispatch_n8n_raiox_webhook') as mock_webhook:
        resp = client.post('/raiox/submit', json=payload)
        assert resp.status_code == 200
        assert resp.json.get('status') == 'success'
        assert mock_webhook.called

        with app.app_context():
            lead = Lead.query.filter_by(raiox_token=token).first()
            assert lead.raiox_status == 'concluido'
            assert lead.source == 'Raio-X Digital'
            assert lead.pipeline_stage_id is not None
            assert lead.meta_event_id is not None
        assert resp.json.get('event_id') is not None

    # Reenvio do teste com o mesmo token
    with patch('routes.diagnostic_raiox.dispatch_n8n_raiox_webhook') as mock_webhook_re:
        resp_re = client.post('/raiox/submit', json=payload)
        assert resp_re.status_code == 200
        assert not mock_webhook_re.called # NÃO deve redisparar n8n em reenvio


def test_internal_raiox_abandonados_endpoint(client, app):
    """Testa endpoint interno de abandonados com autenticação e filtros"""
    with app.app_context():
        company = Company.query.first()
        if not company:
            company = Company(name="Test Co")
            db.session.add(company)
            db.session.commit()

        agora = datetime.utcnow()

        # Lead 1: Abandonado elegível (atualizado há 45 min)
        lead_ok = Lead(
            company_id=company.id,
            name="Abandonado 1",
            phone="42999001122",
            raiox_token="tok-abandonado-1",
            raiox_status="parcial_iniciou",
            raiox_ultima_pergunta=7,
            raiox_atualizado_em=agora - timedelta(minutes=45),
            opt_out=False
        )

        # Lead 2: Muito recente (atualizado há 10 min, padrão é 30 min)
        lead_recente = Lead(
            company_id=company.id,
            name="Abandonado Recente",
            phone="42999003344",
            raiox_token="tok-recente",
            raiox_status="parcial_iniciou",
            raiox_ultima_pergunta=3,
            raiox_atualizado_em=agora - timedelta(minutes=10),
            opt_out=False
        )

        # Lead 3: Já recuperado
        lead_recuperado = Lead(
            company_id=company.id,
            name="Abandonado Já Recuperado",
            phone="42999005566",
            raiox_token="tok-recuperado",
            raiox_status="parcial_iniciou",
            raiox_ultima_pergunta=12,
            raiox_atualizado_em=agora - timedelta(minutes=60),
            raiox_recuperacao_em=agora - timedelta(minutes=20),
            opt_out=False
        )

        # Lead 4: Opt-out (não deve vir)
        lead_optout = Lead(
            company_id=company.id,
            name="Abandonado Opt-out",
            phone="42999007788",
            raiox_token="tok-optout",
            raiox_status="parcial_iniciou",
            raiox_ultima_pergunta=4,
            raiox_atualizado_em=agora - timedelta(minutes=50),
            opt_out=True
        )

        db.session.add_all([lead_ok, lead_recente, lead_recuperado, lead_optout])
        db.session.commit()
        lead_ok_id = lead_ok.id
        lead_recente_id = lead_recente.id
        lead_recuperado_id = lead_recuperado.id
        lead_optout_id = lead_optout.id

    # 1. Sem auth -> 401
    resp_no_auth = client.get('/internal/raiox/abandonados')
    assert resp_no_auth.status_code == 401

    # 2. Com auth via X-Internal-API-Key
    headers = {'X-Internal-API-Key': 'test-internal-key'}
    resp = client.get('/internal/raiox/abandonados?minutos=30', headers=headers)
    assert resp.status_code == 200
    data = resp.json
    assert data['success'] is True
    ids = [item['id'] for item in data['leads']]
    assert lead_ok_id in ids
    assert lead_recente_id not in ids
    assert lead_recuperado_id not in ids
    assert lead_optout_id not in ids
    assert "https://crm.northwaycompany.com.br/raiox?retomar=tok-abandonado-1" in data['leads'][0]['url_retomada']


def test_internal_whatsapp_status_endpoint(client, app):
    """Testa registro de status do WhatsApp automático pelo n8n"""
    with app.app_context():
        company = Company.query.first()
        if not company:
            company = Company(name="Test Co")
            db.session.add(company)
            db.session.commit()
        lead = Lead(company_id=company.id, name="Lead WhatsApp Status Test", phone="42999110022")
        db.session.add(lead)
        db.session.commit()
        lead_id = lead.id

    headers = {'X-Internal-API-Key': 'test-internal-key'}
    payload = {
        "lead_id": lead_id,
        "status": "enviado",
        "tipo": "abandono",
        "detalhe": "Disparo Evolution via n8n"
    }

    resp = client.post('/internal/raiox/whatsapp-status', json=payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json.get('success') is True

    with app.app_context():
        l = Lead.query.get(lead_id)
        assert l.raiox_whatsapp_status == "enviado"
        assert l.raiox_recuperacao_em is not None
        assert l.raiox_whatsapp_em is not None

        interaction = Interaction.query.filter_by(lead_id=lead_id).first()
        assert interaction is not None
        assert interaction.type == "whatsapp_auto"
        assert "Tentativa de recuperação de abandono" in interaction.content


def test_opt_out_via_whatsapp_message(client, app):
    """Testa mensagem SAIR no webhook do WhatsApp marcando opt_out=True e gerando interação"""
    phone_raw = "42999887711"
    remote_jid = f"55{phone_raw}@s.whatsapp.net"

    with app.app_context():
        company = Company.query.first() or Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

        instance = WhatsappInstance(instance_name="northway-inst", company_id=company.id, status="connected")
        db.session.add(instance)
        db.session.commit()

        lead = Lead(company_id=company.id, name="Cliente Teste SAIR", phone=phone_raw, opt_out=False)
        db.session.add(lead)
        db.session.commit()
        lead_id = lead.id

    webhook_payload = {
        "event": "messages.upsert",
        "instance": "northway-inst",
        "data": {
            "messages": [{
                "key": {
                    "remoteJid": remote_jid,
                    "fromMe": False,
                    "id": "MSG_OPTOUT_001"
                },
                "pushName": "Cliente Teste",
                "message": {
                    "conversation": "SAIR"
                }
            }]
        }
    }

    with patch('services.evolution_service.EvolutionService.send_text') as mock_reply:
        resp = client.post(
            '/api/webhooks/evolution',
            json=webhook_payload,
            headers={'apikey': 'test-evo-token'}
        )
        assert resp.status_code == 200
        assert mock_reply.called
        # Verifica mensagem de despedida/confirmação
        call_args = mock_reply.call_args[0]
        assert "Você não receberá mais mensagens automáticas da NorthWay" in call_args[2]

    with app.app_context():
        l = Lead.query.get(lead_id)
        assert l.opt_out is True
        interaction = Interaction.query.filter_by(lead_id=lead_id).first()
        assert interaction is not None
        assert "opt-out" in interaction.content
