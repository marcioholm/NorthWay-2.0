import json
import time
from models import db, Lead, ProspectingCampaign, ProspectingMessage, ProspectingSetting, ProspectingBatch
from constants import CampaignStatus, MessageStatus, LeadChannel, MessageType

def test_batch_dispatch_flow(app, auth_client):
    client, user, company = auth_client
    
    with app.app_context():
        # Setup settings
        setting = ProspectingSetting(
            company_id=company.id,
            generate_message_webhook_url="http://mock-generate",
            send_whatsapp_webhook_url="http://mock-send",
            send_email_webhook_url="http://mock-send-email",
            manual_approval_required=True
        )
        db.session.add(setting)
        
        # Setup campaign
        campaign = ProspectingCampaign(
            company_id=company.id,
            name="Test Campaign",
            status=CampaignStatus.ATIVA,
            is_active=True
        )
        db.session.add(campaign)
        db.session.commit()
        
        # Setup leads
        lead1 = Lead(company_id=company.id, name="Lead One", preferred_channel=LeadChannel.WHATSAPP, phone="5541999999999", prospecting_campaign_id=campaign.id)
        lead2 = Lead(company_id=company.id, name="Lead Two", preferred_channel=LeadChannel.WHATSAPP, phone="5541888888888", prospecting_campaign_id=campaign.id)
        db.session.add_all([lead1, lead2])
        db.session.commit()
        
        # Setup pending messages
        msg1 = ProspectingMessage(
            company_id=company.id,
            lead_id=lead1.id,
            campaign_id=campaign.id,
            channel=LeadChannel.WHATSAPP,
            type=MessageType.OUTBOUND,
            status=MessageStatus.PENDING_APPROVAL,
            content="Hello Lead One"
        )
        msg2 = ProspectingMessage(
            company_id=company.id,
            lead_id=lead2.id,
            campaign_id=campaign.id,
            channel=LeadChannel.WHATSAPP,
            type=MessageType.OUTBOUND,
            status=MessageStatus.PENDING_APPROVAL,
            content="Hello Lead Two"
        )
        db.session.add_all([msg1, msg2])
        db.session.commit()
        
        msg1_id = msg1.id
        msg2_id = msg2.id

    # 1. Start a batch
    resp = client.post('/prospecting/batch/start', data=json.dumps({
        'message_ids': [msg1_id, msg2_id]
    }), content_type='application/json')
    
    assert resp.status_code == 200
    data = resp.json
    assert data['success'] is True
    batch_id = data['data']['batch_id']
    assert data['data']['total_count'] == 2

    # 2. Get batch status
    resp = client.get(f'/prospecting/batch/{batch_id}/status')
    assert resp.status_code == 200
    status_data = resp.json
    assert status_data['success'] is True
    assert status_data['data']['total_count'] == 2
    assert status_data['data']['status'] in ['pending', 'processing', 'completed']

    # 3. Check active batch
    resp = client.get('/prospecting/batch/active')
    assert resp.status_code == 200
    active_data = resp.json
    assert active_data['success'] is True
    if active_data['data']:
        assert active_data['data']['id'] == batch_id

    # 4. Stop batch
    resp = client.post(f'/prospecting/batch/{batch_id}/stop')
    assert resp.status_code == 200
    assert resp.json['success'] is True

    # Verify batch is stopped
    with app.app_context():
        batch = ProspectingBatch.query.get(batch_id)
        assert batch.status == 'stopped'
