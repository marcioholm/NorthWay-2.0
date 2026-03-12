import os
from dotenv import load_dotenv

load_dotenv('.env.production')

from app import app
import os
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', '').replace(':6543', ':5432')
from models import db, Company, Pipeline, PipelineStage

with app.app_context():
    companies = Company.query.all()
    created = 0
    for company in companies:
        existing_fu = Pipeline.query.filter_by(company_id=company.id, name='Follow-up (12 Dias)').first()
        if not existing_fu:
            try:
                fu_pipeline = Pipeline(name='Follow-up (12 Dias)', company_id=company.id)
                db.session.add(fu_pipeline)
                db.session.flush() # get ID
                
                fu_stages = ['Dia 1', 'Dia 2', 'Dia 4', 'Dia 7', 'Dia 12', 'Perdido/Sem Resposta']
                for i, fu_name in enumerate(fu_stages):
                    fu_stage = PipelineStage(name=fu_name, order=i, pipeline_id=fu_pipeline.id, company_id=company.id)
                    db.session.add(fu_stage)
                    
                created += 1
                print(f"Created for company {company.id}")
            except Exception as ce:
                db.session.rollback()
                print(f"Failed for company {company.id}: {ce}")
    db.session.commit()
    print(f"Done. Created {created} pipelines on {app.config['SQLALCHEMY_DATABASE_URI'][:20]}...")
