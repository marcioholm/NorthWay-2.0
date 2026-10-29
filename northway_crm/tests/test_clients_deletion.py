from unittest.mock import patch
from datetime import date
from flask import url_for
from models import db, Client, Integration, Transaction


def test_delete_client_with_asaas_integration(auth_client, app):
    """
    Excluir um cliente com integração Asaas ativa, cancelando subscription (via getattr mockado)
    e pagamentos pendentes, deve responder com sucesso (redirect 302, sem 500/NameError).
    """
    client, user, company = auth_client

    with app.app_context():
        # Configurar integracao Asaas ativa com api_key
        integration = Integration(
            company_id=company.id,
            service='asaas',
            is_active=True,
            api_key='mock_asaas_api_key_test'
        )
        db.session.add(integration)

        # Criar cliente padrao (sem coluna subscription_id no banco)
        target_client = Client(
            company_id=company.id,
            account_manager_id=user.id,
            name="Cliente Asaas Deletion Test",
            email="asaas_client@example.com"
        )
        db.session.add(target_client)
        db.session.flush()

        # Criar transacao pendente com asaas_id vinculada ao cliente
        tx = Transaction(
            company_id=company.id,
            client_id=target_client.id,
            description="Mensalidade Outubro Test",
            due_date=date.today(),
            status='pending',
            asaas_id='pay_test_4321',
            amount=150.0
        )
        db.session.add(tx)
        db.session.commit()
        client_id = target_client.id

    with patch('services.asaas_service.delete_subscription') as mock_del_sub, \
         patch('services.asaas_service.cancel_payment') as mock_cancel_pay, \
         patch.object(Client, 'subscription_id', 'sub_test_98765', create=True):
        
        mock_del_sub.return_value = True
        mock_cancel_pay.return_value = True

        resp = client.post(f'/clients/{client_id}/delete', follow_redirects=False)

        assert resp.status_code == 302, f"Expected 302 redirect, got {resp.status_code}"
        assert resp.status_code != 500, "Deletion should not trigger 500 Internal Server Error"
        
        mock_del_sub.assert_called_once_with('sub_test_98765', api_key='mock_asaas_api_key_test')
        mock_cancel_pay.assert_called_once_with('pay_test_4321', api_key='mock_asaas_api_key_test')

    with app.app_context():
        deleted = Client.query.filter_by(id=client_id).first()
        assert deleted is None, "Client should be deleted from database"


def test_static_url_defaults_cache_busting(app):
    """
    url_for('static', filename='css/tailwind.min.css') deve conter '?v=' para cache busting automático.
    """
    with app.test_request_context():
        static_url = url_for('static', filename='css/tailwind.min.css')
        assert '?v=' in static_url, f"Expected '?v=' in static URL, got: {static_url}"
