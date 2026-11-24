import pytest
from models import db, Lead, Company, Pipeline, PipelineStage, Interaction, User


@pytest.fixture(autouse=True)
def setup_internal_key(monkeypatch):
    monkeypatch.setenv('INTERNAL_API_KEY', 'test-internal-key')
    monkeypatch.setenv('CRM_INTERNAL_API_KEY', 'test-internal-key')


def _seed_tenant(app):
    with app.app_context():
        company = Company(name="NorthWay Solar")
        db.session.add(company)
        db.session.flush()

        pipeline = Pipeline(name="Funil Comercial", company_id=company.id)
        db.session.add(pipeline)
        db.session.flush()

        s1 = PipelineStage(name="Novo", order=1, pipeline_id=pipeline.id, company_id=company.id)
        s2 = PipelineStage(name="Qualificação", order=2, pipeline_id=pipeline.id, company_id=company.id)
        db.session.add_all([s1, s2])
        db.session.flush()

        user = User(name="Vendedor", email="vend@test.com", password_hash="hash", company_id=company.id)
        db.session.add(user)
        db.session.commit()
        return company.id, pipeline.id, s1.id, s2.id, user.id


def test_landing_requires_internal_auth(client):
    resp = client.post('/internal/leads/landing', json={'tenant_id': 1, 'origem': 'lp-payback', 'lp_lead_id': 'abc'})
    assert resp.status_code in (401, 403)

    resp_bad = client.post(
        '/internal/leads/landing',
        headers={'X-Internal-API-Key': 'wrong-key'},
        json={'tenant_id': 1, 'origem': 'lp-payback', 'lp_lead_id': 'abc', 'email': 'a@b.com'},
    )
    assert resp_bad.status_code in (401, 403)


def test_landing_validation_400(client, app):
    cid, _, _, _, _ = _seed_tenant(app)
    headers = {'X-Internal-API-Key': 'test-internal-key'}

    # Missing lp_lead_id
    r1 = client.post('/internal/leads/landing', headers=headers, json={'tenant_id': cid, 'origem': 'lp-payback', 'email': 'a@b.com'})
    assert r1.status_code == 400

    # Missing whatsapp and email
    r2 = client.post('/internal/leads/landing', headers=headers, json={'tenant_id': cid, 'origem': 'lp-payback', 'lp_lead_id': 'lp-1'})
    assert r2.status_code == 400


def test_landing_create_and_update_by_lp_lead_id(client, app):
    cid, pid, s1_id, s2_id, uid = _seed_tenant(app)
    headers = {'Authorization': 'Bearer test-internal-key'}

    # 1. Primeira chamada cria o lead
    resp1 = client.post('/internal/leads/landing', headers=headers, json={
        'tenant_id': cid,
        'origem': 'lp-payback',
        'lp_lead_id': 'visitor-001',
        'status_lp': 'completo',
        'nome': 'João Solar',
        'whatsapp': '5542999887766',
        'email': 'joao@solar.com.br',
        'empresa': 'Solar Sul',
        'cidade': 'Ponta Grossa/PR',
        'faturamento': 'R$ 100 a 300 mil',
        'desafio': 'Precificação e margem',
        'bonus': 'ebook',
        'utm_source': 'meta',
        'utm_campaign': 'payback_q4',
    })
    assert resp1.status_code == 200
    data1 = resp1.get_json()
    assert data1['success'] is True
    assert data1['created'] is True
    lead_id = data1['lead_id']

    with app.app_context():
        lead = db.session.get(Lead, lead_id)
        assert lead is not None
        assert lead.source == 'lp-payback'
        assert lead.lp_lead_id == 'visitor-001'
        assert lead.pipeline_id == pid
        assert lead.pipeline_stage_id == s1_id
        assert lead.faixa_faturamento == 'R$ 100 a 300 mil'
        assert lead.lp_desafio == 'Precificação e margem'
        assert Interaction.query.filter_by(lead_id=lead.id, type='landing_page').count() == 1

        # Move lead to stage 2 and assign user
        lead.pipeline_stage_id = s2_id
        lead.assigned_to_id = uid
        db.session.commit()

    # 2. Segunda chamada com mesmo lp_lead_id atualiza sem duplicar, sem apagar campos vazios e sem mudar etapa
    resp2 = client.post('/internal/leads/landing', headers=headers, json={
        'tenant_id': cid,
        'origem': 'lp-payback',
        'lp_lead_id': 'visitor-001',
        'status_lp': 'calculadora',
        'nome': '',
        'whatsapp': '5542999887766',
        'email': '',
        'bonus': 'calculadora',
        'calculadora': {
            'passo': 4,
            'verba_segura': 4500,
            'cac_seguro': 350,
            'situacao': 'Pronto para escalar',
        },
    })
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2['success'] is True
    assert data2['created'] is False
    assert data2['lead_id'] == lead_id

    with app.app_context():
        assert Lead.query.filter_by(company_id=cid).count() == 1
        lead = db.session.get(Lead, lead_id)
        assert lead.name == 'João Solar'
        assert lead.email == 'joao@solar.com.br'
        assert lead.pipeline_stage_id == s2_id
        assert lead.assigned_to_id == uid
        assert lead.lp_status == 'calculadora'
        assert lead.lp_calculadora['verba_segura'] == 4500
        # 1 interaction for 'completo' + 1 for 'calculadora'
        assert Interaction.query.filter_by(lead_id=lead.id, type='landing_page').count() == 2

    # 3. Reenvio com mesmo status_lp ('calculadora') atualiza a interaction existente em vez de duplicar
    resp3 = client.post('/internal/leads/landing', headers=headers, json={
        'tenant_id': cid,
        'origem': 'lp-payback',
        'lp_lead_id': 'visitor-001',
        'status_lp': 'calculadora',
        'whatsapp': '5542999887766',
        'calculadora': {'passo': 5, 'verba_segura': 6000, 'cac_seguro': 400, 'situacao': 'Escala'},
    })
    assert resp3.status_code == 200
    with app.app_context():
        interactions = Interaction.query.filter_by(lead_id=lead_id, type='landing_page').all()
        assert len(interactions) == 2
        assert any('6000' in i.content for i in interactions)


def test_landing_matches_existing_lead_by_whatsapp_variants_and_preserves_source(client, app):
    cid, pid, s1_id, s2_id, uid = _seed_tenant(app)
    with app.app_context():
        existing = Lead(
            company_id=cid,
            name="Maria Integradora",
            phone="(42) 99989-6358",
            source="Prospecção",
            pipeline_id=pid,
            pipeline_stage_id=s2_id,
            assigned_to_id=uid,
            opt_out=True,
        )
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

    headers = {'X-Internal-API-Key': 'test-internal-key'}
    resp = client.post('/internal/leads/landing', headers=headers, json={
        'tenant_id': cid,
        'origem': 'lp-payback',
        'lp_lead_id': 'visitor-wa-match',
        'status_lp': 'completo',
        'whatsapp': '5542999896358',
        'email': 'maria@integradora.com',
        'faturamento': 'Acima de R$ 300 mil',
        'desafio': 'Fechar mais propostas',
        'bonus': 'ebook',
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['created'] is False
    assert body['lead_id'] == existing_id

    with app.app_context():
        lead = db.session.get(Lead, existing_id)
        assert lead.lp_lead_id == 'visitor-wa-match'
        assert lead.source == 'Prospecção'  # Preserva origem original
        assert lead.pipeline_stage_id == s2_id  # Etapa não muda
        assert lead.assigned_to_id == uid
        assert lead.opt_out is True
        assert Interaction.query.filter_by(lead_id=existing_id, type='landing_page').count() == 1
