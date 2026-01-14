from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Add niche column to client table
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE client ADD COLUMN niche VARCHAR(100)"))
            conn.commit()
        print("Successfully added 'niche' column to Client table.")
    except Exception as e:
        print(f"Error (might already exist): {e}")
