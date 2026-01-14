import os
from supabase import create_client, Client

def init_supabase(app):
    url = app.config.get('SUPABASE_URL')
    key = app.config.get('SUPABASE_KEY')
    
    if not url or not key:
        return None
        
    return create_client(url, key)
