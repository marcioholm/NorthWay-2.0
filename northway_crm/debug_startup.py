import sys
from unittest.mock import MagicMock

# Mock Depedency Modules
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.extras"] = MagicMock()
sys.modules["supabase"] = MagicMock()

# Attempt to load app
try:
    print("Attempting to import app...")
    from app import create_app
    print("App imported successfully.")
    
    app = create_app()
    print("App created successfully.")
    
except Exception as e:
    print(f"CRASH: {e}")
    import traceback
    traceback.print_exc()
