from app import app
from models import User
from flask import session

with app.test_client() as client:
    # 1. Login
    rv = client.post('/login', data={'email': 'admin@northway.com', 'password': 'admin'}, follow_redirects=True)
    
    # 2. Test Dashboard
    rv = client.get('/dashboard')
    print(f"Dashboard status: {rv.status_code}")
    if rv.status_code != 200:
        print(rv.data.decode('utf-8'))
        
    # 3. Test API that might have broken
    from models import Client
    with app.app_context():
        c = Client.query.first()
        if c:
            rv = client.get(f'/api/clients/{c.id}/crepi/list')
            print(f"CREPI list status: {rv.status_code}")
            if rv.status_code != 200:
                print(rv.data.decode('utf-8'))
