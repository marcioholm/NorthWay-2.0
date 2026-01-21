from app import create_app
from models import db, User, Company

app = create_app()

with app.app_context():
    print("--- DEBUGGING LATEST USER ---")
    user = User.query.order_by(User.created_at.desc()).first()
    if user:
        print(f"User: {user.name} ({user.email})")
        print(f"Company ID: {user.company_id}")
        if user.company:
            print(f"Company Name: {user.company.name}")
            print(f"SaaS Status: {user.company.subscription_status}")
            print(f"Plan Type: {user.company.plan_type}")
            print(f"CPF/CNPJ: {user.company.cpf_cnpj}")
        else:
            print("No Company Linked")
    else:
        print("No users found.")
    
    print("\n--- DEBUGGING LATEST COMPANY ---")
    comp = Company.query.order_by(Company.created_at.desc()).first()
    if comp:
        print(f"Company: {comp.name}")
        print(f"SaaS Status: {comp.subscription_status}")
