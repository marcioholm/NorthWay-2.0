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
    import services.form_service
    
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
    import routes.forms
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
    import routes.diagnostic_raiox
    
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
except Exception as e:
    # We ignore ImportErrors/InitErrors here as these are just for the builder
    # but we print it to stderr for debugging in Vercel logs if needed
    print(f"⚠️ Dummy import failed: {e}")
    pass

# 3. Create App Instance
def get_app():
    try:
        from app import app as crm_app
        return crm_app
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
        
        @error_app.route('/', defaults={'path': ''})
        @error_app.route('/<path:path>')
        def boot_error(path):
            return """
            <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Sistema Temporariamente Indisponível - NorthWay</title>
            </head>
            <body style="margin: 0; background-color: #0A0A0A; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; box-sizing: border-box;">
                <div style="max-width: 480px; text-align: center;">
                    <div style="font-size: 28px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 8px;">NORTH<span style="color: #FA0102;">WAY</span></div>
                    <h1 style="font-size: 20px; font-weight: 700; color: #F1F5F9; margin-top: 24px; margin-bottom: 12px;">Sistema Temporariamente Indisponível</h1>
                    <p style="font-size: 14px; color: #94A3B8; line-height: 1.6; margin-bottom: 24px;">Estamos realizando uma atualização no servidor. Por favor, recarregue a página ou tente novamente em alguns instantes.</p>
                    <a href="javascript:location.reload()" style="display: inline-block; background-color: #FA0102; color: #FFFFFF; text-decoration: none; font-size: 13px; font-weight: 600; padding: 10px 24px; border-radius: 8px;">Recarregar Página</a>
                </div>
            </body>
            </html>
            """, 500
        return error_app

app = get_app()
application = app # Standard alias for Vercel/WSGI
