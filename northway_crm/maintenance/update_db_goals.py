from app import create_app
from models import db, Goal

app = create_app()

def update_db():
    with app.app_context():
        # Create tables if not exist
        db.create_all()
        print("Database updated for Goals successfully!")

if __name__ == "__main__":
    update_db()
