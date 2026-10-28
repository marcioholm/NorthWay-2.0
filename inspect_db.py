import os
import sys
import psycopg2

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("Erro: variavel de ambiente DATABASE_URL nao configurada.")
    sys.exit(1)

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    for t in ['company', 'tenant_ai_credentials']:
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{t}'
            ORDER BY ordinal_position;
        """)
        rows = cur.fetchall()
        print(f"\nTable: {t}")
        for r in rows:
            print(f"  Col: {r[0]}, Type: {r[1]}, Nullable: {r[2]}")
            
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
