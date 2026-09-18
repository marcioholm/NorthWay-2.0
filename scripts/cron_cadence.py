from app import create_app
from models import db, Lead, Pipeline, PipelineStage, get_now_br
from datetime import timedelta

app = create_app()

def run_cadence():
    with app.app_context():
        # Find all pre-sales pipelines
        presales_pipelines = Pipeline.query.filter_by(name='Funil de Pré-venda').all()
        now = get_now_br()
        
        for pipeline in presales_pipelines:
            stages = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).all()
            if not stages:
                continue
                
            # Create a map of current stage to next stage
            cadence_stages = [s for s in stages if s.name.startswith('Cadência — Dia')]
            if not cadence_stages:
                continue
                
            # For each cadence stage, find leads that have been there for > 24h
            for i, stage in enumerate(cadence_stages):
                # If it's the last cadence stage, we might move to "Sem retorno" or leave it.
                next_stage = cadence_stages[i+1] if i + 1 < len(cadence_stages) else None
                
                # Fetch leads in this stage
                leads = Lead.query.filter_by(pipeline_stage_id=stage.id).all()
                for lead in leads:
                    # Determine how long it's been in this stage
                    # Assuming we use updated_at to track stage change
                    # A robust implementation uses LeadStageHistory, but updated_at is a good proxy for now.
                    if lead.updated_at and now - lead.updated_at > timedelta(days=1):
                        if next_stage:
                            lead.pipeline_stage_id = next_stage.id
                            print(f"Moved Lead {lead.id} ({lead.name}) to {next_stage.name}")
                        else:
                            # Time's up for the cadence
                            sem_retorno = PipelineStage.query.filter_by(pipeline_id=pipeline.id, name='Sem retorno').first()
                            if sem_retorno:
                                lead.pipeline_stage_id = sem_retorno.id
                                print(f"Moved Lead {lead.id} ({lead.name}) to Sem retorno")
                        db.session.commit()

if __name__ == '__main__':
    run_cadence()
