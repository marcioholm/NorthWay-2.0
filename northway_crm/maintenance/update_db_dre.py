from app import create_app
from models import db, FinancialCategory, Company

app = create_app()

def update_db():
    with app.app_context():
        # Create tables if not exist
        db.create_all()
        
        # Seed categories for all companies
        companies = Company.query.all()
        
        default_categories = [
            {'name': 'Custos de Serviços (CMV/CSP)', 'type': 'cost'},
            {'name': 'Comissões de Vendas', 'type': 'cost'},
            {'name': 'Despesas com Pessoal', 'type': 'expense'},
            {'name': 'Marketing e Publicidade', 'type': 'expense'},
            {'name': 'Tecnologia e Software', 'type': 'expense'},
            {'name': 'Aluguel e Estrutura', 'type': 'expense'},
            {'name': 'Impostos e Taxas', 'type': 'expense'},
            {'name': 'Despesas Administrativas', 'type': 'expense'},
            {'name': 'Outras Despesas', 'type': 'expense'}
        ]
        
        for company in companies:
            print(f"Checking categories for company: {company.name}")
            for cat_data in default_categories:
                exists = FinancialCategory.query.filter_by(
                    company_id=company.id, 
                    name=cat_data['name']
                ).first()
                
                if not exists:
                    print(f"  Adding category: {cat_data['name']}")
                    new_cat = FinancialCategory(
                        name=cat_data['name'],
                        type=cat_data['type'],
                        is_default=True,
                        company_id=company.id
                    )
                    db.session.add(new_cat)
        
        db.session.commit()
        print("Database updated for DRE successfully!")

if __name__ == "__main__":
    update_db()
