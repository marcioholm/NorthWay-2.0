import os
import sys

# Add the parent directory (project root) to sys.path
# so that 'app.py' and other modules can be imported.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    print("🚀 STARTING APP IMPORT...")
    from app import app
    print("✅ APP IMPORT SUCCESSFUL")
except Exception as e:
    import traceback
    err_msg = traceback.format_exc()
    print(f"CRITICAL ERROR STARTING APP: {err_msg}")
    
    # Inline Fallback App
    from flask import Flask
    app = Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<h1>⚠️ CRITICAL STARTUP ERROR</h1><pre>{err_msg}</pre>", 500
        
    @app.route('/ping')
    def ping(): return "pong_critical_fallback"

# Vercel Serverless Function Entry Point
# This works by exposing the WSGI app as a variable named 'app'
# which Vercel's Python runtime automatically picks up.
