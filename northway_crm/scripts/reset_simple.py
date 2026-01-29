import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from werkzeug.security import generate_password_hash
from app import app, db
from models import User

def reset_simple():
    with app.app_context():
        user = User.query.filter_by(email='master@northway.com').first()
        if user:
            user.password_hash = generate_password_hash('admin123')
            user.is_super_admin = True
            db.session.commit()
            print("✅ Password reset to: admin123")
        else:
            print("❌ User not found")

if __name__ == "__main__":
    reset_simple()
