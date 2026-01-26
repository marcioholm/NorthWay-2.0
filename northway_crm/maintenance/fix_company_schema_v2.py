from app import create_app, db
from sqlalchemy import text

def fix_schema():
    print("Fixing Company Schema...")
    app = create_app()
    with app.app_context():
        with db.engine.connect() as conn:
            # 1. cpf_cnpj
            try:
                conn.execute(text("ALTER TABLE company ADD COLUMN cpf_cnpj VARCHAR(20)"))
                print("Added cpf_cnpj")
            except Exception as e:
                print(f"Skip cpf_cnpj: {e}")

            # 2. subscription_id
            try:
                conn.execute(text("ALTER TABLE company ADD COLUMN subscription_id VARCHAR(50)"))
                print("Added subscription_id")
            except Exception as e:
                print(f"Skip subscription_id: {e}")

            # 3. subscription_status
            try:
                conn.execute(text("ALTER TABLE company ADD COLUMN subscription_status VARCHAR(20) DEFAULT 'inactive'"))
                print("Added subscription_status")
            except Exception as e:
                print(f"Skip subscription_status: {e}")

            # 4. plan_type
            try:
                conn.execute(text("ALTER TABLE company ADD COLUMN plan_type VARCHAR(20) DEFAULT 'free'"))
                print("Added plan_type")
            except Exception as e:
                print(f"Skip plan_type: {e}")
            
            # --- Transaction Fixes ---
            # 5. contact_uuid
            try:
                conn.execute(text("ALTER TABLE 'transaction' ADD COLUMN contact_uuid VARCHAR(36)"))
                print("Added contact_uuid to transaction")
            except Exception as e:
                print(f"Skip transaction.contact_uuid: {e}")

            # 6. asaas_id
            try:
                conn.execute(text("ALTER TABLE 'transaction' ADD COLUMN asaas_id VARCHAR(50)"))
                print("Added asaas_id to transaction")
            except Exception as e:
                print(f"Skip transaction.asaas_id: {e}")

            # 7. asaas_invoice_url
            try:
                conn.execute(text("ALTER TABLE 'transaction' ADD COLUMN asaas_invoice_url VARCHAR(500)"))
                print("Added asaas_invoice_url to transaction")
            except Exception as e:
                print(f"Skip transaction.asaas_invoice_url: {e}")

            # 8. installment_number
            try:
                conn.execute(text("ALTER TABLE 'transaction' ADD COLUMN installment_number INTEGER"))
                print("Added installment_number to transaction")
            except Exception as e:
                print(f"Skip transaction.installment_number: {e}")

            # 9. total_installments
            try:
                conn.execute(text("ALTER TABLE 'transaction' ADD COLUMN total_installments INTEGER"))
                print("Added total_installments to transaction")
            except Exception as e:
                print(f"Skip transaction.total_installments: {e}")

            # 10. cancellation_reason
            try:
                conn.execute(text("ALTER TABLE 'transaction' ADD COLUMN cancellation_reason TEXT"))
                print("Added cancellation_reason to transaction")
            except Exception as e:
                print(f"Skip transaction.cancellation_reason: {e}")

            conn.commit()
    print("Schema fixed.")

if __name__ == "__main__":
    fix_schema()
