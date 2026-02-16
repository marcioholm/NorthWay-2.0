import os
import sys

# 1. Add NORTHWAY_CRM to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 2. Add Vendor directory (for fpdf2 on Vercel)
vendor_dir = os.path.join(root_dir, 'vendor')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir) # Prioritize vendor


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
                app = Flask(__name__)
                @app.route('/', defaults={'path': ''})
                @app.route('/<path:path>')
                def catch_all(path):
                    return "<h1>Sistema Indisponível</h1><p>Ocorreu um erro na inicialização. Por favor, tente novamente mais tarde.</p>", 500

