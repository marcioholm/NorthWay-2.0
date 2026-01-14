from app import create_app
from models import db, User, Company, Role, ROLE_ADMIN
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # 1. Ensure 'NorthWay System' company exists
    system_comp = Company.query.filter_by(name='NorthWay System').first()
    if not system_comp:
        print("Creating System Company...")
        system_comp = Company(name='NorthWay System', document='00000000000000')
        db.session.add(system_comp)
        db.session.commit()
    
    # 2. Check for Master User
    email = 'master@northway.com'
    password = 'master_password_123' # Default, change later
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        print(f"User {email} already exists. Updating...")
        existing_user.password_hash = generate_password_hash(password)
        existing_user.is_super_admin = True
        existing_user.company_id = system_comp.id
        db.session.commit()
        print("Updated.")
    else:
        print(f"Creating new Master User: {email}")
        new_user = User(
            name='Super Admin',
            email=email,
            password_hash=generate_password_hash(password),
            company_id=system_comp.id,
            role=ROLE_ADMIN,
            is_super_admin=True
        )
        db.session.add(new_user)
        db.session.commit()
        print("Created.")
        
    print(f"\nSUCCESS! Credentials:\nEmail: {email}\nPassword: {password}")
