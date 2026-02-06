import os
import sys

# 1. Add NORTHWAY_CRM to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from app import app
except ImportError:
    # If root_dir is actually the parent folder (northway_crm),
    # then 'app.py' is in root_dir.
    try:
        from northway_crm.app import app
    except ImportError:
        # Fallback for when 'northway_crm' is root (vercel project settings)
        sys.path.append(os.path.dirname(os.path.abspath(__file__))) # current dir/api
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # northway_crm
        try:
             from app import app
        except Exception as e:
                from flask import Flask
                import traceback
                app = Flask(__name__)
                @app.route('/', defaults={'path': ''})
                @app.route('/<path:path>')
                def catch_all(path):
                    return f"<h1>Start Error (Nested API)</h1><pre>{traceback.format_exc()}</pre>", 500
