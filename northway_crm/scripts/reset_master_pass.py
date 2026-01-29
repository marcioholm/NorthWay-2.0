import sys
import os
# Add parent dir to path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from werkzeug.security import generate_password_hash
from app import app, db
from models import User

def reset_password():
    with app.app_context():
        # Find master user
        user = User.query.filter_by(email='master@northway.com').first()
        if user:
            print(f"Found user: {user.name}")
            user.password_hash = generate_password_hash('NorthWay@Master2024')
            user.is_super_admin = True # Ensure permissions
            db.session.commit()
            print("✅ Password reset to: NorthWay@Master2024")
        else:
            print("❌ User master@northway.com not found.")

if __name__ == "__main__":
    reset_password()
