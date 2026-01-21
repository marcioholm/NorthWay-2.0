from app import create_app
from models import db, User

app = create_app()

with app.app_context():
    users = User.query.all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"- {u.name} ({u.email}) [ID: {u.id}, Company: {u.company_id}]")
