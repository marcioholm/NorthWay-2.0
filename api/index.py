import os
import sys

# Add the project root to sys.path so we can find northway_crm
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add northway_crm to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'northway_crm'))

try:
    from northway_crm.app import app
except Exception as e:
    # Emergency Fallback
    from flask import Flask
    import traceback
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<h1>Start Error (Root API)</h1><pre>{traceback.format_exc()}</pre>", 500
