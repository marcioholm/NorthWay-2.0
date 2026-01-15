from app import create_app
from models import db, LibraryBook, Company

app = create_app()

def migrate_library():
    with app.app_context():
        print("Starting Library Migration...")
        
        # 1. Create Tables if they don't exist (ensure new model is picked up)
        db.create_all()
        print("Database tables ensured.")
        
        # 2. Define Initial Books (from hardcoded HTML)
        initial_books = [
            {
                'title': 'Diagnóstico Estratégico',
                'description': 'Análise completa para Óticas 2026.',
                'category': 'Vendas',
                'route_name': 'docs.presentation_consultancy',
                'cover_image': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=1000', # Placeholder or keep icon logic in template
                'active': True
            },
            {
                'title': 'Apresentação Institucional',
                'description': 'Marketing com Direção - Quem somos e o que fazemos.',
                'category': 'Institucional',
                'route_name': 'docs.presentation_institutional',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Oferta Principal',
                'description': 'Estrutura Completa da Proposta Comercial.',
                'category': 'Vendas',
                'route_name': 'docs.presentation_offer_main',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Plano Essencial (Downsell)',
                'description': 'Alternativa de proposta para recuperação.',
                'category': 'Vendas',
                'route_name': 'docs.presentation_offer_downsell',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Manual de Onboarding',
                'description': 'Guia operacional para início de jornada.',
                'category': 'Processos',
                'route_name': 'docs.user_manual',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Scripts & Técnicas',
                'description': 'Roteiros de vendas e técnicas de fechamento.',
                'category': 'Vendas',
                'route_name': 'docs.playbook_comercial',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Objeções & SDR',
                'description': 'Matriz de objeções e guia para pré-vendas.',
                'category': 'Processos',
                'route_name': 'docs.playbook_processos',
                'cover_image': None,
                'active': True
            },
            {
                'title': 'Academia de Treinamento',
                'description': 'Training & Scripts area.',
                'category': 'Treinamento',
                'route_name': 'docs.playbook_treinamento',
                'cover_image': None,
                'active': True
            }
        ]
        
        # 3. Fetch All Companies (to grant initial access)
        all_companies = Company.query.all()
        print(f"Found {len(all_companies)} companies to grant access.")
        
        count = 0
        for data in initial_books:
            existing = LibraryBook.query.filter_by(route_name=data['route_name']).first()
            if not existing:
                print(f"Creating book: {data['title']}")
                book = LibraryBook(
                    title=data['title'],
                    description=data['description'],
                    category=data['category'],
                    route_name=data['route_name'],
                    cover_image=data.get('cover_image'),
                    active=data['active']
                )
                
                # Grant access to ALL current companies
                for comp in all_companies:
                    book.allowed_companies.append(comp)
                
                db.session.add(book)
                count += 1
            else:
                print(f"Book already exists: {data['title']}")
                # Optional: Ensure companies have access if missing?
                # for comp in all_companies:
                #     if comp not in existing.allowed_companies:
                #         existing.allowed_companies.append(comp)
        
        db.session.commit()
        print(f"Migration Complete. Added {count} new books.")

if __name__ == "__main__":
    migrate_library()
