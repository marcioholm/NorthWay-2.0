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
            "Diagnóstico do Mercado Óptico Local": "north_compass.png",
            "Diagnóstico Estratégico": "north_meeting.png", 
            "Playbook Comercial": "north_structure.png",
            "Playbook de Processos": "north_structure.png",
            "Playbook de Treinamento": "north_meeting.png",
            "Onboarding Institucional": "north_compass.png",
            "Manual do Usuário": "crm-user-bg.png",
            "Apresentação Institucional": "north_compass.png",
            "Playbook BDR": "north_growth.png",
            "Oferta Principal": "north_structure.png",
            "Oferta Downsell": "north_structure.png",
            "Consultoria": "north_meeting.png",
            "O Custo da Inação": "north_growth.png",
            "Plano Essencial": "north_structure.png",
            "Manual de Onboarding": "north_meeting.png",
            "Scripts": "north_meeting.png",
            "Objeções": "north_meeting.png",
            "Academia": "north_growth.png"
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
