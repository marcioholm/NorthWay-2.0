import os
import sys

# Ensure the root directory (where app.py lives) is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Add vendor directory for dependencies
vendor_dir = os.path.join(root_dir, 'vendor')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

# Explicit top-level import
from app import app as application

# Re-assign to standard 'app' name
app = application

