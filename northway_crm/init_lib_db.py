
from app import create_app, db
from models import template_company_association

app = create_app()

with app.app_context():
    # Only create the new table
    try:
        template_company_association.create(db.engine)
        print("Created template_company_association table successfully.")
    except Exception as e:
        print(f"Error creating table (might already exist): {e}")
