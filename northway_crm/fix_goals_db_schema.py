from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Checking Goal table schema...")
    try:
        # Try to select the column to see if it exists
        with db.engine.connect() as conn:
            conn.execute(text("SELECT min_new_sales FROM goal LIMIT 1"))
        print("Column 'min_new_sales' already exists.")
    except Exception as e:
        print(f"Column missing ({e}). Adding it now...")
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE goal ADD COLUMN min_new_sales FLOAT DEFAULT 0"))
                conn.commit()
            print("SUCCESS: Added 'min_new_sales' column.")
        except Exception as e2:
            print(f"FAILED to add column: {e2}")
