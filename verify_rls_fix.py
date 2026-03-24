import os
import sys
from sqlalchemy import create_engine, text

def verify():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        from dotenv import load_dotenv
        load_dotenv('northway_crm/.env.production')
        db_url = os.getenv('DATABASE_URL')

    if not db_url:
        print("❌ ERROR: DATABASE_URL not found.")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            print("🔍 Checking RLS status of tables...")
            check_rls_sql = """
            SELECT 
                relname as table_name, 
                relrowsecurity as rls_enabled
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' 
            AND relname IN ('role', 'pipeline', 'integration', 'whats_app_message', 'quick_message', 
                           'process_template', 'financial_category', 'nfse_log', 'user', 'pipeline_stage')
            """
            result = conn.execute(text(check_rls_sql))
            for row in result:
                status = "✅ ENABLED" if row.rls_enabled else "❌ DISABLED"
                print(f"Table {row.table_name:20}: {status}")

            print("\n🔍 Checking for policies...")
            check_policies_sql = """
            SELECT tablename, policyname, roles, cmd, qual
            FROM pg_policies
            WHERE schemaname = 'public'
            AND tablename IN ('role', 'pipeline', 'integration', 'whats_app_message', 'quick_message', 
                             'process_template', 'financial_category', 'nfse_log', 'user', 'pipeline_stage')
            """
            result = conn.execute(text(check_policies_sql))
            policies_count = 0
            for row in result:
                print(f"Policy: {row.policyname} on {row.tablename}")
                policies_count += 1
            
            if policies_count > 0:
                print(f"\n✅ Found {policies_count} policies applied.")
            else:
                print("\n❌ No policies found!")

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify()
