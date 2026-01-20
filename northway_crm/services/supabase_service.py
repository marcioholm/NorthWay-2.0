import os
from supabase import create_client, Client

def init_supabase(app):
    url = app.config.get('SUPABASE_URL')
    # Use service role key if available for backend operations, fallback to anon key
    key = app.config.get('SUPABASE_SERVICE_ROLE_KEY') or app.config.get('SUPABASE_KEY')
    
    if not url or not key:
        return None
        
    return create_client(url, key)
