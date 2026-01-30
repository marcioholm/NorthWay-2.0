import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import LibraryBook, ContractTemplate, Company, User

def restore_master_access():
    with app.app_context():
        print("🔍 RESTORING MASTER ACCESS TO DOCUMENTS...")
        
        # 1. Identify Master User and Company
        master_user = User.query.filter_by(email='master@northway.com').first()
        if not master_user:
            print("❌ Master user not found!")
            return
            
        master_company = Company.query.get(master_user.company_id)
        if not master_company:
            print("❌ Master company not found!")
            return
            
        print(f"🏢 Master Company: {master_company.name} (ID: {master_company.id})")

        # 2. Re-associate ALL Library Books
        books = LibraryBook.query.all()
        for book in books:
            if master_company not in book.allowed_companies:
                book.allowed_companies.append(master_company)
                print(f"📖 Linked Book: {book.title}")
        
        # 3. Re-associate and Globalize Contract Templates
        templates = ContractTemplate.query.all()
        for tmpl in templates:
            # Re-link owner if necessary (or just make global)
            tmpl.company_id = master_company.id
            tmpl.is_global = True
            print(f"📄 Globalized Template: {tmpl.name}")
            
        db.session.commit()
        print("✨ RESTORATION COMPLETE!")

if __name__ == "__main__":
    restore_master_access()
