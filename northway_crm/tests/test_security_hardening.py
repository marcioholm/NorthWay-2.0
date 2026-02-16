import json

def test_asaas_webhook_security(client):
    """Verify that Asaas webhook requires a valid token"""
    # 1. No token
    response = client.post('/api/webhooks/asaas/1', json={'event': 'test'})
    assert response.status_code == 401
    
    # 2. Invalid token
    response = client.post('/api/webhooks/asaas/1', 
                           headers={'asaas-access-token': 'wrong'},
                           json={'event': 'test'})
    assert response.status_code == 401
    
    # 3. Valid token (from conftest env)
    response = client.post('/api/webhooks/asaas/1', 
                           headers={'asaas-access-token': 'test-asaas-token'},
                           json={'event': 'PAYMENT_CONFIRMED', 'payment': {'id': 'tx_1', 'customer': 'cus_1'}})
    assert response.status_code != 401
