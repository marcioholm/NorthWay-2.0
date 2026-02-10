import os
import sys

# 1. Add ROOT and NORTHWAY_CRM to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

crm_dir = os.path.join(root_dir, 'northway_crm')
if crm_dir not in sys.path:
    sys.path.append(crm_dir)

# 2. Import App
try:
    from northway_crm.app import app
except Exception as e:
    # Fail-safe error page
    from flask import Flask
    import traceback
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def boot_error(path):
        return f"<h1>Boot Error</h1><pre>{traceback.format_exc()}</pre>", 500
