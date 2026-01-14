from app import create_app
from models import User

app = create_app()

with app.app_context():
    print("--- USERS & COMPANIES ---")
    users = User.query.all()
    for u in users:
        print(f"User: {u.name} (ID: {u.id}) | Role: {u.role} | Company ID: {u.company_id}")
