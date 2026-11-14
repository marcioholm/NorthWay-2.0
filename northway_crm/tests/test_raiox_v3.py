import pytest
from unittest.mock import patch
from sqlalchemy import text
from models import db, Lead, Company


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv('INTERNAL_API_KEY', 'test-internal-key')
    monkeypatch.setenv('CRM_INTERNAL_API_KEY', 'test-internal-key')


def test_raiox_v3_page_renders_pixel_resume_and_short_flow(client):
    resp = client.get('/raiox')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # Meta Pixel events
    assert "2336445306916882" in html
    assert "fbq('track', 'ViewContent')" in html
    assert "RaioXInicio" in html
    assert "RaioXPerguntas" in html

    # Entrada direta na pergunta 1 + 5
    assert "Hoje, onde está a maior dificuldade da sua empresa?" in html
    assert "6 perguntas · 1 minuto · resultado no WhatsApp" in html

    # Retomada localStorage 7 dias
    assert "Continuando de onde você parou" in html
    assert "nw_raiox_v3_progress" in html

    # Dados somente Nome, WhatsApp e Empresa opcional (sem email/faturamento/funcionários)
    assert "Pronto! Para onde enviamos seu resultado?" in html
    assert 'id="fNome"' in html
    assert 'id="fWhats"' in html
    assert 'id="fEmpresa"' in html
    assert 'faturamento_mensal' not in html
    assert 'quantidade_funcionarios' not in html


def test_anonymous_progress_and_funil_abandono_query(client, app):
    with app.app_context():
        company = Company.query.first() or Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

    # Sessão 1 para na p2
    t1 = "sess-anon-1"
    assert client.post('/raiox/progresso', json={"token": t1, "etapa": "abriu"}).status_code == 200
    assert client.post('/raiox/progresso', json={"token": t1, "path": "marketing", "etapa": "inicio"}).status_code == 200
    assert client.post('/raiox/progresso', json={"token": t1, "path": "marketing", "etapa": "p1", "answers": {"1": 2}}).status_code == 200
    assert client.post('/raiox/progresso', json={"token": t1, "path": "marketing", "etapa": "p2", "answers": {"1": 2, "2": 1}}).status_code == 200
    # Não deve regredir se chegar chamada atrasada de p1
    assert client.post('/raiox/progresso', json={"token": t1, "path": "marketing", "etapa": "p1"}).status_code == 200

    # Sessão 2 para em dados (sem telefone)
    t2 = "sess-anon-2"
    assert client.post('/raiox/progresso', json={"token": t2, "path": "gestao", "etapa": "dados"}).status_code == 200

    with app.app_context():
        # Nenhum Lead deve ser criado sem WhatsApp/email
        assert Lead.query.filter(Lead.raiox_token.in_([t1, t2])).count() == 0

        row1 = db.session.execute(
            text("SELECT caminho, etapa_maxima, etapa_ordem FROM raiox_sessions WHERE session_token = :t"),
            {"t": t1},
        ).fetchone()
        assert row1 == ("marketing", "p2", 3)

    resp = client.get('/internal/raiox/funil-abandono?dias=7', headers={'X-Internal-API-Key': 'test-internal-key'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["totais_etapa"]["p2"] >= 1
    assert data["totais_etapa"]["dados"] >= 1
    assert len(data["por_dia"]) >= 1


def test_raiox_v3_submit_marketing_and_geral(client, app):
    with app.app_context():
        company = Company.query.first() or Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

    # 1. Caminho Marketing: soma = 2 + 0 + 3 + 2 + 2 = 9 -> 9/15*10 = 6.0; urgente = Q2 (valor 0)
    tok_mkt = "v3-mkt-token-1"
    with patch('routes.diagnostic_raiox.dispatch_n8n_raiox_webhook') as mock_wh:
        resp = client.post('/raiox/submit', json={
            "version": "v3",
            "token": tok_mkt,
            "path": "marketing",
            "answers": {"1": 2, "2": 0, "3": 3, "4": 2, "7": 2},
            "lead_info": {
                "nome": "Maria Teste",
                "whatsapp": "(42) 99911-2233",
                "empresa": ""
            }
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        res = body["resultado"]
        assert res["nota"] == 6.0
        assert res["nota_formatada"] == "6,0"
        assert res["urgente_id"] == 2
        assert "Google" in res["acao_prioritaria"]
        assert mock_wh.called

    with app.app_context():
        lead = Lead.query.filter_by(raiox_token=tok_mkt).first()
        assert lead is not None
        assert lead.name == "Maria Teste"
        assert lead.raiox_status == "concluido"
        assert lead.indice_maturidade == 6.0
        assert lead.ponto_fraco == 2

        sess = db.session.execute(
            text("SELECT etapa_maxima, lead_id FROM raiox_sessions WHERE session_token = :t"),
            {"t": tok_mkt},
        ).fetchone()
        assert sess == ("concluido", lead.id)

    # 2. Caminho Geral: menor nota em Vender (Q10 = 0)
    tok_ger = "v3-ger-token-2"
    with patch('routes.diagnostic_raiox.dispatch_n8n_raiox_webhook'):
        resp2 = client.post('/raiox/submit', json={
            "version": "v3",
            "token": tok_ger,
            "path": "geral",
            "answers": {"4": 3, "7": 2, "10": 0, "13": 2, "17": 3},
            "lead_info": {
                "nome": "Pedro Geral",
                "whatsapp": "42999001122"
            }
        })
        assert resp2.status_code == 200
        res2 = resp2.get_json()["resultado"]
        assert res2["caminho"] == "geral"
        assert res2["gargalo"] == "vender"
        assert res2["gargalo_nome"] == "Vender"
        assert res2["urgente_id"] == 10
