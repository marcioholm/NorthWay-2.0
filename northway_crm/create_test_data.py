from app import create_app
from models import db, User, Company, Role, ROLE_ADMIN, ROLE_SALES
from werkzeug.security import generate_password_hash

app = create_app()

def create_company_with_admin(name, plan, admin_email, admin_name):
    # Check if company exists
    comp = Company.query.filter_by(name=name).first()
    if not comp:
        print(f"Creating Company: {name}...")
        comp = Company(name=name, plan=plan, status='active')
        if plan == 'pro':
            comp.max_users = 10
            comp.max_leads = 5000
        else:
            comp.max_users = 2
            comp.max_leads = 500
            
        db.session.add(comp)
        db.session.commit()
    else:
        print(f"Company {name} already exists.")
        
    # Check Admin
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        print(f"Creating Admin: {admin_email}...")
        admin = User(
            name=admin_name,
            email=admin_email,
            password_hash=generate_password_hash('123456'),
            company_id=comp.id,
            role=ROLE_ADMIN
        )
        db.session.add(admin)
        db.session.commit()
    else:
        print(f"Admin {admin_email} already exists. Updating company link...")
        admin.company_id = comp.id
        admin.role = ROLE_ADMIN
        admin.password_hash = generate_password_hash('123456') # Reset pass for test
        db.session.commit()

    return comp, admin

with app.app_context():
    # 1. Company Alpha (Pro)
    create_company_with_admin(
        name='Company Alpha',
        plan='pro',
        admin_email='admin@alpha.com',
        admin_name='Admin Alpha'
    )
    
    # 2. Company Beta (Starter)
    create_company_with_admin(
        name='Company Beta',
        plan='starter',
        admin_email='admin@beta.com',
        admin_name='Admin Beta'
    )
    
    print("\nSUCCESS! Test Data Created:")
    print("1. admin@alpha.com / 123456 (Company Alpha)")
    print("2. admin@beta.com / 123456 (Company Beta)")
