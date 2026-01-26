from app import create_app, db
import os
import sys

def setup():
    app = create_app()
    with app.app_context():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        print(f"📡 SQLALCHEMY_DATABASE_URI: {uri}")
        
        if 'postgresql' not in uri:
            print("❌ ERRO: A URI do banco de dados não parece ser de um PostgreSQL (Supabase).")
            print("Certifique-se de que a DATABASE_URL esteja configurada corretamente no ambiente.")
            return

        print("🔨 Criando tabelas no Supabase...")
        try:
            db.create_all()
            print("✅ Tabelas criadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar tabelas: {e}")

if __name__ == "__main__":
    setup()
