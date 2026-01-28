
from app import create_app
from models import db, User, Company, Client, Transaction, Expense, FinancialCategory, Contract, ContractTemplate, ROLE_ADMIN
from datetime import date, timedelta, datetime
import random
import json

app = create_app()

def seed_financial_demo():
    print("🚀 Seeding Financial Demo Data...")
    
    # 1. Get Target User/Company
    user = User.query.filter_by(email='admin@northway.com').first()
    if not user:
        print("❌ Admin user not found. Run seed_admin.py first.")
        return
        
    company = user.company
    print(f"🏢 Treating Company: {company.name}")
    
    # 2. Cleanup Existing Financial Data
    print("🧹 Cleaning old financial data...")
    Transaction.query.filter_by(company_id=company.id).delete()
    Expense.query.filter_by(company_id=company.id).delete()
    Contract.query.filter_by(company_id=company.id).delete()
    # Also clean templates if we are creating new ones or just ensure one exists
    # Client.query.filter_by(company_id=company.id).delete() 
    # Just reuse existing logic
    db.session.commit()
    
    # 3. Create Categories if missing
    cat_revenue = FinancialCategory.query.filter_by(company_id=company.id, type='revenue', name='Vendas').first()
    if not cat_revenue:
        cat_revenue = FinancialCategory(name='Vendas', type='revenue', company_id=company.id)
        db.session.add(cat_revenue)
        
    cat_exp_fixed = FinancialCategory.query.filter_by(company_id=company.id, type='expense', name='Despesas Fixas').first()
    if not cat_exp_fixed:
        cat_exp_fixed = FinancialCategory(name='Despesas Fixas', type='expense', company_id=company.id)
        db.session.add(cat_exp_fixed)
        
    cat_cost = FinancialCategory.query.filter_by(company_id=company.id, type='cost', name='Marketing').first()
    if not cat_cost:
        cat_cost = FinancialCategory(name='Marketing', type='cost', company_id=company.id)
        db.session.add(cat_cost)
        
    # Create Dummy Template
    template = ContractTemplate.query.filter_by(company_id=company.id).first()
    if not template:
        template = ContractTemplate(
            name="Contrato Padrão",
            description="Modelo padrão para serviços",
            content="<p>Conteúdo do contrato...</p>",
            company_id=company.id,
            user_id=user.id
        )
        db.session.add(template)
        
    db.session.commit()

    # 4. Create Fake Clients
    # Clean clients first to avoid duplicates
    Client.query.filter_by(company_id=company.id).delete()
    db.session.commit()

    clients_data = [
        {"name": "Tech Solutions Ltda", "niche": "Tecnologia"},
        {"name": "Restaurante Sabor & Arte", "niche": "Alimentação"},
        {"name": "Advocacia Silva & Santos", "niche": "Jurídico"},
        {"name": "Moda Center", "niche": "Varejo"},
        {"name": "Startup Hub", "niche": "Tecnologia"},
        {"name": "Construtora Horizonte", "niche": "Construção"},
    ]
    
    created_clients = []
    for c_data in clients_data:
        client = Client(
            name=c_data["name"],
            niche=c_data["niche"],
            company_id=company.id,
            account_manager_id=user.id,
            status='ativo',
            health_status='verde'
        )
        db.session.add(client)
        created_clients.append(client)
    
    db.session.commit()
    
    # Reload clients to get IDs
    clients = Client.query.filter_by(company_id=company.id).all()
    c_tech = next(c for c in clients if "Tech" in c.name)
    c_rest = next(c for c in clients if "Restaurante" in c.name)
    c_adv = next(c for c in clients if "Advocacia" in c.name)
    c_moda = next(c for c in clients if "Moda" in c.name)
    c_hub = next(c for c in clients if "Startup" in c.name)


    # 5. Create Contracts & Transactions
    # Targets:
    # - MRR: 9.500,00 (Requested Correction)
    # - Churn: ~14%
    # - Distribution:
    #   - Tech Solutions: 3.500,00
    #   - Advocacia Silva: 2.250,00
    #   - Startup Hub: 1.750,00
    #   - Restaurante Sabor: 1.250,00
    #   - Dr. Saúde: 750,00
    #   Total: 9.500,00
    
    active_configs = [
        {"client": c_tech, "amount": 3500.00, "desc": "Consultoria Tech"},
        {"client": c_adv, "amount": 2250.00, "desc": "Honorários Mensais"},
        {"client": c_hub, "amount": 1750.00, "desc": "Licença Enterprise"},
        {"client": c_rest, "amount": 1250.00, "desc": "Gestão de Tráfego"},
        # c_moda removed/churned or standard
        {"client_new": True, "name": "Dr. Saúde", "niche": "Saúde", "amount": 750.00, "desc": "Manutenção Site"},
    ]
    
    # Need to keep c_moda created but maybe not active MRR or use it for churn?
    # Let's keep c_moda as the Churn victim
    
    today = date.today()
    
    for conf in active_configs:
        # Resolve Client
        if conf.get("client_new"):
            client = Client(name=conf["name"], niche=conf["niche"], company_id=company.id, account_manager_id=user.id, status='ativo')
            db.session.add(client)
            db.session.flush()
        else:
            client = conf["client"]
            
        # FORMATTING FIX: "2500.0" -> "2500,00"
        val_formatted = "{:.2f}".format(conf["amount"]).replace('.', ',')
        
        # 1. Active Contract
        contract = Contract(
            company_id=company.id,
            client_id=client.id,
            template_id=template.id,
            status='signed',
            form_data=json.dumps({"valor_parcela": val_formatted}),
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        db.session.add(contract)
        db.session.flush()
        
        # 2. Forecast Transaction (Next 30 days)
        days_offset = random.randint(2, 25)
        t_future = Transaction(
            company_id=company.id,
            client_id=client.id,
            contract_id=contract.id,
            description=conf["desc"],
            amount=conf["amount"],
            due_date=today + timedelta(days=days_offset),
            status='pending',
            created_at=datetime.utcnow()
        )
        db.session.add(t_future)
        
    # EXTRA Forecast Item (Forecast > MRR)
    # Target Forecast: 10.250 (9.500 + 750)
    contract_tech = Contract.query.filter_by(company_id=company.id, client_id=c_tech.id, status='signed').first()
    
    extra_tx = Transaction(
        company_id=company.id,
        client_id=c_tech.id,
        contract_id=contract_tech.id, 
        description="Setup Integração API",
        amount=750.00,
        due_date=today + timedelta(days=15),
        status='pending',
        created_at=datetime.utcnow()
    )
    db.session.add(extra_tx)
    
    # OVERDUE Item (1.799)
    contract_rest = Contract.query.filter_by(company_id=company.id, client_id=c_rest.id, status='signed').first()
    
    overdue_tx = Transaction(
        company_id=company.id,
        client_id=c_rest.id,
        contract_id=contract_rest.id,
        description="Taxa de Implementação (Atrasada)",
        amount=1799.00,
        due_date=today - timedelta(days=12),
        status='pending', 
        created_at=datetime.utcnow() - timedelta(days=40)
    )
    db.session.add(overdue_tx)
    
    # CHURNED Contract
    # Use c_moda as churned
    churn_contract = Contract(
        company_id=company.id,
        client_id=c_moda.id,
        template_id=template.id,
        status='cancelled',
        form_data=json.dumps({"valor_parcela": "1500,00"}), # Formatted
        created_at=datetime.utcnow() - timedelta(days=120)
    )
    db.session.add(churn_contract)
    
    # Add paid history specifically for charts if needed, but not required for top KPIs
    
    db.session.commit()
    
    print(f"💰 Seeding Refined! Targets: MRR 9.500 | Forecast 10.250 | Overdue 1.799")
    
    # 7. Add Expenses (To show charts)
    expenses = [
        {"desc": "Servidores AWS", "amount": 800.00, "cat": cat_exp_fixed, "day": 5},
        {"desc": "Aluguel Escritório", "amount": 2500.00, "cat": cat_exp_fixed, "day": 1},
        {"desc": "Campanha Facebook Ads", "amount": 1500.00, "cat": cat_cost, "day": 15},
        {"desc": "Campanha Google Ads", "amount": 1200.00, "cat": cat_cost, "day": 20},
        {"desc": "Internet Fibra", "amount": 250.00, "cat": cat_exp_fixed, "day": 10},
    ]
    
    for exp_data in expenses:
        due = today.replace(day=exp_data["day"]) 
        # handling month boundary simply
        if due < today.replace(day=1): due = due + timedelta(days=30)
        
        # Paid ones
        exp = Expense(
            company_id=company.id,
            user_id=user.id,
            category_id=exp_data["cat"].id,
            description=exp_data["desc"],
            amount=exp_data["amount"],
            due_date=due,
            paid_date=due if due <= today else None,
            status='paid' if due <= today else 'pending'
        )
        db.session.add(exp)

    db.session.commit()
    
    # Verify Total Forecast
    # total_forecast = sum(t["amount"] for t in txs)
    # print(f"💰 Seeding Complete! Total Forecast Generated: R$ {total_forecast:,.2f}")
    # assert abs(total_forecast - 12760.0) < 0.1, "Target mismatch!"

if __name__ == '__main__':
    with app.app_context():
        seed_financial_demo()
