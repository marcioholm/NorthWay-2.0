import pytest
import os
import sys

# Add the app directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Avoid top-level imports that might trigger context errors

@pytest.fixture(name="app")
def app_fixture():
    # Force testing config
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['SECRET_KEY'] = 'test-secret'
    os.environ['ASAAS_WEBHOOK_TOKEN'] = 'test-asaas-token'
    
    from app import create_app
    # Set it in config directly instead of just env
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "ASAAS_WEBHOOK_TOKEN": "test-asaas-token"
    })

    from models import db
    with app.app_context():
        # Ensure we are using the in-memory DB
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def auth_client(client, app):
    """A client with an authenticated user"""
    from flask_login import login_user
    from models import db, User, Company, ROLE_ADMIN
    with app.app_context():
        # Create a test company
        company = Company(name="Test Company", plan_type="monthly")
        db.session.add(company)
        db.session.commit()
        
        # Create a test user
        user = User(
            email="test@example.com",
            name="Test User",
            company_id=company.id,
            role=ROLE_ADMIN
        )
        user.password_hash = "mocked"
        db.session.add(user)
        db.session.commit()
        
        # In Flask-Login, we only need the user_id in the session
        # and the user to exist in the DB for the user_loader
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
            
        yield client, user, company
