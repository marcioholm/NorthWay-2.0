import os
from supabase import create_client
from dotenv import load_dotenv

def deploy_playbook():
    # Load environment variables
    env_path = "northway_crm/.env"
    load_dotenv(env_path)
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in .env")
        return

    supabase = create_client(url, key)
    
    # 1. Create the Library Book
    book_data = {
        "title": "PLAYBOOK DE BDR — NORTHWAY",
        "category": "Estratégia & Vendas",
        "description": "Manual estratégico de prospecção para BDRs. Foco em autoridade, processo e previsibilidade.",
        "content": "Manual interno premium para o time de BDR da Northway.",
        "route_name": "docs.presentation_playbook_bdr",
        "active": True
    }
    
    print(f"Registering book: {book_data['title']}...")
    
    # Check if exists
    existing = supabase.table("library_book").select("id").eq("title", book_data["title"]).execute()
    
    if existing.data:
        book_id = existing.data[0]["id"]
        print(f"Book already exists with ID: {book_id}. Updating...")
        supabase.table("library_book").update(book_data).eq("id", book_id).execute()
    else:
        res = supabase.table("library_book").insert(book_data).execute()
        book_id = res.data[0]["id"]
        print(f"Created new book with ID: {book_id}")

    # 2. Associate with all existing companies
    print("Associating with all companies...")
    companies = supabase.table("company").select("id").execute()
    
    associations = []
    for comp in companies.data:
        associations.append({
            "company_id": comp["id"],
            "book_id": book_id
        })
    
    if associations:
        # Clear existing associations to avoid duplicates if re-running
        supabase.table("library_book_company_association").delete().eq("book_id", book_id).execute()
        # Insert new ones
        supabase.table("library_book_company_association").insert(associations).execute()
        print(f"Associated with {len(associations)} companies.")

    print("\n✅ PLAYBOOK DE BDR DEPLOYED SUCCESSFULLY.")

if __name__ == "__main__":
    deploy_playbook()
