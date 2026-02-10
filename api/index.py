import os
import sys

# 1. Add ROOT to sys.path (to find 'northway_crm' package)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 2. Add NORTHWAY_CRM to sys.path (so 'from models import...' works inside app.py)
crm_dir = os.path.join(root_dir, 'northway_crm')
if crm_dir not in sys.path:
    sys.path.append(crm_dir)

try:
    # 3. Import Application Factory
    # We must ensure that any error during IMPORT or CREATION is caught.
    from northway_crm.app import app
    
except Exception as e:
    # Diagnostic Fail-Safe
    from flask import Flask
    import traceback
    app = Flask(__name__)
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        tb = traceback.format_exc()
        try:
            import os
            env_vars = dict(os.environ)
            # Mask secrets
            for k in env_vars:
                if 'KEY' in k or 'SECRET' in k or 'PASSWORD' in k or 'URI' in k:
                    env_vars[k] = '***'
        except:
            env_vars = "Could not read env"
            
        return f"""
        <html>
        <head><title>Boot Error</title></head>
        <body style="font-family: monospace; padding: 20px;">
            <h1 style="color: red;">CRITICAL BOOT ERROR</h1>
            <p>The application could not start due to an error during import.</p>
            
            <h3>Exception:</h3>
            <pre style="background: #eee; padding: 10px;">{str(e)}</pre>
            
            <h3>Traceback:</h3>
            <pre style="background: #eee; padding: 10px;">{tb}</pre>
            
            <h3>Debug Context:</h3>
            <ul>
                <li><strong>CWD:</strong> {os.getcwd()}</li>
                <li><strong>Sys Path:</strong> {sys.path}</li>
            </ul>
        </body>
        </html>
        """, 500
