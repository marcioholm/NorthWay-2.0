from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Running migration: Adding min_new_sales to Goal table...")
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE goal ADD COLUMN min_new_sales FLOAT DEFAULT 0"))
            conn.commit()
        print("Migration successful: Added min_new_sales column.")
    except Exception as e:
        print(f"Migration failed (maybe column exists?): {e}")
