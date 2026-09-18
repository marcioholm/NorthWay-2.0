from app import create_app
from models import db, Company, Pipeline, PipelineStage, User, get_now_br

app = create_app()

with app.app_context():
    db.create_all() # Ensure new tables exist
    
    companies = Company.query.all()
    for company in companies:
        # Check if already migrated
        if Pipeline.query.filter_by(company_id=company.id, name='Funil de Pré-venda').first():
            print(f"Company {company.id} already migrated.")
            continue
            
        print(f"Migrating company {company.id}...")
        
        # Funil de Pré-venda
        pipeline_presales = Pipeline(name='Funil de Pré-venda', company_id=company.id)
        db.session.add(pipeline_presales)
        
        # Funil de Vendas
        pipeline_sales = Pipeline(name='Funil de Vendas', company_id=company.id)
        db.session.add(pipeline_sales)
        
        db.session.flush()
        
        presales_stages = [
            'Novo lead', 'Cadência — Dia 1', 'Cadência — Dia 2', 'Cadência — Dia 3', 
            'Cadência — Dia 4', 'Cadência — Dia 5', 'Cadência — Dia 6', 'Cadência — Dia 7', 
            'Cadência — Dia 8', 'Cadência — Dia 9', 'Cadência — Dia 10', 'Cadência — Dia 11', 
            'Cadência — Dia 12', 'Contato aceito', 'Em qualificação', 'Reunião agendada', 
            'Desqualificado', 'Sem retorno', 'Retomar futuramente'
        ]
        for i, s_name in enumerate(presales_stages):
            stage = PipelineStage(name=s_name, order=i, pipeline_id=pipeline_presales.id, company_id=company.id)
            db.session.add(stage)
            
        sales_stages = [
            'Reunião agendada', 'Reunião confirmada', 'Reunião realizada', 'Proposta enviada', 
            'Follow-up — Dia 1', 'Follow-up — Dia 2', 'Follow-up — Dia 3', 'Follow-up — Dia 4',
            'Follow-up — Dia 5', 'Follow-up — Dia 6', 'Follow-up — Dia 7', 'Follow-up — Dia 8',
            'Negócio ganho', 'Negócio perdido', 'Retomar futuramente', 'Não compareceu'
        ]
        for i, fu_name in enumerate(sales_stages):
            fu_stage = PipelineStage(name=fu_name, order=i, pipeline_id=pipeline_sales.id, company_id=company.id)
            db.session.add(fu_stage)
            
        # Give all users in company access
        users = User.query.filter_by(company_id=company.id).all()
        for user in users:
            user.allowed_pipelines.append(pipeline_presales)
            user.allowed_pipelines.append(pipeline_sales)
            
    db.session.commit()
    print("Migration complete!")
