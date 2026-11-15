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


def test_raiox_completo_requires_login(client):
    resp = client.get('/raiox/completo/1')
    assert resp.status_code in (302, 401)


def test_raiox_v3_pdf_and_internal_completo_flow(client, auth_client, app):
    from routes.diagnostic_raiox import generate_raiox_v3_pdf_bytes

    authed, user, company = auth_client

    # 1. PDF v3 gera bytes válidos
    pdf_bytes = generate_raiox_v3_pdf_bytes(
        nome="Lucas Teste",
        empresa="Empresa Teste",
        resultado={
            "caminho": "marketing",
            "area_nome": "Marketing",
            "nota": 5.3,
            "nota_formatada": "5,3",
            "urgente_id": 2,
            "urgente_curto": "Presença no Google",
            "urgente_valor": 0,
            "acao_prioritaria": "Atualize o Google Perfil.",
            "detalhes": [
                {"id": 1, "curto": "Cliente ideal", "area": "Atrair", "valor": 2, "resposta": "Sei bem"},
                {"id": 2, "curto": "Presença no Google", "area": "Atrair", "valor": 0, "resposta": "Não aparece"},
            ],
        },
        whatsapp_url="https://wa.me/5542999896358",
    )
    assert pdf_bytes.startswith(b"%PDF-")

    user_id = user.id
    company_id = company.id

    # 2. Cria lead via submit v3 e verifica pdf_url no retorno e no webhook n8n
    tok = "v3-completo-tok"
    with patch('routes.diagnostic_raiox.dispatch_n8n_raiox_webhook') as mock_wh_sub:
        r_sub = client.post('/raiox/submit', json={
            "version": "v3",
            "token": tok,
            "path": "marketing",
            "answers": {"1": 2, "2": 0, "3": 1, "4": 3, "7": 2},
            "lead_info": {"nome": "Lead Completo", "whatsapp": "42999887755"}
        })
        assert r_sub.status_code == 200
        sub_json = r_sub.get_json()
        assert sub_json["resultado"]["pdf_url"] == f"/raiox/pdf/{tok}"
        assert mock_wh_sub.called
        wh_payload = mock_wh_sub.call_args[0][1]
        assert wh_payload["pdf_url"].endswith(f"/raiox/pdf/{tok}")

    # 2b. Rota pública /raiox/pdf/<token> (válido -> PDF, inválido -> 404)
    assert client.get('/raiox/pdf/token-inexistente-999').status_code == 404
    r_pub_pdf = client.get(f'/raiox/pdf/{tok}')
    assert r_pub_pdf.status_code == 200
    assert r_pub_pdf.mimetype == 'application/pdf'
    assert r_pub_pdf.data.startswith(b"%PDF-")

    with app.app_context():
        lead = Lead.query.filter_by(raiox_token=tok).first()
        lead.company_id = company_id
        db.session.commit()
        lead_id = lead.id
        orig_respostas = lead.respostas
        orig_indice = lead.indice_maturidade

    # 3b. Antes do completo: /raiox/report/<id> mostra resultado v3 (sem calcular v2 incompleto) e /pdf gera PDF v3
    r_rep_init = authed.get(f'/raiox/report/{lead_id}')
    assert r_rep_init.status_code == 200
    rep_init_html = r_rep_init.data.decode('utf-8')
    assert "Raio-X Inicial (1 + 5 Perguntas)" in rep_init_html
    assert "Fazer diagnóstico completo" in rep_init_html
    r_pdf_init = authed.get(f'/raiox/report/{lead_id}/pdf')
    assert r_pdf_init.status_code == 200
    assert r_pdf_init.mimetype == 'application/pdf'
    assert r_pdf_init.data.startswith(b"%PDF-")

    # 4. Logado acessa pré-preenchido e salva completo sem sobrescrever inicial nem disparar webhook
    resp_get = authed.get(f'/raiox/completo/{lead_id}')
    assert resp_get.status_code == 200
    html = resp_get.data.decode('utf-8')
    assert "Diagnóstico Completo (20 perguntas)" in html
    assert "Respondido no inicial" in html

    answers_20 = {str(i): (i % 4) for i in range(1, 21)}
    with patch('routes.diagnostic_raiox.dispatch_n8n_raiox_webhook') as mock_wh:
        resp_post = authed.post(f'/raiox/completo/{lead_id}', json={"answers": answers_20})
        assert resp_post.status_code == 200
        assert not mock_wh.called

    with app.app_context():
        lead_after = db.session.get(Lead, lead_id)
        assert lead_after.raiox_completo_em is not None
        assert lead_after.raiox_completo_por == user_id
        assert len(lead_after.raiox_completo_respostas) == 20
        # Inicial v3 preservado
        assert lead_after.respostas == orig_respostas
        assert lead_after.indice_maturidade == orig_indice

    # 5. Relatório completo e PDF de 5 eixos
    resp_rep = authed.get(f'/raiox/report/{lead_id}?tipo=completo')
    assert resp_rep.status_code == 200
    assert "Raio-X de Maturidade Comercial (5 Eixos)" in resp_rep.data.decode('utf-8')

    resp_pdf = authed.get(f'/raiox/report/{lead_id}/pdf')
    assert resp_pdf.status_code == 200
    assert resp_pdf.mimetype == 'application/pdf'
    assert resp_pdf.data.startswith(b"%PDF-")


def test_raiox_cross_company_isolation_and_csrf(auth_client, app):
    import re
    authed, user, company = auth_client

    with app.app_context():
        other_company = Company(name="Outra Empresa", plan_type="monthly", payment_status="active", subscription_status="active")
        db.session.add(other_company)
        db.session.commit()

        other_lead = Lead(
            company_id=other_company.id,
            name="Lead Outra Empresa",
            phone="42999123456",
            raiox_token="other-co-tok",
            raiox_status="concluido",
            respostas={"version": "v3", "path": "marketing", "answers": {"1": 1, "2": 1, "3": 1, "4": 1, "7": 1}},
        )
        own_lead = Lead(
            company_id=company.id,
            name="Lead Propria Empresa",
            phone="42999654321",
            raiox_token="own-co-tok",
            raiox_status="concluido",
            respostas={"version": "v3", "path": "marketing", "answers": {"1": 2, "2": 2, "3": 2, "4": 2, "7": 2}},
        )
        db.session.add_all([other_lead, own_lead])
        db.session.commit()
        other_id = other_lead.id
        own_id = own_lead.id

    # Acesso entre empresas deve retornar 404 em todas as rotas internas
    assert authed.get(f'/raiox/completo/{other_id}').status_code == 404
    assert authed.post(f'/raiox/completo/{other_id}', json={"answers": {str(i): 1 for i in range(1, 21)}}).status_code == 404
    assert authed.get(f'/raiox/report/{other_id}').status_code == 404
    assert authed.get(f'/raiox/report/{other_id}/pdf').status_code == 404

    # Proteção CSRF ativa no POST /raiox/completo/<lead_id>
    prev_csrf = app.config.get('WTF_CSRF_ENABLED', False)
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        r_no_csrf = authed.post(f'/raiox/completo/{own_id}', json={"answers": {str(i): 2 for i in range(1, 21)}})
        assert r_no_csrf.status_code == 400

        r_form = authed.get(f'/raiox/completo/{own_id}')
        assert r_form.status_code == 200
        m = re.search(r'name="csrf_token" value="([^"]+)"', r_form.data.decode('utf-8'))
        assert m is not None
        csrf_tok = m.group(1)

        r_with_csrf = authed.post(
            f'/raiox/completo/{own_id}',
            json={"answers": {str(i): 2 for i in range(1, 21)}},
            headers={"X-CSRFToken": csrf_tok},
        )
        assert r_with_csrf.status_code == 200
    finally:
        app.config['WTF_CSRF_ENABLED'] = prev_csrf

