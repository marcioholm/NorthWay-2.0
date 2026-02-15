import os
import sys

# Add the app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

print("🔍 Starting Smoke Test...")

try:
    print("📦 Importing app.py...")
    from app import create_app
    print("✅ app.py imported successfully.")
except Exception as e:
    print(f"❌ Failed to import app.py: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("🚀 Creating app instance...")
    app = create_app()
    print("✅ App instance created successfully.")
except Exception as e:
    print(f"❌ Failed to create app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("🎉 Smoke Test PASSED!")
