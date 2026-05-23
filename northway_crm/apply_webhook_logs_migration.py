import sys
import os
from dotenv import load_dotenv

# Load production env
load_dotenv('.env.production')

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'northway_crm'))

from northway_crm.app import create_app
from models import db

def apply_migration(app):
    with app.app_context():
        print("🚀 Applying Webhook Logs Migration on Production DB...")
        db.create_all()
        print("✅ crm_webhook_logs table created successfully based on models.py")

if __name__ == "__main__":
    app = create_app()
    apply_migration(app)
