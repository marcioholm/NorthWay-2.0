import sys
import os

# Add northway_crm to path
sys.path.append(os.path.join(os.getcwd(), 'northway_crm'))

from northway_crm.app import create_app
from northway_crm.models import db, Company, LibraryBook

app = create_app()
with app.app_context():
    print("--- COMPANIES ---")
    companies = Company.query.all()
    for c in companies:
        print(f"ID: {c.id} | Name: {c.name}")
    
    print("\n--- BOOKS ---")
    books = LibraryBook.query.all()
    for b in books:
        print(f"ID: {b.id} | Title: {b.title} | Category: {b.category}")
