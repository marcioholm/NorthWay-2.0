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
    import northway_crm.models
    import northway_crm.app
    import northway_crm.database_sync
    import northway_crm.utils
    import northway_crm.utils.crypto
    import northway_crm.services.supabase_service
    
    # Blueprints/Routes
    import northway_crm.routes.auth
    import northway_crm.routes.master
    import northway_crm.routes.financial
    import northway_crm.routes.financial_strategic
    import northway_crm.routes.docs
    import northway_crm.routes.goals
    import northway_crm.routes.prospecting
    import northway_crm.routes.internal_api
    import northway_crm.routes.integrations
    import northway_crm.routes.admin
    import northway_crm.routes.ai_settings
    import northway_crm.routes.api_debug
    import northway_crm.routes.jobs
    import northway_crm.routes.api_extension
    import northway_crm.routes.whatsapp
    import northway_crm.routes.webhook_whatsapp
    import northway_crm.routes.clients
    import northway_crm.routes.leads
    import northway_crm.routes.leads_enrichment
    import northway_crm.routes.contracts
    import northway_crm.routes.dashboard
    import northway_crm.routes.tasks
    import northway_crm.routes.templates
    import northway_crm.routes.checklists
    import northway_crm.routes.notifications
    import northway_crm.routes.roles
    import northway_crm.routes.billing
    import northway_crm.routes.service_orders
    import northway_crm.routes.pdf_routes
    import northway_crm.routes.financial_payable
    import northway_crm.routes.commercial_performance
    import northway_crm.routes.matrix_routes
    import northway_crm.routes.crepi_routes
    import northway_crm.routes.swot_routes
    import northway_crm.routes.marketing
    import northway_crm.routes.api_v1
except ImportError as e:
    # We ignore ImportErrors here as these are just for the builder
    # but we print it to stderr for debugging in Vercel logs if needed
    print(f"⚠️ Dummy import failed: {e}")
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
