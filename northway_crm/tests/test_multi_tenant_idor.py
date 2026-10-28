import pytest
from datetime import date
from models import (
    db, Company, User, Lead, Client, Pipeline, PipelineStage,
    ContractTemplate, Task, ROLE_ADMIN, ROLE_SALES
)

@pytest.fixture
def two_tenants(app):
    """Cria duas empresas distintas (A e B) com usuários e recursos para teste de isolamento IDOR."""
    with app.app_context():
        from models import WhatsappInstance
        comp_a = Company(name="Empresa A", plan_type="pro", payment_status="active", subscription_status="active", features={"whatsapp": True})
        comp_b = Company(name="Empresa B", plan_type="pro", payment_status="active", subscription_status="active", features={"whatsapp": True})
        db.session.add_all([comp_a, comp_b])
        db.session.commit()

        inst_a = WhatsappInstance(company_id=comp_a.id, instance_name="inst-a", status="connected")
        db.session.add(inst_a)
        db.session.commit()

        user_a = User(
            email="user_a@empresa-a.com",
            name="User A",
            company_id=comp_a.id,
            role=ROLE_ADMIN,
            password_hash="mocked"
        )
        user_b = User(
            email="user_b@empresa-b.com",
            name="User B",
            company_id=comp_b.id,
            role=ROLE_ADMIN,
            password_hash="mocked"
        )
        db.session.add_all([user_a, user_b])
        db.session.commit()

        # Recursos da Empresa B
        pipe_b = Pipeline(company_id=comp_b.id, name="Funil B")
        db.session.add(pipe_b)
        db.session.commit()

        stage_b = PipelineStage(company_id=comp_b.id, pipeline_id=pipe_b.id, name="Etapa Confidencial B", order=1)
        db.session.add(stage_b)
        db.session.commit()

        lead_b = Lead(
            company_id=comp_b.id,
            pipeline_id=pipe_b.id,
            pipeline_stage_id=stage_b.id,
            name="Lead Confidencial B",
            email="lead_b@alvo.com",
            phone="5511999998888",
            source="Raio-X Digital",
            diagnostic_status="done",
            diagnostic_score=85.0
        )
        client_b = Client(
            company_id=comp_b.id,
            account_manager_id=user_b.id,
            name="Cliente B",
            phone="5511988887777",
            email_contact="client_b@empresa.com"
        )
        template_b = ContractTemplate(
            company_id=comp_b.id,
            name="Contrato Confidencial Empresa B",
            content="# Minuta Confidencial B\n\nNome: {{contratante_nome}}",
            type="contract",
            is_global=False,
            active=True
        )
        task_b = Task(
            company_id=comp_b.id,
            title="Tarefa Confidencial Empresa B",
            status="a_fazer"
        )
        db.session.add_all([lead_b, client_b, template_b, task_b])
        db.session.commit()

        # Recursos da Empresa A
        pipe_a = Pipeline(company_id=comp_a.id, name="Funil A")
        db.session.add(pipe_a)
        db.session.commit()

        stage_a = PipelineStage(company_id=comp_a.id, pipeline_id=pipe_a.id, name="Etapa Inicial A", order=1)
        db.session.add(stage_a)
        db.session.commit()

        lead_a = Lead(
            company_id=comp_a.id,
            pipeline_id=pipe_a.id,
            pipeline_stage_id=stage_a.id,
            name="Lead A",
            phone="5511911112222"
        )
        client_a = Client(
            company_id=comp_a.id,
            account_manager_id=user_a.id,
            name="Cliente A",
            phone="5511922223333"
        )
        db.session.add_all([lead_a, client_a])
        db.session.commit()

        data = {
            'comp_a_id': comp_a.id,
            'comp_b_id': comp_b.id,
            'user_a_id': user_a.id,
            'lead_a_id': lead_a.id,
            'client_a_id': client_a.id,
            'stage_a_id': stage_a.id,
            'lead_b_id': lead_b.id,
            'client_b_id': client_b.id,
            'stage_b_id': stage_b.id,
            'template_b_id': template_b.id,
            'task_b_id': task_b.id,
        }
        return data

def auth_as_user_a(client, two_tenants):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(two_tenants['user_a_id'])
        sess['_fresh'] = True

def test_diagnostic_raiox_report_cross_tenant_returns_404(client, two_tenants):
    """Usuário da Empresa A acessando relatório do Raio-X de lead da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.get(f'/raiox/report/{two_tenants["lead_b_id"]}')
    assert resp.status_code == 404

def test_diagnostic_raiox_delete_cross_tenant_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando deletar diagnóstico de lead da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.post(f'/raiox/{two_tenants["lead_b_id"]}/delete')
    assert resp.status_code == 404

def test_whatsapp_sync_profile_cross_tenant_returns_404(client, two_tenants):
    """Usuário da Empresa A chamando sync-profile com lead ou client da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp_lead = client.post('/api/whatsapp/sync-profile', json={'type': 'lead', 'id': str(two_tenants['lead_b_id'])})
    assert resp_lead.status_code == 404

    resp_client = client.post('/api/whatsapp/sync-profile', json={'type': 'client', 'id': str(two_tenants['client_b_id'])})
    assert resp_client.status_code == 404

def test_whatsapp_send_msg_cross_tenant_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando enviar WhatsApp para lead da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.post('/api/whatsapp/send', json={'lead_id': two_tenants['lead_b_id'], 'content': 'Tentativa IDOR'})
    assert resp.status_code == 404

def test_whatsapp_send_media_cross_tenant_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando enviar mídia para lead da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    import io
    data = {
        'lead_id': str(two_tenants['lead_b_id']),
        'file': (io.BytesIO(b'dummy content'), 'test.jpg')
    }
    resp = client.post('/api/whatsapp/send-media', data=data, content_type='multipart/form-data')
    assert resp.status_code == 404

def test_leads_update_stage_with_foreign_stage_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando mover lead para estágio da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.post(
        f'/api/leads/{two_tenants["lead_a_id"]}/update_stage',
        json={'stage_id': two_tenants['stage_b_id']}
    )
    assert resp.status_code in (404, 400)

def test_leads_export_with_foreign_stage_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando filtrar exportação com estágio da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.get(f'/leads/export?stage_id={two_tenants["stage_b_id"]}')
    assert resp.status_code == 404

def test_contracts_create_with_foreign_template_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando emitir contrato com template confidencial da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.post(
        f'/clients/{two_tenants["client_a_id"]}/contracts',
        data={'template_id': str(two_tenants['template_b_id']), 'action': 'issue'}
    )
    assert resp.status_code == 404

def test_client_details_cross_tenant_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando acessar detalhes do cliente da Empresa B deve receber 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.get(f'/clients/{two_tenants["client_b_id"]}')
    assert resp.status_code == 404

def test_lead_details_cross_tenant_returns_404(client, two_tenants):
    """Usuário da Empresa A tentando acessar detalhes do lead da Empresa B deve receber 403 ou 404."""
    auth_as_user_a(client, two_tenants)
    resp = client.get(f'/leads/{two_tenants["lead_b_id"]}')
    assert resp.status_code in (403, 404)

