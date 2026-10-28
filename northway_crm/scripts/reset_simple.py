import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from werkzeug.security import generate_password_hash
from app import app, db
from models import User

def reset_simple():
    new_password = os.environ.get('MASTER_PASSWORD')
    if not new_password:
        print("Erro: variavel de ambiente MASTER_PASSWORD obrigatoria para resetar senha.")
        sys.exit(1)

    with app.app_context():
        user = User.query.filter_by(email='master@northway.com').first()
        if user:
            user.password_hash = generate_password_hash(new_password)
            user.is_super_admin = True
            db.session.commit()
            print("✅ Senha atualizada com sucesso a partir de MASTER_PASSWORD.")
        else:
            print("❌ User not found")

if __name__ == "__main__":
    reset_simple()
