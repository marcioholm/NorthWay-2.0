import sys
import os

# Add the project directory to the path so we can import models
sys.path.append('/Users/Marci.Holm/Applications/NorthWay-2.0/northway_crm')

from app import create_app
from models import db, LibraryBook

app = create_app()
with app.app_context():
    books = LibraryBook.query.all()
    print(f"Total books found: {len(books)}")
    for book in books:
        print(f"ID: {book.id} | Title: {book.title} | Active: {book.active} | Route: {book.route_name}")
