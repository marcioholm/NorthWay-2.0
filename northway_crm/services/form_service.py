
from models import db, FormInstance, FormSubmission, Lead, Interaction, Task, User, Company, Client
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
            # Handle int/str mismatch
            try:
                q_id_int = int(q_id)
            except:
                q_id_int = q_id
            
            pilar = q_map.get(q_id_int)
            # Fallback if key is string in q_map
            if not pilar:
                 pilar = q_map.get(str(q_id))
                 
            if pilar and pilar in pillars:
                pillars[pilar] += val
                
        # Stars (0-60 -> 0-5)
        if score_total > 60: score_total = 60 # Cap just in case
        stars = round((score_total / 60) * 5, 1)
        
        # Classification
        classification = "Indefinido"
        if stars <= 1.4: classification = "Crítico: crescimento travado"
        elif stars <= 2.4: classification = "Base frágil: perda constante de vendas"
        elif stars <= 3.4: classification = "Esforço sem processo"
        elif stars <= 4.4: classification = "Boa estrutura, falta escala"
        else: classification = "Pronto para acelerar"
            
        # 2. Identify Target (Lead or Client)
        target_id = payload.get('target_id')
        target_type = payload.get('target_type') # 'lead' or 'client'
        
        target_lead = None
        target_client = None
        
        if target_type == 'client' and target_id:
            target_client = Client.query.get(target_id)
            if target_client:
                # Update Client Diagnostic Info
                target_client.diagnostic_status = 'done'
                target_client.diagnostic_score = score_total
                target_client.diagnostic_stars = stars
                target_client.diagnostic_classification = classification
                target_client.diagnostic_date = datetime.utcnow() - timedelta(hours=3)
                target_client.diagnostic_pillars = pillars
        
        elif target_type == 'lead' and target_id:
            target_lead = Lead.query.get(target_id)
            
        # Fallback to phone search if no specific target found
        lead_data = payload.get('contact', {})
        whatsapp = lead_data.get('whatsapp', '').strip()
        
        if not target_client and not target_lead:
            target_lead = Lead.query.filter_by(company_id=form_instance.tenant_id, phone=whatsapp).first()
        
        if not target_client:
            if not target_lead:
                target_lead = Lead(
                    company_id=form_instance.tenant_id,
                    name=lead_data.get('full_name', '')[:100],
                    phone=whatsapp[:50],
                    email=lead_data.get('email')[:120] if lead_data.get('email') else None, 
                    pipeline_id=None,
                    stage_id=None,
                    user_id=form_instance.owner_user_id,
                    status='new',
                    source="Diagnóstico Northway"
                )
                db.session.add(target_lead)
                db.session.flush()
            else:
                # Update existing lead
                if not target_lead.name: target_lead.name = lead_data.get('full_name')
                if not target_lead.email and lead_data.get('email'): target_lead.email = lead_data.get('email')
            
            # Update Lead Diagnostic Info
            target_lead.diagnostic_status = 'done'
            target_lead.diagnostic_score = score_total
            target_lead.diagnostic_stars = stars
            target_lead.diagnostic_classification = classification
            target_lead.diagnostic_date = datetime.utcnow() - timedelta(hours=3)
            target_lead.diagnostic_pillars = pillars

        # 3. Save Submission
        submission = FormSubmission(
            form_instance_id=form_instance.id,
            tenant_id=form_instance.tenant_id,
            owner_user_id=form_instance.owner_user_id,
            lead_id=target_lead.id if target_lead else None,
            client_id=target_client.id if target_client else None,
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
        note_target_lead_id = target_lead.id if target_lead else None
        # If it's a client, we might want to attach interaction to client? 
        # Checking Interaction model... usually it has lead_id. 
        # If it's a client, we might need a client_id in Interaction or just skip interaction for now.
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
            lead_id=note_target_lead_id,
            client_id=target_client.id if target_client else None, # Add client_id if supported
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
            description=f"{(target_type or 'Lead').capitalize()} preencheu diagnóstico com nota {stars}. Classificação: {classification}.",
            due_date=datetime.utcnow() - timedelta(hours=3) + due_delta,
            user_id=form_instance.owner_user_id,
            company_id=form_instance.tenant_id,
            lead_id=note_target_lead_id,
            client_id=target_client.id if target_client else None, # Add client_id if supported
            status='pending'
        )
        db.session.add(task)
        
        db.session.commit()
        return submission

