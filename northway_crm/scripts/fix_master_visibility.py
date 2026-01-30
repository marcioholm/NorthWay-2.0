import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import LibraryBook, ContractTemplate, Company, User

def fix_visibility_master_only():
    with app.app_context():
        print("🛡️ SETTING DOCUMENTS TO MASTER-ONLY ACCESS...")
        
        # 1. Identify Master Company
        master_user = User.query.filter_by(email='master@northway.com').first()
        if not master_user:
            print("❌ Master user not found!")
            return
            
        master_id = master_user.company_id

        # 2. De-globalize templates
        count = 0
        templates = ContractTemplate.query.all()
        for tmpl in templates:
            # Revert to private
            tmpl.is_global = False
            # Ensure owner is Master
            tmpl.company_id = master_id
            count += 1
            print(f"🔒 Template made private: {tmpl.name}")
            
        # 3. Ensure Library Books are only linked to Master for now
        # (Though association table was cleared, my previous script linked them to Master)
        books = LibraryBook.query.all()
        for book in books:
            # Owners are already Company 6 generally, but let's be sure about association
            # The previous script did this:
            # if master_company not in book.allowed_companies:
            #    book.allowed_companies.append(master_company)
            pass

        db.session.commit()
        print(f"✨ SUCCESS: {count} templates reverted to private. Access is now controlled by Super Admin.")

if __name__ == "__main__":
    fix_visibility_master_only()
