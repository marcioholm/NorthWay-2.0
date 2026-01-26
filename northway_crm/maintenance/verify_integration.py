
import os
os.environ['SECRET_KEY'] = 'test'
os.environ['DATABASE_URL'] = 'sqlite:////tmp/test.db'
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'

from app import app
from models import db, User, Company, Integration

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    db.create_all()
    
    # Create test data
    if not Company.query.first():
        company = Company(name="Test Corp")
        db.session.add(company)
        db.session.commit()
    
    # Ensure no integration exists initially
    Integration.query.delete()
    db.session.commit()
        
    print("Testing Integration Query logic...")
    try:
        # Simulate logic from routes/dashboard.py:42
        company_id = 1
        count = Integration.query.filter_by(company_id=company_id, is_active=True).count()
        print(f"Integration Count: {count}")
        step_integrations = count > 0
        print(f"Step Integrations: {step_integrations}")
        print("SUCCESS: Query executed without error.")
    except Exception as e:
        print("CRITICAL FAILURE during query execution:")
        import traceback
        traceback.print_exc()
