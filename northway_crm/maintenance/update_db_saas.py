from sqlalchemy import text
from app import create_app, db

def update_db_saas():
    app = create_app()
    with app.app_context():
        print("--- Updating Schema for SaaS ---")
        connection = db.engine.connect()
        trans = connection.begin()
        
        columns = [
            ("cpf_cnpj", "VARCHAR(20)"),
            ("subscription_id", "VARCHAR(50)"),
            ("subscription_status", "VARCHAR(20) DEFAULT 'inactive'"),
            ("plan_type", "VARCHAR(20) DEFAULT 'free'"),
        ]
        
        for col_name, col_type in columns:
            try:
                # SQLite syntax for ADD COLUMN
                # Note: "IF NOT EXISTS" for ADD COLUMN is only supported in very new SQLite versions.
                # We use try/except for robust fallback on older versions/drivers.
                sql = text(f'ALTER TABLE company ADD COLUMN {col_name} {col_type}')
                connection.execute(sql)
                print(f"✅ Added column: {col_name}")
            except Exception as e:
                # Check for "duplicate column" (sqlite) or "already exists" (postgres)
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"ℹ️ Column {col_name} already exists.")
                else:
                    print(f"❌ Error adding {col_name}: {e}")
        
        trans.commit()
        connection.close()
        print("--- SaaS Schema Update Complete ---")

if __name__ == "__main__":
    update_db_saas()
