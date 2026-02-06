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
        return f"""
        <h1>Boot Error</h1>
        <p>Could not import app from northway_crm.</p>
        <pre>{e}</pre>
        <h3>Traceback:</h3>
        <pre>{tb}</pre>
        <h3>Sys Path:</h3>
        <pre>{sys.path}</pre>
        """, 500
