import os
import psycopg2
from dotenv import load_dotenv
import json

def register_presentation():
    # Load env
    dotenv_path = os.path.join(os.getcwd(), '.env.production')
    load_dotenv(dotenv_path)
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        title = "Posicionamento Comercial — M&K Fitness Center"
        desc = "Apresentação estratégica para academias femininas, focada em mulheres reais, acolhimento e jornada da aluna."
        route = "docs.presentation_mk_fitness"
        category = "Apresentação"

        # Check if title exists
        cur.execute("SELECT id FROM library_book WHERE title = %s;", (title,))
        row = cur.fetchone()
        
        if row:
            book_id = row[0]
            cur.execute("""
                UPDATE library_book 
                SET description = %s, route_name = %s 
                WHERE id = %s;
            """, (desc, route, book_id))
            print(f"Updated existing book with ID: {book_id}")
        else:
            cur.execute("""
                INSERT INTO library_book (title, description, category, route_name, active, created_at)
                VALUES (%s, %s, %s, %s, true, NOW())
                RETURNING id;
            """, (title, desc, category, route))
            book_id = cur.fetchone()[0]
            print(f"Registered new book with ID: {book_id}")

        # 2. Grant access to all companies
        cur.execute("SELECT id FROM company;")
        companies = cur.fetchall()
        
        for company in companies:
            # Check if association already exists to avoid conflict
            cur.execute("""
                INSERT INTO library_book_company_association (book_id, company_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (book_id, company[0]))
        
        conn.commit()
        print(f"Access granted to {len(companies)} companies.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    register_presentation()
