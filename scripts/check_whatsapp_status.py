import os
import psycopg2
from dotenv import load_dotenv
import json

def main():
    dotenv_path = os.path.join(os.getcwd(), '.env.production')
    load_dotenv(dotenv_path)
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        cur.execute("SELECT id, name, features FROM company ORDER BY id;")
        rows = cur.fetchall()
        
        print(f"Total Companies: {len(rows)}")
        print("-" * 50)
        for row in rows:
            company_id, name, features = row
            # features is already a dict when using psycopg2 with jsonb
            is_enabled = features.get('whatsapp', False) if features else False
            print(f"ID: {company_id:2} | WhatsApp: {str(is_enabled):5} | Name: {name}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
