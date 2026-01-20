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
    print(f"CRITICAL ERROR STARTING APP: {e}")
    traceback.print_exc()
    raise e

# Vercel Serverless Function Entry Point
# This works by exposing the WSGI app as a variable named 'app'
# which Vercel's Python runtime automatically picks up.
