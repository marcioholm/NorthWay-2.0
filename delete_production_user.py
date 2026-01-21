import os
from supabase import create_client

# Load from .env manually to be safe
env_path = "northway_crm/.env"
env_vars = {}
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env_vars[k] = v

url = env_vars.get("SUPABASE_URL")
key = env_vars.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing.")
    exit(1)

supabase = create_client(url, key)
email = "marciogholmm@gmail.com"

print(f"--- Thorough Deleting User: {email} from Production ---")

try:
    # 1. Get User
    res = supabase.table("user").select("id, company_id").eq("email", email).execute()
    
    if res.data:
        user_id = res.data[0]['id']
        company_id = res.data[0]['company_id']
        print(f"Found user ID {user_id}, Company {company_id}")
        
        # Unassign from leads first
        supabase.table("lead").update({"assigned_to_id": None}).eq("assigned_to_id", user_id).execute()

        # 2. Clean up Company data if we are deleting the company
        if company_id:
            others = supabase.table("user").select("id").eq("company_id", company_id).execute()
            if len(others.data) <= 1:
                print(f"Cleaning all data for Company {company_id}...")
                
                # Delete in order of dependencies
                supabase.table("client_checklist").delete().eq("company_id", company_id).execute()
                supabase.table("notification").delete().eq("company_id", company_id).execute()
                supabase.table("transaction").delete().eq("company_id", company_id).execute()
                supabase.table("contract").delete().eq("company_id", company_id).execute()
                supabase.table("client").delete().eq("company_id", company_id).execute()
                
                # Leads and interactions
                supabase.table("interaction").delete().eq("company_id", company_id).execute()
                supabase.table("task").delete().eq("company_id", company_id).execute()
                supabase.table("lead").delete().eq("company_id", company_id).execute()
                
                # Pipelines and stages
                supabase.table("pipeline_stage").delete().eq("company_id", company_id).execute()
                supabase.table("user_pipeline_association").delete().eq("user_id", user_id).execute() # Also handled later but safe here
                supabase.table("pipeline").delete().eq("company_id", company_id).execute()
                
                # Settings
                supabase.table("integration").delete().eq("company_id", company_id).execute()
                supabase.table("financial_category").delete().eq("company_id", company_id).execute()
                supabase.table("role").delete().eq("company_id", company_id).execute()
                supabase.table("goal").delete().eq("company_id", company_id).execute()
                supabase.table("process_template").delete().eq("company_id", company_id).execute()
                supabase.table("contract_template").delete().eq("company_id", company_id).execute()
                
                # 3. Delete from public.user
                supabase.table("user").delete().eq("id", user_id).execute()
                
                # 4. Delete Company
                supabase.table("company").delete().eq("id", company_id).execute()
                print("Company and all data deleted.")
            else:
                print(f"Company {company_id} has {len(others.data)} users. Only deleting user.")
                supabase.table("user_pipeline_association").delete().eq("user_id", user_id).execute()
                supabase.table("notification").delete().eq("user_id", user_id).execute()
                supabase.table("user").delete().eq("id", user_id).execute()
        else:
            supabase.table("user_pipeline_association").delete().eq("user_id", user_id).execute()
            supabase.table("user").delete().eq("id", user_id).execute()
            print("User deleted (no company linked).")
    else:
        print("User not found in public.user.")

    # 5. Delete from Auth
    auth_users = supabase.auth.admin.list_users()
    for u in auth_users:
        if u.email == email:
            print(f"Found in auth.users: UUID {u.id}. Deleting...")
            supabase.auth.admin.delete_user(u.id)
            print("Deleted from auth.users.")
            break
    else:
        print("Not found in auth.users.")

    print("\n✅ User cleanup complete.")

except Exception as e:
    print(f"❌ Error during cleanup: {e}")
