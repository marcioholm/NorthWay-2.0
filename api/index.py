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
    # Core
    import models
    import app
    import database_sync
    import utils
    import utils.crypto
    import services.supabase_service
    
    # Blueprints/Routes
    import auth
    import master
    import routes.financial
    import routes.financial_strategic
    import routes.docs
    import routes.goals
    import routes.prospecting
    import routes.internal_api
    import routes.integrations
    import routes.admin
    import routes.ai_settings
    import routes.api_debug
    import routes.jobs
    import routes.api_extension
    import routes.whatsapp
    import routes.webhook_whatsapp
    import routes.clients
    import routes.leads
    import routes.leads_enrichment
    import routes.contracts
    import routes.dashboard
    import routes.tasks
    import routes.templates
    import routes.checklists
    import routes.notifications
    import routes.roles
    import routes.billing
    import routes.service_orders
    import routes.pdf_routes
    import routes.financial_payable
    import routes.commercial_performance
    import routes.matrix_routes
    import routes.crepi_routes
    import routes.swot_routes
    import routes.marketing
    import routes.api_v1
    
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
except ImportError as e:
    # We ignore ImportErrors here as these are just for the builder
    # but we print it to stderr for debugging in Vercel logs if needed
    print(f"⚠️ Dummy import failed: {e}")
    pass

# 3. Create App Instance
def get_app():
    try:
        from app import create_app
        return create_app()
    except Exception as e:
        import traceback
        traceback.print_exc() # Print to Vercel logs (stdout/stderr)
        # Capture error for closure
        error_msg = str(e)
        tb_str = traceback.format_exc()
        # Fail-safe error page
        from flask import Flask
        error_app = Flask(__name__)
        
        # Log to stderr so it shows up in Vercel Logs
        print(f"🔥 BOOT ERROR: {e}")
        traceback.print_exc()
        
        error_details = str(e) + "\n\n" + traceback.format_exc()
        
        @error_app.route('/', defaults={'path': ''})
        @error_app.route('/<path:path>')
        def boot_error(path):
            return f"""
            <div style="font-family: sans-serif; padding: 40px; line-height: 1.6; max-width: 800px; margin: 0 auto;">
                <h1 style="color: #e53e3e;">🔥 Boot Error</h1>
                <p>The application failed to start correctly. This usually happens due to missing environment variables or database connection issues.</p>
                <div style="background: #f7fafc; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; overflow-x: auto;">
                    <pre style="font-size: 14px; margin: 0;">{error_details}</pre>
                </div>
            </div>
            """, 500
        return error_app

app = get_app()
application = app # Standard alias for Vercel/WSGI
