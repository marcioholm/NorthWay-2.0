from datetime import datetime, timedelta
from models import db, Task, Lead, PipelineStageTaskTemplate, User, Notification
from utils import get_now_br, create_notification

def generate_tasks_for_stage(lead_id, stage_id):
    """
    Generates automated tasks for a lead based on the templates defined for a stage.
    """
    lead = Lead.query.get(lead_id)
    if not lead:
        return False
    
    templates = PipelineStageTaskTemplate.query.filter_by(stage_id=stage_id).all()
    if not templates:
        return False
    
    now = get_now_br()
    generated_count = 0
    
    # Responsible user (assigned to the lead)
    assigned_to_id = lead.assigned_to_id
    if not assigned_to_id:
        # Fallback to current company admin or creator if not assigned
        # For now, if unassigned, we might not generate or assign to a default.
        # Let's check if the lead has a creator
        assigned_to_id = lead.user_id 

    if not assigned_to_id:
        return False

    for template in templates:
        # Prevent 100% exact duplicates (same stage, same title, same lead) 
        # specifically if they are still pending
        existing = Task.query.filter_by(
            lead_id=lead_id,
            origin_stage_id=stage_id,
            title=template.title,
            status='pendente'
        ).first()
        
        if existing:
            continue
            
        # Variable Substitution
        script = template.script or ""
        replacements = {
            "[Nome]": lead.name.split()[0] if lead.name else "Lead",
            "[Empresa]": lead.company_name or "Empresa",
            "[segmento]": lead.segment or "Segmento",
            "[Responsável]": User.query.get(assigned_to_id).name if assigned_to_id else "Responsável"
        }
        
        for key, val in replacements.items():
            script = script.replace(key, str(val))
            
        due_date = now + timedelta(hours=template.delay_hours)
        
        new_task = Task(
            title=template.title,
            description=script,
            due_date=due_date,
            status='pendente',
            priority='media',
            auto_generated=True,
            task_type=template.task_type,
            origin_stage_id=stage_id,
            lead_id=lead_id,
            assigned_to_id=assigned_to_id,
            company_id=lead.company_id,
            created_by_user_id=None # System generated
        )
        
        db.session.add(new_task)
        generated_count += 1
        
        # Immediate Notification
        create_notification(
            user_id=assigned_to_id,
            company_id=lead.company_id,
            type='task_assigned',
            title=f"Nova tarefa: {template.title}",
            message=f"Tarefa automática gerada para {lead.name} ({lead.company_name or 'S/E'}). Vence em {template.delay_hours}h."
        )
        
    if generated_count > 0:
        db.session.commit()
        return True
        
    return False
