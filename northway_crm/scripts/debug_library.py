import sys
import os

# Add parent dir to path to import app factory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, LibraryBook, Company, User

def debug_library():
    app = create_app()
    with app.app_context():
        print("🔍 Debugging Library Visibility")
        
        # 1. List All Companies
        print("\n🏢 Companies:")
        companies = Company.query.all()
        for c in companies:
            print(f" - ID: {c.id} | Name: {c.name} | Plan: {c.plan_type}")

        # 2. List All Books & Their Access
        print("\n📚 Library Books & Access:")
        books = LibraryBook.query.all()
        if not books:
            print("❌ No books found in LibraryBook table!")
        
        for book in books:
            allowed_ids = [c.id for c in book.allowed_companies]
            status = "✅ Active" if book.active else "❌ Inactive"
            print(f" - [{book.id}] '{book.title}' ({status})")
            print(f"   Route: {book.route_name}")
            print(f"   Cover: {book.cover_image}")
            print(f"   Allowed Company IDs: {allowed_ids}")
            
        # 3. Specific Check for 'Cost of Inaction'
        print("\n🎯 Specific Check: 'O Custo da Inação'")
        target = LibraryBook.query.filter((LibraryBook.title.ilike('%Custo%'))).first()
        if target:
            print(f"   Found ID: {target.id}")
            print(f"   Active: {target.active}")
            print(f"   Allowed Companies: {[c.name for c in target.allowed_companies]}")
        else:
            print("   ❌ NOT FOUND via query title like '%Custo%'")

if __name__ == "__main__":
    debug_library()
