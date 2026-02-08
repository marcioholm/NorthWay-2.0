
from models import db, FormInstance, FormSubmission, Lead, Interaction, Task, User, Company
from datetime import datetime, timedelta
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import uuid

class FormService:
    @staticmethod
    def get_serializer():
        return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    @staticmethod
    def generate_public_token(form_instance_id):
        s = FormService.get_serializer()
        return s.dumps({'fid': form_instance_id}, salt='form-submission')

    @staticmethod
    def verify_token(token, form_instance_id):
        s = FormService.get_serializer()
        try:
            data = s.loads(token, salt='form-submission', max_age=3600) # 1 hour exp
            if data.get('fid') != form_instance_id:
                return False
            return True
        except (SignatureExpired, BadSignature):
            return False

    @staticmethod
    def process_submission(form_instance, payload):
        """
        Process the form submission:
        1. Calc Scores
        2. Upsert Lead
        3. Create Note
        4. Create Task
        5. Save Submission
        """
        # 1. Calc Scores
        schema = form_instance.template.schema_json
        answers = payload.get('answers', {})
        
        score_total = 0
        pillars = {'Atrair': 0, 'Engajar': 0, 'Vender': 0, 'Reter': 0} # Normalize keys
        
        # Helper to map q_id to pillar
        q_map = {q['id']: q['pilar'] for q in schema['questions']}
        
        for q_id, val in answers.items():
            val = int(val)
            score_total += val
            pilar = q_map.get(q_id)
            if pilar in pillars:
                pillars[pilar] += val
                
        # Stars (0-60 -> 0-5)
        stars = round((score_total / 60) * 5, 1)
        
        # Classification
        classification = "Indefinido"
        if stars <= 1.4: classification = "Crítico: crescimento travado"
        elif stars <= 2.4: classification = "Base frágil: perda constante de vendas"
        elif stars <= 3.4: classification = "Esforço sem processo"
        elif stars <= 4.4: classification = "Boa estrutura, falta escala"
        else: classification = "Pronto para acelerar"
            
        # 2. Upsert Lead
        lead_data = payload.get('contact', {})
        whatsapp = lead_data.get('whatsapp', '').strip()
        
        # Search existing lead by phone in this tenant
        lead = Lead.query.filter_by(company_id=form_instance.tenant_id, phone=whatsapp).first()
        
        if not lead:
            lead = Lead(
                company_id=form_instance.tenant_id,
                name=lead_data.get('full_name'),
                phone=whatsapp,
                email=lead_data.get('email'), # Optional capture
                pipeline_id=None, # Default or process later
                stage_id=None,
                user_id=form_instance.owner_user_id, # Assign to form owner
                status='new',
                source="Diagnóstico Northway"
            )
            db.session.add(lead)
            db.session.flush()
        else:
            # Update missing info if needed
            if not lead.name: lead.name = lead_data.get('full_name')
            if not lead.email and lead_data.get('email'): lead.email = lead_data.get('email')
            # Don't change owner if already exists
            
        # 3. Save Submission
        submission = FormSubmission(
            form_instance_id=form_instance.id,
            tenant_id=form_instance.tenant_id,
            owner_user_id=form_instance.owner_user_id,
            lead_id=lead.id,
            payload=payload,
            score_total=score_total,
            score_atrair=pillars['Atrair'],
            score_engajar=pillars['Engajar'],
            score_vender=pillars['Vender'],
            score_reter=pillars['Reter'],
            stars=stars,
            classification=classification
        )
        db.session.add(submission)
        
        # 4. Create Note (Interaction)
        note_body = f"""
Score Total: {score_total} / 60
Nota Final: {stars} / 5.0
Classificação: {classification}

--- Pilares ---
Atrair: {pillars['Atrair']} / 15
Engajar: {pillars['Engajar']} / 15
Vender: {pillars['Vender']} / 15
Reter: {pillars['Reter']} / 15

--- Respostas ---
"""
        for q in schema['questions']:
            ans = answers.get(q['id'], 0)
            note_body += f"{q['id']}) {q['text']}: {ans}\n"
            
        note_body += f"\nMetadados:\nInstance: {form_instance.public_slug}"

        interaction = Interaction(
            lead_id=lead.id,
            user_id=form_instance.owner_user_id,
            company_id=form_instance.tenant_id,
            type='nota',
            content=note_body
        )
        db.session.add(interaction)
        
        # 5. Create Task
        task_title = "Contato Diagnóstico"
        due_delta = timedelta(hours=24)
        
        if stars <= 2.4:
            task_title = "🚨 Contato Urgente (Diagnóstico Crítico)"
            due_delta = timedelta(minutes=15)
        elif stars <= 3.4:
            task_title = "📚 Enviar eBook de conscientização (Diagnóstico Médio)"
            due_delta = timedelta(hours=2)
        else:
            task_title = "🚀 Agendar Reunião de Escala (Diagnóstico Alto)"
            due_delta = timedelta(hours=24)
            
        task = Task(
            title=task_title,
            description=f"Lead preencheu diagnóstico com nota {stars}. Classificação: {classification}.",
            due_date=datetime.utcnow() - timedelta(hours=3) + due_delta,
            user_id=form_instance.owner_user_id,
            company_id=form_instance.tenant_id,
            lead_id=lead.id,
            status='pending'
        )
        db.session.add(task)
        
        db.session.commit()
        return submission

