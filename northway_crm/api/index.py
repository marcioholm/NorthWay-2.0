import os
import sys

# Add the parent directory (project root) to sys.path
# so that 'app.py' and other modules can be imported.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    print("🚀 STARTING APP IMPORT...")
    from app import app
    print("✅ APP IMPORT SUCCESSFUL")
    
    # [STARTUP HOOK] Seed Creative Data if missing (Vercel Ephemeral Fix)
    try:
        from app import app, db, User
        with app.app_context():
            # Check if admin exists using SQLAlchemy or raw SQL if preferred
            # Using raw script logic for robustness
            import sqlite3
            # We need to run the seed script logic. Importing it.
            # Assuming seed_creative_data is in the path
            from seed_creative_data import seed_creative_data
            
            # Check safely
            # Note: seed_creative_data uses 'crm.db'. In Vercel, this might be relative.
            # Ensure we are in the right dir or pass path?
            # app.config['SQLALCHEMY_DATABASE_URI'] usually is 'sqlite:///crm.db'
            
            # Simple check:
            conn = sqlite3.connect('crm.db')
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user WHERE email='Admin@northway.com.br'")
            if not cursor.fetchone():
                print("⚠️ [STARTUP] Admin not found. Running Creative Seeding...")
                seed_creative_data()
                print("✅ [STARTUP] Creative Seeding Done.")
            else:
                print("ℹ️ [STARTUP] Admin exists. Skipping seeding.")
            conn.close()
            
    except Exception as seed_err:
        print(f"⚠️ [STARTUP] Seeding check failed: {seed_err}")
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
