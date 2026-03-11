import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from app import app
            from models import db, Company, Pipeline, PipelineStage
            
            results = []
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
                            results.append(f"Created for company {company.id}")
                        except Exception as ce:
                            db.session.rollback()
                            results.append(f"Failed for company {company.id}: {ce}")
                    else:
                        results.append(f"Skipped {company.id} (exists)")
                db.session.commit()
                results.append(f"Done! Total created: {created}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "results": results}).encode('utf-8'))
        except Exception as e:
            import traceback
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(traceback.format_exc().encode('utf-8'))
