from app import create_app, db
from models import User, Company, Lead, Pipeline, PipelineStage, Transaction, Goal, Client, Contract, ContractTemplate, Interaction, FinancialCategory, Expense
from datetime import datetime, timedelta
import random

def seed_data():
    app = create_app()
    with app.app_context():
        company = Company.query.first()
        user = User.query.filter_by(email="admin@northway.com").first()
        pipeline = Pipeline.query.filter_by(company_id=company.id).first()
        stages = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).all()

        print(f"Seeding data for Company: {company.name} (ID: {company.id})")

        # 1. Clear existing Data for clean stats
        try:
            db.session.query(Expense).delete()
            db.session.query(Transaction).delete()
            db.session.query(Contract).delete()
            db.session.query(Client).delete()
            db.session.query(Lead).delete()
            db.session.commit()
            print("Cleared old data.")
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing data: {e}")

        # 2. Add Leads (Prospects)
        names = ["Tech Solutions", "Mercado Livre", "Consultoria XYZ", "Construtora Silva", "Educa Mais", "Varejo Express", "Healthfy", "Solar Energy", "Logística Rapida", "Food Delivery"]
        
        print("Creating Leads...")
        for i, name in enumerate(names):
            stage = random.choice(stages)
            lead = Lead(
                name=name,
                company_id=company.id,
                pipeline_id=pipeline.id,
                pipeline_stage_id=stage.id,
                assigned_to_id=user.id,
                source="Google",
                phone=f"1199999{i:04d}",
                email=f"contato{i}@empresa.com",
                bant_budget="50k-100k",
                created_at=datetime.now() - timedelta(days=random.randint(1, 30))
            )
            db.session.add(lead)
        
        # 3. Add Clients & Contracts (Revenue ~ 50k)
        # 10 Clients * 5k ticket = 50k MRR
        print("Creating Clients/Contracts...")
        
        # Ensure a template
        template = ContractTemplate.query.filter_by(company_id=company.id).first()
        if not template:
            template = ContractTemplate(company_id=company.id, name="Contrato Padrão", content="...", type='contract')
            db.session.add(template)
            db.session.flush()

        for i in range(10):
            client = Client(
                name=f"Cliente Premium {i+1}",
                company_id=company.id,
                account_manager_id=user.id,
                status='ativo',
                monthly_value=5000.0, # Ticket Medio 5k
                start_date=datetime.now().date() - timedelta(days=90),
                email=f"client{i}@vip.com",
                niche="Tecnologia" if i % 2 == 0 else "Varejo"
            )
            db.session.add(client)
            db.session.flush()

            # Contract
            contract = Contract(
                client_id=client.id,
                company_id=company.id,
                template_id=template.id,
                code=f"CTR-2024-{i:02d}",
                status='signed',
                form_data='{"valor_parcela": "5000.00"}', # For MRR calc
                created_at=datetime.now() - timedelta(days=90)
            )
            db.session.add(contract)
            db.session.flush()

            # Transactions (3 months history + 1 future)
            # Month -2 (Paid), Month -1 (Paid), Month 0 (Computed for DRE?), Month +1 (Future)
            # DRE usually looks at "This Month".
            # Let's populate "This Month" (Month 0) as PAID/PENDING mix to show revenue.
            
            today = datetime.now()
            
            # Past/Current
            for m in range(3): 
                # 0 = this month, 1 = last month, 2 = 2 months ago
                t_date = today - timedelta(days=30*m)
                
                # Make 1 overdue in current month
                status = 'paid'
                paid_date = t_date.date()
                if m == 0 and i == 9: # Last client, this month
                     status = 'pending' # Late?
                     paid_date = None
                     # actually to show overdue risk, due date must be past
                     t_date = today - timedelta(days=2) 
                
                trans = Transaction(
                    client_id=client.id,
                    contract_id=contract.id,
                    company_id=company.id,
                    description=f"Mensalidade {m}",
                    amount=5000.0,
                    due_date=t_date.date(),
                    status=status,
                    paid_date=paid_date,
                    created_at=t_date
                )
                db.session.add(trans)
                
            # Future (Forecast)
            trans_future = Transaction(
                client_id=client.id,
                contract_id=contract.id,
                company_id=company.id,
                description="Mensalidade Futura",
                amount=5000.0,
                due_date=(today + timedelta(days=30)).date(),
                status='pending'
            )
            db.session.add(trans_future)

        # Churn (1 Client)
        client_churn = Client(name="Cliente Cancelado", company_id=company.id, account_manager_id=user.id, status='cancelado', monthly_value=5000.0, start_date=datetime.now().date())
        db.session.add(client_churn)
        db.session.flush()
        contract_churn = Contract(client_id=client_churn.id, company_id=company.id, template_id=template.id, status='cancelled', form_data='{"valor_parcela": "5000.00"}', created_at=datetime.now())
        db.session.add(contract_churn)

        # 4. Add Expenses (To match EBITDA)
        # Revenue = 10 * 5k = 50k (Approx, minus 1 overdue maybe)
        # Gross Revenue in DRE counts ACCRUAL (Faturado), so 50k usually.
        
        # Target EBITDA ~ 30% = 15k
        # Expenses need to be ~35k
        
        print("Creating Expenses...")
        cat_infra = FinancialCategory.query.filter_by(name="Infraestrutura").first() or FinancialCategory(name="Infraestrutura", type="expense", company_id=company.id)
        db.session.add(cat_infra)
        
        cat_tax = FinancialCategory.query.filter_by(name="Impostos e Taxas").first() or FinancialCategory(name="Impostos e Taxas", type="expense", company_id=company.id)
        db.session.add(cat_tax)
            
        cat_comm = FinancialCategory.query.filter_by(name="Comissões").first() or FinancialCategory(name="Comissões", type="cost", company_id=company.id)
        db.session.add(cat_comm)
        
        cat_personnel = FinancialCategory.query.filter_by(name="Pessoal").first()
        if not cat_personnel:
             cat_personnel = FinancialCategory(name="Pessoal", type="expense", company_id=company.id)
             db.session.add(cat_personnel)
            
        db.session.flush()
            
        # 1. Taxes (10% of 50k = 5k)
        exp_tax = Expense(
             description="DAS Simples Nacional",
             amount=5000.00,
             due_date=datetime.now().date(),
             status='paid',
             category_id=cat_tax.id,
             company_id=company.id,
             user_id=user.id
        )
        db.session.add(exp_tax)
        
        # 2. Commissions (5% = 2.5k)
        exp_comm = Expense(
             description="Comissões de Vendas",
             amount=2500.00,
             due_date=datetime.now().date(),
             status='paid',
             category_id=cat_comm.id,
             company_id=company.id,
             user_id=user.id
        )
        db.session.add(exp_comm)
        
        # 3. Fixed - Personnel (20k)
        exp_salaries = Expense(
             description="Folha de Pagamento",
             amount=20000.00,
             due_date=datetime.now().date(),
             status='paid',
             category_id=cat_personnel.id,
             company_id=company.id,
             user_id=user.id
        )
        db.session.add(exp_salaries)
        
        # 4. Fixed - Infra (7.5k)
        exp_infra = Expense(
             description="Servidores e Software",
             amount=7500.00,
             due_date=datetime.now().date(),
             status='paid',
             category_id=cat_infra.id,
             company_id=company.id,
             user_id=user.id
        )
        db.session.add(exp_infra)
        
        # Total Expenses = 5 + 2.5 + 20 + 7.5 = 35k
        # EBITDA = 50k - 35k = 15k. Matches.

        # 5. Goals
        print("Creating Goals...")
        goal = Goal.query.filter_by(company_id=company.id, month=datetime.now().month, year=datetime.now().year).first()
        if not goal:
            goal = Goal(
                company_id=company.id,
                month=datetime.now().month,
                year=datetime.now().year,
                target_amount=50000.0,
                min_new_sales=5000.0
            )
            db.session.add(goal)
        
        db.session.commit()
        print("Seed Complete!")

if __name__ == "__main__":
    seed_data()
