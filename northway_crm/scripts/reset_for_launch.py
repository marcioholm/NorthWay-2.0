import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import User, Company
from sqlalchemy import text

def reset_for_launch():
    with app.app_context():
        print("🚀 STARTING PRODUCTION RESET...")
        
        # 0. Ensure Schema is Ready
        print("🛠️ Ensuring schema is ready...")
        try:
            with db.engine.connect() as conn:
                # Add columns if they don't exist
                columns_to_add = [
                    ("user", "last_login", "DATETIME"),
                    ("company", "last_active_at", "DATETIME"),
                ]
                for table, col, col_type in columns_to_add:
                    try:
                        conn.execute(text(f"ALTER TABLE \"{table}\" ADD COLUMN {col} {col_type}"))
                        conn.commit()
                        print(f"✅ Schema: Added {col} to {table}")
                    except Exception:
                        pass # Likely already exists
        except Exception as e:
            print(f"⚠️ Schema check warning: {e}")

        # 1. Identify Master User and Company
        master_user = User.query.filter_by(email='master@northway.com').first()
        if not master_user:
            print("❌ Master user not found! Aborting.")
            return
            
        master_company_id = master_user.company_id
        print(f"✅ Keeping Master Company ID: {master_company_id}")

        tables_to_clear = [
            "interaction", "task", "whats_app_message", "notification", 
            "billing_event", "financial_event", "expense", "client_checklist", 
            "goal", "\"transaction\"", "template_company_association", 
            "library_book_company_association", "user_pipeline_association", 
            "contract", "lead", "client", "contact", "pipeline_stage", "pipeline",
            "quick_message", "process_template"
        ]

        try:
            with db.engine.connect() as conn:
                # 2. Clear Global Data Tables
                print("🧹 Clearing data tables...")
                for table in tables_to_clear:
                    try:
                        conn.execute(text(f"DELETE FROM {table}"))
                        print(f"✅ Cleared {table}")
                    except Exception as te:
                        print(f"⚠️ Table {table} skipped: {te}")
                
                # 3. Handle Multitenant Cleanup (Users, Roles, Companies)
                # First, find IDs to delete
                other_company_ids_result = conn.execute(text(f"SELECT id FROM company WHERE id != {master_company_id}"))
                other_company_ids = [r[0] for r in other_company_ids_result.fetchall()]
                
                if other_company_ids:
                    ids_str = ", ".join(map(str, other_company_ids))
                    print(f"🏢 Removing {len(other_company_ids)} other companies and their users...")
                    conn.execute(text(f"DELETE FROM \"user\" WHERE company_id IN ({ids_str})"))
                    conn.execute(text(f"DELETE FROM role WHERE company_id IN ({ids_str})"))
                    conn.execute(text(f"DELETE FROM company WHERE id != {master_company_id}"))
                
                conn.commit()
                print("✨ SYSTEM RESET SUCCESSFUL! Ready for Sales.")
            
        except Exception as e:
            print(f"🔥 RESET FAILED: {str(e)}")

if __name__ == "__main__":
    confirm = input("ARE YOU SURE? This will delete ALL test data. (y/n): ")
    if confirm.lower() == 'y':
        reset_for_launch()
    else:
        print("Reset aborted.")
