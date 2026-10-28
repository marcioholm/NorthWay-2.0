import sys
import os
# Add parent dir to path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from werkzeug.security import generate_password_hash
from app import app, db
from models import User

def reset_password():
    new_password = os.environ.get('MASTER_PASSWORD')
    if not new_password:
        print("Erro: variavel de ambiente MASTER_PASSWORD obrigatoria para resetar senha.")
        sys.exit(1)

    with app.app_context():
        # Find master user
        user = User.query.filter_by(email='master@northway.com').first()
        if user:
            print(f"Found user: {user.name}")
            user.password_hash = generate_password_hash(new_password)
            user.is_super_admin = True # Ensure permissions
            db.session.commit()
            print("✅ Senha do Super Admin atualizada com sucesso a partir de MASTER_PASSWORD.")
        else:
            print("❌ User master@northway.com not found.")

if __name__ == "__main__":
    reset_password()
