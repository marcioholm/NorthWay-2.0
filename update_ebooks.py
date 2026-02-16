import sys
import os

# Add project directory to path
sys.path.append(os.path.join(os.getcwd(), 'northway_crm'))

from app import create_app
from models import db, LibraryBook

app = create_app()

def update_ebooks():
    with app.app_context():
        # Ebooks to update
        ebooks_data = [
            {
                'route_name': 'docs.ebook_norte_pioneiro',
                'category': 'Apresentação',
                'cover_image': 'north_compass.png', 
                'title': 'Radar Solar: Norte Pioneiro',
                'description': 'Levantamento exclusivo sobre o potencial fotovoltaico no Norte do Paraná. TAM, Penetração e Oportunidades.'
            },
            {
                'route_name': 'docs.ebook_campos_gerais',
                'category': 'Apresentação',
                'cover_image': 'north_growth.png',
                'title': 'Radar Solar: Campos Gerais',
                'description': 'Mapeamento estratégico do mercado solar nos Campos Gerais. Dados de potencial industrial e residencial.'
            }
        ]

        for data in ebooks_data:
            book = LibraryBook.query.filter_by(route_name=data['route_name']).first()
            
            if book:
                print(f"Updating existing book: {book.title}")
                book.category = data['category']
                book.cover_image = data['cover_image']
                book.description = data['description'] # Ensure description is set
            else:
                print(f"Creating new book: {data['title']}")
                book = LibraryBook(
                    title=data['title'],
                    route_name=data['route_name'],
                    category=data['category'],
                    cover_image=data['cover_image'],
                    description=data['description'],
                    active=True
                )
                db.session.add(book)
        
        try:
            db.session.commit()
            print("Successfully updated ebook records!")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating records: {str(e)}")

if __name__ == "__main__":
    update_ebooks()
