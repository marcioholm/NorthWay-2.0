import os
import sys

# 1. Add ROOT and NORTHWAY_CRM to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

crm_dir = os.path.join(root_dir, 'northway_crm')
if crm_dir not in sys.path:
    sys.path.append(crm_dir)

# 2. Add explicit dummy imports to force Vercel's Serverless Builder to package the folders
try:
    import northway_crm.models
    import northway_crm.services.supabase_service
    import northway_crm.routes.ai_settings
except ImportError:
    pass

# 3. Create App Instance
def get_app():
    try:
        from northway_crm.app import create_app
        return create_app()
    except Exception as e:
        # Fail-safe error page
        from flask import Flask
        import traceback
        error_app = Flask(__name__)
        
        error_details = str(e) + "\n\n" + traceback.format_exc()
        
        @error_app.route('/', defaults={'path': ''})
        @error_app.route('/<path:path>')
        def boot_error(path):
            return f"<h1>🔥 Boot Error</h1><pre>{error_details}</pre>", 500
        return error_app

app = get_app()
application = app # Standard alias for Vercel/WSGI
