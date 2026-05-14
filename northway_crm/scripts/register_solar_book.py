import os
import sys
from sqlalchemy import create_engine, text

# Get DB URL from environment
db_url = os.getenv('DATABASE_URL')
if not db_url:
    for env_file in [".env.production", ".env.local", ".env", "northway_crm/.env"]:
        if os.path.exists(env_file):
            print(f"📄 Found env file: {env_file}")
            with open(env_file, "r") as f:
                for line in f:
                    if "DATABASE_URL" in line:
                        try:
                            val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                db_url = val
                                break
                        except:
                            continue
            if db_url: break

if not db_url:
    if os.path.exists('crm.db'):
        db_url = 'sqlite:///crm.db'
    elif os.path.exists('northway_crm/crm.db'):
        db_url = 'sqlite:///northway_crm/crm.db'

if not db_url:
    print("❌ DATABASE_URL not found.")
    sys.exit(1)

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

print(f"🔌 Connecting to database...")
engine = create_engine(db_url)

target_email = "marciogholmm@gmail.com"
title = "Apresentação Comercial — Energia Solar"
desc = "Apresentação estratégica de alta performance para o setor fotovoltaico, focada em ROI, economia e sustentabilidade."
route = "docs.presentation_solar"

is_postgres = 'postgresql' in db_url

with engine.connect() as conn:
    print(f"🔍 Searching for user: {target_email}")
    user_table = '"user"' if is_postgres else 'user'
    
    try:
        res = conn.execute(text(f"SELECT id, company_id FROM {user_table} WHERE email = :email"), {"email": target_email}).fetchone()
    except Exception as e:
        user_table = 'user' if is_postgres else '"user"'
        res = conn.execute(text(f"SELECT id, company_id FROM {user_table} WHERE email = :email"), {"email": target_email}).fetchone()
    
    if not res:
        print(f"⚠️ User {target_email} not found. Fallback to Company ID 6 (NorthWay Default).")
        company_id = 6
    else:
        user_id, company_id = res
        print(f"✅ Found user ID {user_id}, Company ID {company_id}")

    book_res = conn.execute(text("SELECT id FROM library_book WHERE route_name = :route"), {"route": route}).fetchone()
    
    if not book_res:
        print(f"🌱 Creating new library book: {title}")
        # Use Python booleans for compatibility with both SQLite (0/1) and Postgres (true/false) via SQLAlchemy
        conn.execute(text("""
            INSERT INTO library_book (title, description, category, route_name, active, created_at)
            VALUES (:title, :desc, 'Apresentação', :route, :active, CURRENT_TIMESTAMP)
        """), {"title": title, "desc": desc, "route": route, "active": True})
        
        if is_postgres:
            book_id = conn.execute(text("SELECT id FROM library_book WHERE route_name = :route"), {"route": route}).scalar()
        else:
            book_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
    else:
        book_id = book_res[0]
        print(f"ℹ️ Book already exists (ID: {book_id}). Updating description...")
        conn.execute(text("UPDATE library_book SET description = :desc WHERE id = :id"), {"desc": desc, "id": book_id})

    assoc_res = conn.execute(text("SELECT 1 FROM library_book_company_association WHERE book_id = :b_id AND company_id = :c_id"),
                             {"b_id": book_id, "c_id": company_id}).fetchone()
    
    if not assoc_res:
        print(f"🔗 Linking book to Company {company_id}...")
        conn.execute(text("INSERT INTO library_book_company_association (book_id, company_id) VALUES (:b_id, :c_id)"),
                     {"b_id": book_id, "c_id": company_id})
    else:
        print(f"ℹ️ Book already linked to Company {company_id}.")

    conn.commit()
    print("\n✅ Registration completed successfully!")
