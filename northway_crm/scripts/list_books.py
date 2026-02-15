import sys
import os

# Add parent dir to path to import app factory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, LibraryBook

def list_books():
    app = create_app()
    with app.app_context():
        books = LibraryBook.query.all()
        print("-" * 50)
        print(f"{'ID':<4} | {'Title':<30} | {'Route':<30}")
        print("-" * 50)
        for b in books:
            print(f"{b.id:<4} | {b.title:<30} | {b.route_name:<30}")
        print("-" * 50)

if __name__ == "__main__":
    list_books()
