from app import create_app, db
from models import User, ProcessTemplate, Role
from flask_login import login_user

app = create_app()

with app.app_context():
    print("--- Debugging Settings Processes ---")
    try:
        # 1. Fetch the user "Real Tester" or any admin
        user = User.query.filter(User.email.like('%test_reg_fix_real%')).first()
        if not user:
             user = User.query.filter_by(role='admin').first()
             
        print(f"User: {user.name}, ID: {user.id}, Company: {user.company_id}")
        
        # 2. Check Role Access
        print(f"Role: {user.user_role}")
        if user.user_role:
             print(f"Role Name: {user.user_role.name}")
             print(f"Permissions: {user.user_role.permissions}")
             
        can_manage = user.user_role.name in ['Administrador', 'Gestor'] or 'manage_settings' in (user.user_role.permissions or [])
        print(f"Can Manage: {can_manage}")
        
        # 3. Fetch Templates
        print(f"Fetching templates for company {user.company_id}...")
        templates = ProcessTemplate.query.filter_by(company_id=user.company_id).all()
        print(f"Found {len(templates)} templates.")
        for t in templates:
            print(f"- {t.name} (Steps Type: {type(t.steps)})")
            
        print("--- Success ---")

    except Exception as e:
        print(f"!!! CAUGHT EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
