import os
import sys
from services.supabase_service import init_supabase

supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    print("Erro: variaveis de ambiente SUPABASE_URL e SUPABASE_KEY sao obrigatorias.")
    sys.exit(1)

class MockApp:
    config = {
        'SUPABASE_URL': supabase_url,
        'SUPABASE_KEY': supabase_key
    }

print("Initializing Supabase Client...")
supabase = init_supabase(MockApp())

if supabase:
    print("Supabase Client initialized successfully.")
    try:
        print("Attempting connection test (sign in with invalid user)...")
        res = supabase.auth.sign_in_with_password({"email": "fake@email.com", "password": "fake"})
    except Exception as e:
        print(f"Connection made (expected error for invalid user): {e}")
        # If we got a response from the server (even 400), it means connection is good.
else:
    print("Failed to initialize Supabase Client.")
