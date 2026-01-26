
from app import create_app
from models import User

app = create_app()

with app.app_context():
    users = User.query.all()
    print("--- User List ---")
    for user in users:
        print(f"Name: {user.name} | Email: {user.email} | Role: {user.role}")
    print("-----------------")
