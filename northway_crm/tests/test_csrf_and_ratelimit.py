import pytest
import re
from datetime import datetime, date
from werkzeug.security import generate_password_hash
from flask_wtf.csrf import generate_csrf
from models import (
    db, Company, User, Lead, Client, Pipeline, PipelineStage,
    ContractTemplate, Task, ROLE_ADMIN
)
from app import create_app

@pytest.fixture
def csrf_app():
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": True,
        "RATELIMIT_ENABLED": True,
        "RATELIMIT_STORAGE_URI": "memory://",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "csrf-test-secret-key-1234567890",
        "WTF_CSRF_TIME_LIMIT": 3600
    })

    with app.app_context():
        db.create_all()
        comp = Company(
            name="Empresa CSRF Teste",
            plan_type="pro",
            payment_status="active",
            subscription_status="active",
            features={"prospecting": True, "whatsapp": True}
        )
        db.session.add(comp)
        db.session.commit()

        user = User(
            email="admin@csrftest.com",
            name="Admin CSRF",
            company_id=comp.id,
            role=ROLE_ADMIN,
            password_hash=generate_password_hash("Secret123!")
        )
        db.session.add(user)
        db.session.commit()

        pipe = Pipeline(company_id=comp.id, name="Funil Vendas")
        db.session.add(pipe)
        db.session.commit()

        stage1 = PipelineStage(company_id=comp.id, pipeline_id=pipe.id, name="Etapa 1", order=1)
        stage2 = PipelineStage(company_id=comp.id, pipeline_id=pipe.id, name="Etapa 2", order=2)
        db.session.add_all([stage1, stage2])
        db.session.commit()

        lead = Lead(
            company_id=comp.id,
            pipeline_id=pipe.id,
            pipeline_stage_id=stage1.id,
            name="Lead Teste CSRF",
            phone="5511999990001",
            source="Manual"
        )
        client_obj = Client(
            company_id=comp.id,
            account_manager_id=user.id,
            name="Cliente Teste CSRF",
            phone="5511988880001",
            email="cliente@csrftest.com"
        )
        template = ContractTemplate(
            company_id=comp.id,
            name="Contrato Padrão CSRF",
            content="# Contrato\n\nNome: {{contratante_nome}}",
            type="contract",
            is_global=False,
            active=True
        )
        task = Task(
            company_id=comp.id,
            title="Tarefa Inicial CSRF",
            assigned_to_id=user.id,
            status="pendente"
        )
        db.session.add_all([lead, client_obj, template, task])
        db.session.commit()

        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()

def extract_token_from_response(resp):
    html = resp.get_data(as_text=True)
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    if not m:
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m is not None, "CSRF token não encontrado na resposta HTML"
    return m.group(1)

def get_client_csrf_token(client, path='/settings/company'):
    resp = client.get(path)
    return extract_token_from_response(resp)

def auth_user(client, csrf_app):
    """Autentica o usuário no cliente de teste com CSRF válido."""
    with csrf_app.app_context():
        # Primeiro obtemos o cookie de sessão via GET
        resp = client.get('/login')
        assert resp.status_code == 200
        token = extract_token_from_response(resp)

        # POST no login com o CSRF token
        login_resp = client.post('/login', data={
            'email': 'admin@csrftest.com',
            'password': 'Secret123!',
            'csrf_token': token
        }, follow_redirects=False)
        assert login_resp.status_code in (302, 200)
        return token


# --- 1. LOGIN ---
def test_csrf_login_flow(csrf_client, csrf_app):
    """Testa login rejeitado sem CSRF e aceito com CSRF válido."""
    # 1. Sem CSRF -> Rejeitado (400)
    resp_no_csrf = csrf_client.post('/login', data={
        'email': 'admin@csrftest.com',
        'password': 'Secret123!'
    })
    assert resp_no_csrf.status_code == 400

    # 2. Com CSRF -> Sucesso (302 redirect para dashboard)
    resp_get = csrf_client.get('/login')
    token = extract_token_from_response(resp_get)

    resp_csrf = csrf_client.post('/login', data={
        'email': 'admin@csrftest.com',
        'password': 'Secret123!',
        'csrf_token': token
    }, follow_redirects=False)
    assert resp_csrf.status_code == 302


# --- 2. CRIAR LEAD ---
def test_csrf_create_lead_flow(csrf_client, csrf_app):
    """Testa criação de lead rejeitada sem CSRF e aceita com CSRF válido."""
    auth_user(csrf_client, csrf_app)

    # 1. POST sem token CSRF -> 400
    resp_no_csrf = csrf_client.post('/leads', data={
        'name': 'Novo Lead Sem CSRF',
        'phone': '5511977770001',
        'source': 'Site'
    })
    assert resp_no_csrf.status_code == 400

    # 2. POST com token CSRF válido -> 302 (criado)
    valid_token = get_client_csrf_token(csrf_client, '/leads')
    resp_csrf = csrf_client.post('/leads', data={
        'name': 'Novo Lead Com CSRF',
        'phone': '5511977770002',
        'source': 'Site',
        'csrf_token': valid_token
    }, follow_redirects=False)
    assert resp_csrf.status_code == 302

    with csrf_app.app_context():
        created = Lead.query.filter_by(name='Novo Lead Com CSRF').first()
        assert created is not None


# --- 3. MOVER CARD NO PIPELINE ---
def test_csrf_move_pipeline_card_flow(csrf_client, csrf_app):
    """Testa movimentação de card no kanban (AJAX JSON) rejeitada sem header CSRF e aceita com X-CSRFToken."""
    auth_user(csrf_client, csrf_app)

    with csrf_app.app_context():
        lead = Lead.query.filter_by(name="Lead Teste CSRF").first()
        stage2 = PipelineStage.query.filter_by(name="Etapa 2").first()
        lead_id = lead.id
        stage2_id = stage2.id

    # 1. POST JSON sem header CSRF -> 400
    resp_no_csrf = csrf_client.post(
        f'/api/leads/{lead_id}/update_stage',
        json={'stage_id': stage2_id}
    )
    assert resp_no_csrf.status_code == 400

    # 2. POST JSON com X-CSRFToken -> 200
    valid_token = get_client_csrf_token(csrf_client, '/pipeline')
    resp_csrf = csrf_client.post(
        f'/api/leads/{lead_id}/update_stage',
        json={'stage_id': stage2_id},
        headers={'X-CSRFToken': valid_token}
    )
    assert resp_csrf.status_code == 200

    with csrf_app.app_context():
        lead_updated = Lead.query.get(lead_id)
        assert lead_updated.pipeline_stage_id == stage2_id


# --- 4. SALVAR TAREFA ---
def test_csrf_save_task_flow(csrf_client, csrf_app):
    """Testa salvar tarefa rejeitada sem CSRF e aceita com CSRF válido."""
    auth_user(csrf_client, csrf_app)

    # 1. POST sem CSRF -> 400
    resp_no_csrf = csrf_client.post('/tasks', data={
        'title': 'Tarefa Invasora'
    })
    assert resp_no_csrf.status_code == 400

    # 2. POST com CSRF válido -> 302
    valid_token = get_client_csrf_token(csrf_client, '/tasks')
    resp_csrf = csrf_client.post('/tasks', data={
        'title': 'Tarefa Legítima com CSRF',
        'csrf_token': valid_token
    }, follow_redirects=False)
    assert resp_csrf.status_code in (200, 302)

    with csrf_app.app_context():
        task = Task.query.filter_by(title='Tarefa Legítima com CSRF').first()
        assert task is not None


# --- 5. SALVAR CONFIGURAÇÕES DA EMPRESA ---
def test_csrf_save_company_settings_flow(csrf_client, csrf_app):
    """Testa salvar configurações da empresa rejeitada sem CSRF e aceita com CSRF válido."""
    auth_user(csrf_client, csrf_app)

    # 1. POST sem CSRF -> 400
    resp_no_csrf = csrf_client.post('/settings/company', data={
        'name': 'Nome Inválido'
    })
    assert resp_no_csrf.status_code == 400

    # 2. POST com CSRF válido -> 302
    valid_token = get_client_csrf_token(csrf_client, '/settings/company')
    resp_csrf = csrf_client.post('/settings/company', data={
        'name': 'Empresa Nome Atualizado',
        'document': '12.345.678/0001-99',
        'csrf_token': valid_token
    }, follow_redirects=False)
    assert resp_csrf.status_code in (200, 302)

    with csrf_app.app_context():
        comp = Company.query.filter_by(name='Empresa Nome Atualizado').first()
        assert comp is not None


# --- 6. GERAR CONTRATO ---
def test_csrf_generate_contract_flow(csrf_client, csrf_app):
    """Testa emissão de contrato rejeitada sem CSRF e aceita com CSRF válido."""
    auth_user(csrf_client, csrf_app)

    with csrf_app.app_context():
        client_obj = Client.query.filter_by(name="Cliente Teste CSRF").first()
        tmpl = ContractTemplate.query.filter_by(name="Contrato Padrão CSRF").first()
        client_id = client_obj.id
        tmpl_id = tmpl.id

    # 1. POST sem CSRF -> 400
    resp_no_csrf = csrf_client.post(f'/clients/{client_id}/contracts', data={
        'template_id': tmpl_id,
        'contratante_nome': 'Cliente Teste'
    })
    assert resp_no_csrf.status_code == 400

    # 2. POST com CSRF válido -> aceito
    valid_token = get_client_csrf_token(csrf_client, f'/clients/{client_id}')
    resp_csrf = csrf_client.post(f'/clients/{client_id}/contracts', data={
        'template_id': tmpl_id,
        'contratante_nome': 'Cliente Teste',
        'contratante_documento': '111.222.333-44',
        'valor_mensal': '1500',
        'csrf_token': valid_token
    }, follow_redirects=False)
    assert resp_csrf.status_code in (200, 302)


# --- 7. RATE LIMITING ---
def test_rate_limiting_login_endpoint(csrf_client, csrf_app):
    """Testa se o endpoint de login bloqueia requisições em excesso (429 Too Many Requests)."""
    # Obtém token inicial e sessão para /login
    resp_get = csrf_client.get('/login')
    token = extract_token_from_response(resp_get)

    hit_429 = False
    for i in range(15):
        resp = csrf_client.post('/login', data={
            'email': f'bruteforce_{i}@teste.com',
            'password': 'wrongpassword',
            'csrf_token': token
        })
        if resp.status_code == 429:
            hit_429 = True
            break

    assert hit_429, "Rate limiter não disparou 429 após exceder 10 requisições por minuto no login"


def test_rate_limiting_api_extension_login(csrf_client, csrf_app):
    """Testa rate limiting na rota de login da extensão Chrome (/api/ext/login)."""
    hit_429 = False
    for i in range(15):
        resp = csrf_client.post('/api/ext/login', json={
            'email': f'bruteforce_ext_{i}@teste.com',
            'password': 'wrongpassword'
        })
        if resp.status_code == 429:
            hit_429 = True
            break

    assert hit_429, "Rate limiter não disparou 429 após exceder 10 requisições por minuto em /api/ext/login"

