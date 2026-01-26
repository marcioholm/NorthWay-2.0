from app import create_app, db
from models import QuickMessage
import sqlalchemy as sa

app = create_app()

def migrate():
    with app.app_context():
        inspector = sa.inspect(db.engine)
        if 'quick_message' not in inspector.get_table_names():
            print("Creating quick_message table...")
            QuickMessage.__table__.create(db.engine)
            print("Done.")
        else:
            print("quick_message table already exists.")

if __name__ == '__main__':
    migrate()
