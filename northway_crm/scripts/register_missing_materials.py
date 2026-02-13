import sys
import os

# Add parent dir to path to import app factory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, LibraryBook, Company

def register_materials():
    app = create_app()
    with app.app_context():
        materials = [
            {
                "title": "Máquina Comercial Digital (Oferta Principal)",
                "route_name": "docs.presentation_offer_main",
                "category": "Vendas",
                "description": "Estrutura completa da máquina comercial digital para aquisição previsível."
            },
            {
                "title": "Estrutura Comercial Essencial (Downsell)",
                "route_name": "docs.presentation_offer_downsell",
                "category": "Vendas",
                "description": "Versão essencial para estruturação comercial inicial."
            },
            {
                "title": "Ebook: Os Pilares do Marketing",
                "route_name": "docs.ebook_marketing_pillars",
                "category": "Ebook",
                "description": "Guia fundamental sobre os pilares estratégicos do marketing moderno."
            },
            {
                "title": "Ebook Institucional NorthWay",
                "route_name": "docs.ebook_institutional",
                "category": "Ebook",
                "description": "Apresentação detalhada da visão e metodologia NorthWay."
            },
            {
                "title": "Growth Framework",
                "route_name": "docs.presentation_growth_framework",
                "category": "Estratégia",
                "description": "Framework estratégico para aceleração de crescimento."
            },
            {
                "title": "PLAYBOOK DE BDR — NORTHWAY",
                "route_name": "docs.presentation_playbook_bdr",
                "category": "Estratégia & Vendas",
                "description": "Manual completo para operação de Business Development Representative."
            }
        ]

        # Get target company (ID 35 from user screenshot)
        company_ids = [35, 6] # Company 6 is usually the admin company in seeds
        target_companies = Company.query.filter(Company.id.in_(company_ids)).all()

        for mat in materials:
            book = LibraryBook.query.filter_by(route_name=mat["route_name"]).first()
            if not book:
                book = LibraryBook(
                    title=mat["title"],
                    route_name=mat["route_name"],
                    category=mat["category"],
                    description=mat["description"],
                    active=True
                )
                db.session.add(book)
                print(f"✅ Created: {mat['title']}")
            else:
                book.title = mat["title"]
                book.category = mat["category"]
                book.description = mat["description"]
                print(f"ℹ️ Updated: {mat['title']}")
            
            db.session.commit()

            # Associate with target companies if not already
            for comp in target_companies:
                if comp not in book.allowed_companies:
                    book.allowed_companies.append(comp)
                    print(f"   - Linked to company: {comp.name} (ID: {comp.id})")
        
        db.session.commit()
        print("\n✨ All materials registered and linked successfully!")

if __name__ == "__main__":
    register_materials()
