from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE task ADD COLUMN completed_at DATETIME"))
            conn.commit()
            print("Column 'completed_at' added successfully to 'task' table.")
    except Exception as e:
        print(f"Error (column might already exist): {e}")
