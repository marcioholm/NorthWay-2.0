import pytest
from unittest.mock import patch, MagicMock
from models import Lead, ProspectingMessage, ProspectingSetting, ProspectingCampaign
from utils.webhooks import send_outbound_webhook

def test_send_outbound_webhook_success(app):
    # Mock database session commit and add
    with patch('utils.webhooks.db.session') as mock_session:
        with patch('utils.webhooks.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True, "message": "Olá", "angle": "Atrair", "model": "llama-3.1-8b-instant"}
            mock_post.return_value = mock_response

            success, payload, error = send_outbound_webhook(
                tenant_id=1,
                lead_id=1,
                action="generate_message",
                webhook_url="http://mock-n8n.com/generate",
                payload={"test": "data"}
            )

            assert success is True
            assert payload == {"success": True, "message": "Olá", "angle": "Atrair", "model": "llama-3.1-8b-instant"}
            assert error is None
            assert mock_session.add.called
            assert mock_session.commit.called

def test_send_outbound_webhook_failure(app):
    with patch('utils.webhooks.db.session') as mock_session:
        with patch('utils.webhooks.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.json.side_effect = ValueError("No JSON")
            mock_post.return_value = mock_response

            success, payload, error = send_outbound_webhook(
                tenant_id=1,
                lead_id=1,
                action="generate_message",
                webhook_url="http://mock-n8n.com/generate",
                payload={"test": "data"}
            )

            assert success is False
            assert payload == {"raw_text": "Internal Server Error"}
            assert "Status 500" in error
            assert mock_session.add.called
            assert mock_session.commit.called

def test_generate_message_endpoint(client, app):
    # Mock current_user
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    mock_user.id = 1
    mock_user.company_id = 1
    mock_user.name = "Test User"
    mock_user.company.name = "Test Company"

    # Real model instances
    lead = Lead(
        id=1,
        company_id=1,
        in_execution=False,
        prospecting_status='novo',
        prospecting_campaign_id=1,
        preferred_channel='whatsapp',
        phone='11999999999',
        email='test@example.com',
        name='Gabriel'
    )
    setting = ProspectingSetting(
        company_id=1,
        generate_message_webhook_url="http://mock-n8n.com/generate"
    )

    # Mock access and queries
    with patch('routes.prospecting.check_prospecting_access', return_value=(True, None)), \
         patch('flask_login.utils._get_user', return_value=mock_user), \
         patch('routes.prospecting.Lead.query') as mock_lead_query, \
         patch('routes.prospecting.ProspectingSetting.query') as mock_setting_query, \
         patch('routes.prospecting.db.session') as mock_session, \
         patch('routes.prospecting.sync_prospecting_stage') as mock_sync, \
         patch('routes.prospecting.send_outbound_webhook') as mock_webhook:

        mock_lead_query.filter_by.return_value.first_or_404.return_value = lead
        mock_setting_query.filter_by.return_value.first.return_value = setting
        mock_webhook.return_value = (True, {"message": "Olá Gabriel...", "angle": "Atrair", "model": "llama-3.1-8b-instant"}, None)

        response = client.post('/prospecting/lead/1/generate-message')
        result = response.get_json()
        assert response.status_code == 200
        assert result['success'] is True
        assert result['data']['results'][0]['content'] == "Olá Gabriel..."
        assert result['data']['results'][0]['status'] == "pending_approval"
        
        assert lead.prospecting_status == 'pending_approval'
        assert lead.in_execution is False

def test_approve_message_endpoint(client, app):
    mock_user = MagicMock()
    mock_user.is_authenticated = True
    mock_user.id = 1
    mock_user.company_id = 1
    mock_user.name = "Test User"
    mock_user.company.name = "Test Company"

    lead = Lead(
        id=1,
        company_id=1,
        prospecting_status='pending_approval',
        prospecting_campaign_id=1,
        preferred_channel='whatsapp',
        wa_attempts=0
    )
    message = ProspectingMessage(
        id=1,
        company_id=1,
        lead_id=1,
        status='pending_approval',
        channel='whatsapp',
        content="Olá Gabriel..."
    )
    setting = ProspectingSetting(
        company_id=1,
        send_whatsapp_webhook_url="http://mock-n8n.com/send"
    )
    campaign = ProspectingCampaign(
        id=1,
        followup_interval_days=3
    )

    with patch('routes.prospecting.check_prospecting_access', return_value=(True, None)), \
         patch('flask_login.utils._get_user', return_value=mock_user), \
         patch('routes.prospecting.Lead.query') as mock_lead_query, \
         patch('routes.prospecting.ProspectingMessage.query') as mock_msg_query, \
         patch('routes.prospecting.ProspectingSetting.query') as mock_setting_query, \
         patch('routes.prospecting.ProspectingCampaign.query') as mock_campaign_query, \
         patch('routes.prospecting.Interaction') as mock_int_cls, \
         patch('routes.prospecting.db.session') as mock_session, \
         patch('routes.prospecting.sync_prospecting_stage') as mock_sync, \
         patch('routes.prospecting.send_outbound_webhook') as mock_webhook:

        mock_lead_query.filter_by.return_value.first_or_404.return_value = lead
        mock_msg_query.filter_by.return_value.first_or_404.return_value = message
        mock_setting_query.filter_by.return_value.first.return_value = setting
        mock_campaign_query.get.return_value = campaign
        mock_webhook.return_value = (True, {"success": True}, None)

        response = client.post('/prospecting/lead/1/approve-message/1')
        if response.status_code != 200:
            print("APPROVE MESSAGE RESPONSE:", response.text)
        assert response.status_code == 200
        result = response.get_json()
        assert result['success'] is True
        assert result['data']['status'] == "sent"

        assert message.status == 'sent'
        assert lead.prospecting_status == 'contatado'
        assert lead.wa_attempts == 1
