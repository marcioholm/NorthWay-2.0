import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from werkzeug.security import check_password_hash
from app import app
from models import User

def check_login():
    password = os.environ.get('MASTER_PASSWORD')
    if not password:
        print("Erro: variavel de ambiente MASTER_PASSWORD obrigatoria para teste de login.")
        sys.exit(1)

    with app.app_context():
        user = User.query.filter_by(email='master@northway.com').first()
        if not user:
             print("❌ User not found")
             return
             
        print(f"User found: {user.name}")
        print(f"Stored Hash: {user.password_hash}")
        
        is_valid = check_password_hash(user.password_hash, password)
        
        if is_valid:
            print("✅ Password CHECK PASS")
        else:
            print("❌ Password CHECK FAIL")

if __name__ == "__main__":
    check_login()
