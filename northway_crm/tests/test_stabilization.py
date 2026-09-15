from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
from flask import template_rendered, g
from sqlalchemy import event
from models import (db, Company, User, Lead, Client, Task, Pipeline, PipelineStage,
                    Interaction, WhatsappInstance, WhatsappConversation, WhatsappMessage,
                    IntegrationWebhook, WebhookDelivery, get_now_br)


def other_tenant():
    company = Company(name='Other company', payment_status='active', features={'whatsapp': True})
    db.session.add(company)
    db.session.flush()
    user = User(name='Other user', email='other@example.test', password_hash='test',
                company_id=company.id, role='admin')
    db.session.add(user)
    db.session.commit()
    return company, user


def test_anonymous_routes_and_removed_maintenance(client):
    assert client.get('/home').status_code == 302
    assert client.get('/not-a-real-page').status_code == 404
    for path in ['/debug_test_template', '/sys-admin/sync-db', '/master/migrate-integrations', '/master/migrate-campaign-stats']:
        assert client.get(path).status_code == 404
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_api_never_publicly_cached(auth_client):
    client, _, _ = auth_client
    response = client.get('/api/clients/search?q=Test')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'private, no-store'


def test_cross_tenant_lead_and_tasks_denied(auth_client):
    client, _, company = auth_client
    other, user = other_tenant()
    lead = Lead(name='Private', company_id=other.id, source='Raio-X Digital')
    db.session.add(lead)
    db.session.commit()
    assert client.get(f'/leads/{lead.id}').status_code == 403
    assert client.get(f'/tasks/api/kanban?user_id={user.id}').status_code == 404


def test_task_service_always_scopes_company(auth_client):
    _, user, company = auth_client
    other, _ = other_tenant()
    # Even inconsistent legacy ownership cannot bypass the company filter.
    db.session.add(Task(title='Private task', company_id=other.id, assigned_to_id=user.id))
    db.session.commit()
    from services.task_service import TaskService
    result = TaskService.get_kanban_tasks(user.id, company.id)
    assert not any(result.values())


def test_conversion_is_repeatable(auth_client):
    client, user, company = auth_client
    lead = Lead(name='Convert once', company_id=company.id, assigned_to_id=user.id)
    db.session.add(lead)
    db.session.commit()
    with patch('routes.leads.IntegrationsService.dispatch_webhooks'):
        first = client.post(f'/leads/{lead.id}/convert', data={'monthly_value': '1.200,00'})
        second = client.post(f'/leads/{lead.id}/convert', data={'monthly_value': '1.200,00'})
    assert first.status_code == second.status_code == 302
    assert first.location == second.location
    assert Client.query.filter_by(lead_id=lead.id).count() == 1
    assert Task.query.filter_by(client_id=Client.query.filter_by(lead_id=lead.id).one().id).count() == 1


@pytest.mark.parametrize('period', ['today', 'daily', 'weekly', 'monthly', 'bimonthly', 'quarterly', 'semiannual', 'annual', 'all_time'])
def test_chart_periods_aggregate_without_dialect_errors(auth_client, period):
    client, user, company = auth_client
    db.session.add(Lead(name='Count me', company_id=company.id, created_at=get_now_br()))
    db.session.add(Client(name='Count client', company_id=company.id, account_manager_id=user.id, start_date=get_now_br().date()))
    db.session.commit()
    response = client.get(f'/api/dashboard/chart-data?period={period}')
    assert response.status_code == 200
    assert sum(response.json['data']['leads']) == 1
    assert sum(response.json['data']['sales']) == 1


def test_calendar_bucket_boundaries():
    from services.chart_service import bucket_key
    assert bucket_key(datetime(2026, 3, 31), 'quarterly')[0] == '2026-01'
    assert bucket_key(datetime(2026, 4, 1), 'quarterly')[0] == '2026-04'
    assert bucket_key(datetime(2026, 1, 1), 'weekly')[0] == '2025-12-29'


def test_today_includes_later_tasks(auth_client):
    _, user, company = auth_client
    from routes.dashboard import get_today_tasks
    now = datetime.now()
    task = Task(title='Later today', company_id=company.id, assigned_to_id=user.id,
                status='pendente', due_date=now.replace(hour=23, minute=59, second=59))
    db.session.add(task)
    db.session.commit()
    assert task.id in [t.id for t in get_today_tasks(company.id, user.id)]


def test_clients_list_does_not_write_or_query_per_client(auth_client, app):
    client, user, company = auth_client
    for n in range(30):
        db.session.add(Client(name=f'Customer {n}', company_id=company.id, account_manager_id=user.id, health_status='verde'))
    db.session.commit()
    statements = []
    def record(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(db.engine, 'before_cursor_execute', record)
    try:
        response = client.get('/clients')
    finally:
        event.remove(db.engine, 'before_cursor_execute', record)
    assert response.status_code == 200
    assert not any(s.lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for s in statements)
    assert len([s for s in statements if 'max(interaction.created_at)' in s]) == 1
    assert Client.query.filter_by(health_status='verde').count() == 30


def test_pipeline_pages_keep_full_totals(auth_client, app):
    client, user, company = auth_client
    pipeline = Pipeline(name='Sales', company_id=company.id)
    db.session.add(pipeline)
    db.session.flush()
    stage = PipelineStage(name='New', pipeline_id=pipeline.id, company_id=company.id, order=0)
    db.session.add(stage)
    db.session.flush()
    for n in range(63):
        db.session.add(Lead(name=f'Lead {n}', company_id=company.id, pipeline_id=pipeline.id,
                            pipeline_stage_id=stage.id, assigned_to_id=user.id, estimated_value=10))
    db.session.commit()
    contexts = []
    def capture(sender, template, context, **extra):
        contexts.append(context)
    template_rendered.connect(capture, app)
    try:
        assert client.get(f'/pipeline/{pipeline.id}').status_code == 200
        first = contexts[-1]
        assert len(first['leads_by_stage'][stage.id]) == 50
        assert first['stage_counts'][stage.id] == 63
        assert first['stage_totals'][stage.id] == 630
        assert client.get(f'/pipeline/{pipeline.id}?page_{stage.id}=2').status_code == 200
        assert len(contexts[-1]['leads_by_stage'][stage.id]) == 13
    finally:
        template_rendered.disconnect(capture, app)


def test_whatsapp_history_cursors_and_isolation(auth_client):
    client, user, company = auth_client
    instance = WhatsappInstance(company_id=company.id, instance_name='test')
    db.session.add(instance)
    db.session.flush()
    lead = Lead(name='Chat', company_id=company.id, phone='5511999999999')
    db.session.add(lead)
    db.session.flush()
    conv = WhatsappConversation(company_id=company.id, instance_id=instance.id,
                                remote_jid='5511999999999@s.whatsapp.net', lead_id=lead.id)
    db.session.add(conv)
    db.session.flush()
    for n in range(65):
        db.session.add(WhatsappMessage(company_id=company.id, conversation_id=conv.id, message_id=f'm{n}', content=str(n), direction='in'))
    db.session.commit()
    url = f'/api/whatsapp/lead/{lead.id}/messages'
    data = client.get(url).json
    assert len(data['messages']) == 50 and data['has_more']
    older = client.get(f"{url}?before_id={data['oldest_id']}").json
    assert len(older['messages']) == 15 and not older['has_more']
    assert not client.get(f"{url}?after_id={data['latest_id']}").json['messages']
    db.session.add(WhatsappMessage(company_id=company.id, conversation_id=conv.id, message_id='new', content='new', direction='in'))
    db.session.commit()
    assert len(client.get(f"{url}?after_id={data['latest_id']}").json['messages']) == 1
    other, other_user = other_tenant()
    with client.session_transaction() as session:
        session['_user_id'] = str(other_user.id)
    # The fixture holds an app context across requests; reset Flask-Login's cache.
    g.pop('_login_user', None)
    assert client.get(url).status_code == 403


def test_cron_requires_secret(client, app):
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/api/cron/'):
            assert client.get(rule.rule).status_code == 401
    assert client.post('/api/cron/webhook-deliveries', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.post('/api/cron/webhook-deliveries', headers={'Authorization': 'Bearer test-cron-secret'}).status_code == 200


def test_conversation_list_paginates_and_searches(auth_client):
    client, _, company = auth_client
    instance = WhatsappInstance(company_id=company.id, instance_name='paged')
    db.session.add(instance)
    db.session.flush()
    for n in range(53):
        db.session.add(WhatsappConversation(company_id=company.id, instance_id=instance.id,
            remote_jid=f'{n}@s.whatsapp.net', name=f'Contact {n}'))
    db.session.commit()
    first = client.get('/api/whatsapp/conversations').json
    assert len(first['conversations']) == 50 and first['next_page'] == 2
    second = client.get('/api/whatsapp/conversations?page=2').json
    assert len(second['conversations']) == 3 and second['next_page'] is None
    searched = client.get('/api/whatsapp/conversations?q=Contact%2052').json
    assert [c['name'] for c in searched['conversations']] == ['Contact 52']


def test_whatsapp_stage_change_validates_company_and_pipeline(auth_client):
    client, user, company = auth_client
    other, _ = other_tenant()
    pipeline = Pipeline(name='Sales', company_id=company.id)
    alien_pipeline = Pipeline(name='Other sales', company_id=other.id)
    db.session.add_all([pipeline, alien_pipeline])
    db.session.flush()
    stage = PipelineStage(name='New', pipeline_id=pipeline.id, company_id=company.id, order=0)
    alien_stage = PipelineStage(name='Private', pipeline_id=alien_pipeline.id, company_id=other.id, order=0)
    lead = Lead(name='Move', company_id=company.id, assigned_to_id=user.id)
    db.session.add_all([stage, alien_stage, lead])
    db.session.commit()
    url = f'/api/whatsapp/leads/{lead.id}/stage'
    assert client.post(url, json={'pipeline_id': alien_pipeline.id, 'stage_id': alien_stage.id}).status_code == 400
    with patch('tasks_utils.generate_tasks_for_stage'), patch('tasks_utils.process_funnel_automations'):
        assert client.post(url, json={'pipeline_id': pipeline.id, 'stage_id': stage.id}).status_code == 200
    db.session.refresh(lead)
    assert lead.pipeline_id == pipeline.id and lead.pipeline_stage_id == stage.id


def test_webhooks_persist_retry_and_keep_request_id(auth_client):
    _, _, company = auth_client
    webhook = IntegrationWebhook(company_id=company.id, name='Test', url='https://example.test/hook', events=['lead.created'], secret='test')
    db.session.add(webhook)
    db.session.commit()
    from services.integrations_service import IntegrationsService
    from services.webhook_delivery_service import process_deliveries
    with patch('services.integrations_service.requests.post') as post:
        IntegrationsService.dispatch_webhooks(company.id, 'lead.created', {'id': 123})
        post.assert_not_called()
        job = WebhookDelivery.query.one()
        post.return_value.status_code = 503
        post.return_value.text = 'unavailable'
        assert process_deliveries()['processed'] == 1
        assert job.status == 'pending' and job.attempts == 1
        first_id = post.call_args.kwargs['headers']['X-NorthWay-Request-Id']
        job.available_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        post.return_value.status_code = 200
        assert process_deliveries()['processed'] == 1
        assert job.status == 'delivered' and job.attempts == 2
        assert post.call_args.kwargs['headers']['X-NorthWay-Request-Id'] == first_id


def test_postgres_conversion_serializes_concurrent_requests(auth_client, app):
    if db.engine.dialect.name != 'postgresql':
        pytest.skip('Row locking requires PostgreSQL')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    _, user, company = auth_client
    lead = Lead(name='Concurrent conversion', company_id=company.id, assigned_to_id=user.id)
    db.session.add(lead)
    db.session.commit()
    lead_id, user_id = lead.id, user.id
    barrier = Barrier(2)
    def convert():
        with app.test_client() as browser:
            with browser.session_transaction() as session:
                session['_user_id'] = str(user_id)
                session['_fresh'] = True
            barrier.wait(timeout=10)
            response = browser.post(f'/leads/{lead_id}/convert', data={'monthly_value': '100,00'})
            return response.status_code, response.location
    with patch('routes.leads.IntegrationsService.dispatch_webhooks'), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(convert) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert results[0] == results[1]
    assert results[0][0] == 302
    assert Client.query.filter_by(lead_id=lead_id).count() == 1


def test_postgres_migration_is_repeatable(app):
    if db.engine.dialect.name != 'postgresql':
        pytest.skip('Migration targets PostgreSQL')
    from pathlib import Path
    script = (Path(__file__).resolve().parents[2] / 'migrations/20260915_stabilization.sql').read_text()
    db.session.remove()
    connection = db.engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(script)
            cursor.execute(script)
        connection.commit()
    finally:
        connection.close()
