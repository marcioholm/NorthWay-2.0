from app import create_app, db
from models import User, Role, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES
import sqlite3

def migrate():
    app = create_app()
    with app.app_context():
        # 1. Create Role Table
        print("Creating Role table...")
        db.create_all() # This creates Role table if not exists. Won't update User.
        
        # 2. Add role_id to User table (SQLite ALTER)
        print("Checking user table schema...")
        try:
            with sqlite3.connect('instance/crm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(user)")
                columns = [info[1] for info in cursor.fetchall()]
                
                if 'role_id' not in columns:
                    print("Adding role_id column to user table...")
                    cursor.execute("ALTER TABLE user ADD COLUMN role_id INTEGER REFERENCES role(id)")
                    conn.commit()
                else:
                    print("role_id column already exists.")
        except Exception as e:
            print(f"Error modifying schema: {e}")

        # 3. Create Default Roles per Company
        print("Migrating users...")
        users = User.query.all()
        companies_migrated = set()
        
        # Permissions Definitions
        PERMS_ADMIN = ['manage_settings', 'manage_team', 'manage_financial', 'view_all_leads', 'edit_all_leads', 'delete_leads', 'view_all_clients', 'edit_all_clients', 'delete_clients', 'manage_pipelines']
        PERMS_MANAGER = ['view_all_leads', 'edit_all_leads', 'view_all_clients', 'edit_all_clients', 'view_all_tasks', 'manage_pipelines']
        PERMS_SALES = ['view_assigned_leads', 'edit_assigned_leads', 'create_leads', 'view_assigned_clients', 'edit_assigned_clients']
        
        roles_cache = {}

        for user in users:
            company_id = user.company_id
            
            # Ensure roles exist for this company
            if company_id not in companies_migrated:
                # Create default roles for this company
                
                # Admin
                r_admin = Role.query.filter_by(company_id=company_id, name='Administrador').first()
                if not r_admin:
                    r_admin = Role(name='Administrador', permissions=PERMS_ADMIN, company_id=company_id, is_default=False)
                    db.session.add(r_admin)
                
                # Manager
                r_manager = Role.query.filter_by(company_id=company_id, name='Gestor').first()
                if not r_manager:
                    r_manager = Role(name='Gestor', permissions=PERMS_MANAGER, company_id=company_id, is_default=False)
                    db.session.add(r_manager)

                # Sales (Default)
                r_sales = Role.query.filter_by(company_id=company_id, name='Vendedor').first()
                if not r_sales:
                    r_sales = Role(name='Vendedor', permissions=PERMS_SALES, company_id=company_id, is_default=True)
                    db.session.add(r_sales)
                
                db.session.commit()
                
                roles_cache[company_id] = {
                    'admin': r_admin,
                    'gestor': r_manager,
                    'vendedor': r_sales,
                    ROLE_ADMIN: r_admin,
                    ROLE_MANAGER: r_manager,
                    ROLE_SALES: r_sales
                }
                companies_migrated.add(company_id)
            
            # Assign Role
            if user.role in roles_cache[company_id]:
                target_role = roles_cache[company_id][user.role]
                user.role_id = target_role.id
                print(f"Assigned {user.name} ({user.role}) -> {target_role.name}")
            else:
                # Fallback to Sales
                target_role = roles_cache[company_id]['vendedor']
                user.role_id = target_role.id
                print(f"Assigned {user.name} (Unknown: {user.role}) -> Vendedor")

        db.session.commit()
        print("Migration complete.")

if __name__ == '__main__':
    migrate()
