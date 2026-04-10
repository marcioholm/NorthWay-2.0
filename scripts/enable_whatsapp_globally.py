import os
import psycopg2
from dotenv import load_dotenv

def main():
    # Load environment variables from .env.production
    dotenv_path = os.path.join(os.getcwd(), '.env.production')
    if not os.path.exists(dotenv_path):
        print(f"Error: {dotenv_path} not found.")
        return

    load_dotenv(dotenv_path)
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("Error: DATABASE_URL not found in environment.")
        return

    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        print("Updating companies features...")
        
        # SQL to set whatsapp feature to true globally
        # jsonb_set handles the nested update
        # COALESCE handle null features
        sql = """
        UPDATE company 
        SET features = jsonb_set(COALESCE(features, '{}'::jsonb), '{whatsapp}', 'true'::jsonb)
        WHERE (features->>'whatsapp') IS DISTINCT FROM 'true';
        """
        
        cur.execute(sql)
        row_count = cur.rowcount
        
        conn.commit()
        print(f"Successfully enabled WhatsApp for {row_count} companies.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
