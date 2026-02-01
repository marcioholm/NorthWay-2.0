import sys
import os

# Add parent dir to path to import app factory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, LibraryBook, Company, User

def update_library():
    app = create_app()
    with app.app_context():
        print("🚀 Updating Library Content & Covers...")

        # 1. Admin Company Resolution
        company = Company.query.get(6)
        if not company:
            admin = User.query.filter_by(is_super_admin=True).first()
            if admin and admin.company:
                company = admin.company
        
        if not company:
            print("❌ No admin company found. Aborting.")
            return

        print(f"🏢 Context: {company.name} (ID: {company.id})")

        # 2. Add "O Custo da Inação"
        inaction_book = LibraryBook.query.filter_by(title="O Custo da Inação").first()
        if not inaction_book:
            inaction_book = LibraryBook(
                title="O Custo da Inação",
                description="Apresentação estratégica para leads: como a falta de direção e processo está custando R$ 120k/ano para óticas médias. O caminho para o crescimento com direção.",
                category="Apresentação",
                cover_image="cover_inaction.jpg",
                route_name="docs.presentation_cost_of_inaction",
                active=True
            )
            db.session.add(inaction_book)
            db.session.commit()
            print("✅ Created 'O Custo da Inação'")
            
            # Associate
            if company not in inaction_book.allowed_companies:
                inaction_book.allowed_companies.append(company)
        else:
            print("ℹ️ 'O Custo da Inação' already exists. Updating cover/route...")
            inaction_book.cover_image = "cover_inaction.jpg"
            inaction_book.route_name = "docs.presentation_cost_of_inaction"
            inaction_book.category = "Apresentação"
            
            if company not in inaction_book.allowed_companies:
                inaction_book.allowed_companies.append(company)

        # 3. Update Covers for Existing Books
        # Mapping Title -> Cover Filename
        cover_map = {
            "Diagnóstico do Mercado Óptico Local": "cover_diagnostic.jpg",
            "Diagnóstico Estratégico": "cover_diagnostic_old.jpg", # Or same
            "Playbook Comercial": "cover_sales.jpg",
            "Playbook de Processos": "cover_process.jpg",
            "Playbook de Treinamento": "cover_training.jpg",
            "Onboarding Institucional": "cover_onboarding.jpg",
            "Manual do Usuário": "cover_manual.jpg",
            "Apresentação Institucional": "cover_institutional.jpg",
            "Playbook BDR": "cover_bdr.jpg",
            "Oferta Principal": "cover_offer_main.jpg",
            "Oferta Downsell": "cover_offer_downsell.jpg",
            "Consultoria": "cover_consultancy.jpg",
            "O Custo da Inação": "cover_inaction.jpg",
            "Plano Essencial": "cover_offer_downsell.jpg",
            "Manual de Onboarding": "cover_manual.jpg",
            "Scripts": "cover_sales_scripts.jpg",
            "Objeções": "cover_objections.jpg",
            "Academia": "cover_training.jpg"
        }

        all_books = LibraryBook.query.all()
        for book in all_books:
            # Fuzzy match or direct match?
            # Let's try direct first, then partiai
            updated = False
            for key, filename in cover_map.items():
                if key.lower() in book.title.lower():
                    book.cover_image = filename
                    updated = True
                    print(f"🔄 Check: {book.title} -> {filename}")
                    break
            
            # Default fallbacks if no match
            if not updated:
                if "playbook" in book.title.lower(): book.cover_image = "cover_general_playbook.jpg"
                elif "apresentação" in book.title.lower(): book.cover_image = "cover_general_presentation.jpg"
                else: book.cover_image = "cover_default.jpg"
                print(f"⚠️ Fallback: {book.title} -> {book.cover_image}")

        db.session.commit()
        print("✨ Library Updates Complete!")

if __name__ == "__main__":
    update_library()
