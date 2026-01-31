from models import db, User, Company, Client, Lead, Contract, Transaction, Pipeline, PipelineStage, Role, ROLE_ADMIN
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def seed_rich_data(db_session, user_email="admin@northway.com"):
    print(f"🚀 Starting RICH data seeding for {user_email}...")
    
    # 1. Get/Create User & Company
    user = User.query.filter_by(email=user_email).first()
    company = None
    
    if user:
        company = Company.query.get(user.company_id)
        if not company:
             # Should not happen if user exists properly, but safety net
             company = Company(name="NorthWay Demo", document="00000000000191", payment_status="active")
             db_session.add(company)
             db_session.flush()
             user.company_id = company.id
    else:
        # Create from scratch
        company = Company.query.filter_by(document="00000000000191").first()
        if not company:
            company = Company(name="NorthWay Demo", document="00000000000191", payment_status="active")
            db_session.add(company)
            db_session.flush()
            
        user = User(
            name="NorthWay Admin",
            email=user_email,
            password_hash=generate_password_hash("123456"),
            role=ROLE_ADMIN,
            company_id=company.id,
            is_super_admin=True
        )
        db_session.add(user)
        db_session.flush()
        
    cid = company.id
    uid = user.id
    
    # 2. WIPE EXISTING DATA for this company
    print("🧹 Wiping old data...")
    Transaction.query.filter_by(company_id=cid).delete()
    Contract.query.filter_by(company_id=cid).delete()
    Client.query.filter_by(company_id=cid).delete()
    Lead.query.filter_by(company_id=cid).delete()
    # Note: We keep configs like pipelines usually, but let's ensure pipeline exists
    
    # 3. Ensure Pipeline
    pipeline = Pipeline.query.filter_by(company_id=cid).first()
    if not pipeline:
        pipeline = Pipeline(name="Comercial Padrão", company_id=cid)
        db_session.add(pipeline)
        db_session.flush()
        stages = ["Novo Lead", "Qualificação", "Apresentação", "Negociação", "Fechamento"]
        for i, s_name in enumerate(stages):
            stage = PipelineStage(name=s_name, order=i, pipeline_id=pipeline.id, company_id=cid)
            db_session.add(stage)
        db_session.flush()

    # Refetch stages
    stages_objs = PipelineStage.query.filter_by(pipeline_id=pipeline.id).all()
    stage_map = {s.name: s.id for s in stages_objs}
    
    # 4. CREATE CLIENTS (Target: ~10k MRR, Ticket 1500)
    # We want 7 clients at 1500 = 10500.
    
    client_names = [
        "TechSolutions Ltda", "Gourmet Foods", "Alpha Logistics", 
        "Consultoria Santos", "Varejo Express", "Clinica Bem Estar", 
        "Educa Mais"
    ]
    
    today = datetime.utcnow()
    
    print("💼 Creating Clients & Financials...")
    for i, name in enumerate(client_names):
        status = 'ativo'
        health = 'verde'
        
        # Make one overdue
        if i == 6: # Educa Mais
            status = 'ativo' # Still active service, but payment pending
            health = 'vermelho'
        
        start_date = today - timedelta(days=random.randint(60, 180))
        
        client = Client(
            name=name,
            company_id=cid,
            account_manager_id=uid,
            status=status,
            health_status=health,
            start_date=start_date,
            monthly_value=1500.00,
            service="Consultoria Premium",
            contract_type="mensal",
            email=f"contato@{name.lower().replace(' ', '')}.com",
            phone="11999999999"
        )
        db_session.add(client)
        db_session.flush()
        
        # Create Past Transactions (Paid)
        # Create last 3 months
        for month_offset in range(1, 4):
            due = today - timedelta(days=30*month_offset)
            t = Transaction(
                client_id=client.id,
                company_id=cid,
                description="Mensalidade Consultoria",
                amount=1500.00,
                due_date=due,
                status='paid',
                paid_date=due + timedelta(days=random.randint(0, 5))
            )
            db_session.add(t)
            
        # Create Current Month
        # If it's the overdue client
        if i == 6: 
            # Overdue by 5 days
            due = today - timedelta(days=5)
            t = Transaction(
                client_id=client.id,
                company_id=cid,
                description="Mensalidade Consultoria (Atrasada)",
                amount=1500.00,
                due_date=due,
                status='overdue' # or pending but date passed
            )
        else:
            # Pending for future or Paid if early month
            due = today + timedelta(days=10)
            t = Transaction(
                client_id=client.id,
                company_id=cid,
                description="Mensalidade Consultoria",
                amount=1500.00,
                due_date=due,
                status='pending'
            )
        db_session.add(t)
        
    # 5. CREATE LEADS
    print("🚀 Creating Leads...")
    leads_data = [
        ("Padaria Central", "Novo Lead"),
        ("Oficina do Zé", "Qualificação"),
        ("StartUp Inova", "Apresentação"),
        ("Loja de Roupas Ana", "Negociação"),
        ("Transportadora Veloz", "Novo Lead")
    ]
    
    for lname, sname in leads_data:
        sid = stage_map.get(sname, stage_map.get("Novo Lead"))
        lead = Lead(
            name=lname,
            company_id=cid,
            pipeline_id=pipeline.id,
            pipeline_stage_id=sid,
            assigned_to_id=uid,
            status='in_progress',
            source='Google Ads'
        )
        db_session.add(lead)
    
    db_session.commit()
    print("✅ Rich Data Seeding Complete!")
