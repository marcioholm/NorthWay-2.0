import pytest
from flask import url_for
from werkzeug.routing import BuildError

ALLOWED_PUBLIC_ENDPOINTS = {
    'auth.blocked_account',
    'auth.callback',
    'auth.forgot_password',
    'auth.google_login',
    'auth.login',
    'auth.register',
    'auth.reset_password',
    'billing.asaas_webhook',
    'dashboard.index',
    'diagnostic_raiox.index',
    'docs.ebook_institutional',
    'docs.playbook_dia_das_maes_marka_moveis',
    'evolution_webhook.evolution_webhook',
    'robots_txt',
    'favicon',                                 # Ícone da aba do navegador (/favicon.ico)
    'sitemap',
    'static',
    'whatsapp.ping_whatsapp',
}

def test_emergency_recreate_is_gone_or_blocked(client):
    """Anonymous access to emergency-recreate must be gone (404) or blocked (403/401/302)."""
    resp = client.get('/master/emergency-recreate')
    assert resp.status_code in (404, 403, 401, 302), f"Expected blocked/gone, got {resp.status_code}"

def test_super_me_is_gone_or_blocked(auth_client):
    """Tenant user must NOT be able to hit /master/super-me to elevate privileges."""
    client, user, _ = auth_client
    resp = client.get('/master/super-me')
    assert resp.status_code in (404, 403), f"Expected blocked/gone, got {resp.status_code}"
    assert getattr(user, 'is_super_admin', False) is False

def test_diagnostic_access_is_gone_or_blocked(client):
    """Hardcoded diagnostic secret must not work or route must be deleted."""
    diag_param = "northway" + "_super_diagnostic_" + "99"
    resp = client.get(f'/master/diagnostic-access-v2?secret={diag_param}')
    assert resp.status_code in (404, 403, 401, 302), f"Expected blocked/gone, got {resp.status_code}"

def test_regular_user_cannot_access_master_dashboard(auth_client):
    """A regular tenant user must receive 403 Forbidden on master dashboard."""
    client, user, _ = auth_client
    resp = client.get('/master/dashboard')
    assert resp.status_code in (403, 404), f"Regular user should be forbidden, got {resp.status_code}"

def test_api_debug_routes_removed_or_forbidden(client, auth_client):
    """Email debug routes must be removed or strictly super-admin."""
    # Anonymous check
    resp_anon = client.get('/debug/emails')
    assert resp_anon.status_code in (404, 403, 401, 302)
    
    # Regular user check
    client_auth, _, _ = auth_client
    resp_auth = client_auth.get('/debug/emails')
    assert resp_auth.status_code in (404, 403)

def test_revert_access_validation(auth_client, app):
    """revert_access must only work if session contains a valid super_admin_id."""
    client, user, _ = auth_client
    
    # Case 1: no super_admin_id in session -> 403 Forbidden
    resp = client.get('/master/revert')
    assert resp.status_code in (403, 404), f"Expected 403 when not impersonating, got {resp.status_code}"

def test_anonymous_route_access_coverage(client, app):
    """
    Every parameterless GET route in the application must require authentication
    unless explicitly in ALLOWED_PUBLIC_ENDPOINTS.
    """
    unprotected = []
    with app.test_request_context():
        for rule in app.url_map.iter_rules():
            if 'GET' not in rule.methods:
                continue
            if rule.arguments:  # Skip parameterized routes for this pass
                continue
            if rule.endpoint in ALLOWED_PUBLIC_ENDPOINTS:
                continue
            
            try:
                url = url_for(rule.endpoint)
            except (BuildError, Exception):
                continue
                
            resp = client.get(url)
            # Must redirect to login or return 401/403/404/405
            if resp.status_code == 200:
                unprotected.append((rule.endpoint, url))

    assert not unprotected, f"Routes accessible anonymously with 200: {unprotected}"

def test_tenant_user_blocked_from_all_master_routes(auth_client, app):
    """
    A tenant user (is_super_admin=False) must not receive 200 on ANY /master/* route.
    """
    client, user, _ = auth_client
    accessible_master = []
    with app.test_request_context():
        for rule in app.url_map.iter_rules():
            if 'GET' not in rule.methods:
                continue
            if not (rule.rule.startswith('/master') or rule.rule.startswith('/admin/master')):
                continue
            if rule.arguments:
                continue

            try:
                url = url_for(rule.endpoint)
            except (BuildError, Exception):
                continue

            resp = client.get(url)
            if resp.status_code == 200:
                accessible_master.append((rule.endpoint, url))

    assert not accessible_master, f"Master routes returning 200 for regular user: {accessible_master}"
 
def test_system_reset_web_route_removed(client, auth_client):
    """The /master/system-reset web route must no longer exist (404)."""
    resp_anon = client.get('/master/system-reset')
    assert resp_anon.status_code == 404, f"Expected 404, got {resp_anon.status_code}"
    
    auth_c, _, _ = auth_client
    resp_auth = auth_c.get('/master/system-reset')
    assert resp_auth.status_code == 404, f"Expected 404, got {resp_auth.status_code}"

def test_allowlist_only_real_endpoints(app):
    """Garante que todos os endpoints declarados em ALLOWED_PUBLIC_ENDPOINTS existem em app.view_functions."""
    missing = [ep for ep in ALLOWED_PUBLIC_ENDPOINTS if ep not in app.view_functions]
    assert not missing, f"Endpoints na allowlist que não existem em app.view_functions: {missing}"

def test_system_reset_cli_command(runner, app, monkeypatch):
    """
    system-reset CLI command:
    - Sem ALLOW_SYSTEM_RESET=1, aborta mesmo com --confirm e não apaga nada
    - Com ALLOW_SYSTEM_RESET=1 e input='n', cancela
    - Com ALLOW_SYSTEM_RESET=1 e --confirm, exibe host do banco e total de empresas
    """
    from models import db, Company, User, ROLE_ADMIN
    with app.app_context():
        # Setup sample companies
        master_comp = Company(name="Master HQ", plan_type="enterprise", payment_status="active", subscription_status="active")
        db.session.add(master_comp)
        db.session.commit()
        super_u = User(name="Super", email="super@northway.com", company_id=master_comp.id, role=ROLE_ADMIN, is_super_admin=True)
        super_u.password_hash = "mock"
        db.session.add(super_u)

        sample_comp = Company(name="Empresa Teste CLI", plan_type="pro", payment_status="active", subscription_status="active")
        db.session.add(sample_comp)
        db.session.commit()

        # 1. Sem ALLOW_SYSTEM_RESET=1: deve abortar mesmo passando --confirm
        monkeypatch.delenv('ALLOW_SYSTEM_RESET', raising=False)
        res_no_env = runner.invoke(args=['system-reset', '--confirm', 'RESET_PRODUCTION'])
        assert "ALLOW_SYSTEM_RESET=1 e obrigatoria" in res_no_env.output
        # Garante que a empresa teste NÃO foi apagada
        assert Company.query.filter_by(name="Empresa Teste CLI").first() is not None

        # 2. Com ALLOW_SYSTEM_RESET=1 mas confirmando 'n': deve cancelar
        monkeypatch.setenv('ALLOW_SYSTEM_RESET', '1')
        res_cancel = runner.invoke(args=['system-reset'], input='n\n')
        assert "Operacao cancelada" in res_cancel.output
        assert Company.query.filter_by(name="Empresa Teste CLI").first() is not None

        # 3. Com ALLOW_SYSTEM_RESET=1 e --confirm: deve mostrar host e executar
        res_run = runner.invoke(args=['system-reset', '--confirm', 'RESET_PRODUCTION'])
        assert "Host do banco de dados:" in res_run.output
        assert "Total de empresas que serao afetadas:" in res_run.output
        assert "Sistema resetado com sucesso via CLI" in res_run.output
        assert Company.query.filter_by(name="Empresa Teste CLI").first() is None

def test_super_admin_core_workflow(client, app):
    """
    Test manual flow for super admin:
    - /master/dashboard (200)
    - /master/companies (200)
    - /master/company/<id> (200)
    - /master/impersonate/<user_id> (302 -> /home)
    - /master/revert (302 -> /master/dashboard)
    - /master/books (200)
    """
    from models import db, User, Company, ROLE_ADMIN
    with app.app_context():
        # Setup master company & super admin
        master_comp = Company(name="NorthWay HQ", plan_type="enterprise", payment_status="active", subscription_status="active")
        db.session.add(master_comp)
        db.session.commit()

        super_user = User(name="Super Admin", email="super@northway.com", company_id=master_comp.id, role=ROLE_ADMIN)
        super_user.password_hash = "mocked"
        super_user.is_super_admin = True
        db.session.add(super_user)

        # Setup tenant company & user
        tenant_comp = Company(name="Cliente Teste", plan_type="pro", payment_status="active", subscription_status="active")
        db.session.add(tenant_comp)
        db.session.commit()

        tenant_user = User(name="Gestor Cliente", email="gestor@cliente.com", company_id=tenant_comp.id, role=ROLE_ADMIN)
        tenant_user.password_hash = "mocked"
        tenant_user.is_super_admin = False
        db.session.add(tenant_user)
        db.session.commit()

        # Login as super admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(super_user.id)
            sess['_fresh'] = True

        # 1. /master/dashboard
        r1 = client.get('/master/dashboard')
        assert r1.status_code == 200, f"/master/dashboard failed with {r1.status_code}"

        # 2. /master/companies (redireciona para o dashboard unificado de empresas)
        r2 = client.get('/master/companies', follow_redirects=True)
        assert r2.status_code == 200, f"/master/companies failed with {r2.status_code}"

        # 3. /master/company/<id>/details (detalhes da empresa)
        r3 = client.get(f'/master/company/{tenant_comp.id}/details')
        assert r3.status_code == 200, f"/master/company/{tenant_comp.id}/details failed with {r3.status_code}"

        # 4. /master/impersonate/<user_id>
        r4 = client.get(f'/master/impersonate/{tenant_user.id}')
        assert r4.status_code == 302, f"impersonate failed with {r4.status_code}"
        with client.session_transaction() as sess:
            assert sess.get('super_admin_id') in (super_user.id, str(super_user.id))
            assert str(sess.get('_user_id')) == str(tenant_user.id)

        # 5. /master/revert
        r5 = client.get('/master/revert')
        assert r5.status_code == 302, f"revert failed with {r5.status_code}"
        with client.session_transaction() as sess:
            assert 'super_admin_id' not in sess or sess.get('super_admin_id') is None
            assert sess.get('_user_id') == str(super_user.id)

        # 6. /master/books (biblioteca/livros)
        r6 = client.get('/master/books')
        assert r6.status_code == 200, f"/master/books failed with {r6.status_code}"


