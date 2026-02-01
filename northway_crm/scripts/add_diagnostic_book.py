import sys
import os

# Add parent dir to path to import app factory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, LibraryBook, Company, User

def add_diagnostic_book():
    app = create_app()
    with app.app_context():
        print("🚀 Adding 'Diagnóstico do Mercado Óptico' to Library...")

        # 1. Find the target company (Admin's company)
        # We'll look for the company with ID 6 (as seen in seed_northway_data.py) or fallback to the first super admin's company
        company = Company.query.get(6)
        if not company:
            print("⚠️ Company ID 6 not found. Searching for Super Admin...")
            admin = User.query.filter_by(is_super_admin=True).first()
            if admin and admin.company:
                company = admin.company
                print(f"✅ Found Admin Company: {company.name} (ID: {company.id})")
            else:
                print("❌ No suitable company found to assign the book to.")
                return

        # 2. Check/Create Book
        # Route name MUST match what's in docs.py: presentation_diagnostic -> @docs_bp.route('/diagnostic-aprofundado')
        # Wait, docs.py says:
        # @docs_bp.route('/diagnostic-aprofundado')
        # def presentation_diagnostic(): ...
        # So route_name should be 'docs.presentation_diagnostic'
        
        book_title = "Diagnóstico do Mercado Óptico Local"
        route_name = "docs.presentation_diagnostic"
        
        book = LibraryBook.query.filter_by(title=book_title).first()
        
        if not book:
            book = LibraryBook(
                title=book_title,
                description="Uma análise exclusiva e completa sobre o mercado óptico local, identificando os principais gargalos de crescimento, a armadilha da inação e o custo real de não ter processos definidos. Inclui dados sobre perda de vendas e estratégias de recuperação.",
                category="Apresentação",
                cover_image="diagnostic_cover.jpg", # Placeholder, frontend should handle missing image or we add one later
                route_name=route_name,
                active=True
            )
            db.session.add(book)
            db.session.commit()
            print(f"✅ Created new LibraryBook: '{book.title}' (ID: {book.id})")
        else:
            print(f"ℹ️ Book '{book.title}' already exists (ID: {book.id}). Updating details...")
            book.route_name = route_name
            book.description = "Uma análise exclusiva e completa sobre o mercado óptico local, identificando os principais gargalos de crescimento, a armadilha da inação e o custo real de não ter processos definidos. Inclui dados sobre perda de vendas e estratégias de recuperação."
            # Force update category if needed
            book.category = "Apresentação"
            db.session.commit()

        # 3. Associate with Company
        if company not in book.allowed_companies:
            book.allowed_companies.append(company)
            db.session.commit()
            print(f"✅ Associated book with company: {company.name}")
        else:
            print(f"ℹ️ Book already associated with company: {company.name}")

        print("✨ Success! The diagnostic presentation is now in the library.")

if __name__ == "__main__":
    add_diagnostic_book()
