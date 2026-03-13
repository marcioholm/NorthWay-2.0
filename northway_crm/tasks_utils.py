from datetime import datetime, timedelta
from models import db, Task, Lead, PipelineStageTaskTemplate, User, Notification, AutomationRule, AutomationExecution, MessageQueue
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

def process_funnel_automations(lead_id, stage_id):
    """
    Checks for active WhatsApp automation rules for a stage and queues messages.
    """
    lead = Lead.query.get(lead_id)
    if not lead or not lead.phone:
        return False

    rules = AutomationRule.query.filter_by(
        stage_id=stage_id,
        company_id=lead.company_id,
        active=True,
        trigger_type='stage_entry'
    ).all()

    if not rules:
        return False

    queued_count = 0
    now = get_now_br()

    for rule in rules:
        # Check if already executed for this lead
        execution = AutomationExecution.query.filter_by(
            rule_id=rule.id,
            lead_id=lead_id
        ).first()

        if execution:
            continue

        # Variable Substitution
        content = rule.message_template or ""
        replacements = {
            "{{nome}}": lead.name.split()[0] if lead.name else "Lead",
            "{{empresa}}": lead.company_name or "Empresa",
            "{{responsavel}}": User.query.get(lead.assigned_to_id).name if lead.assigned_to_id else "Responsável",
            "{{interesse}}": lead.interest or "seu interesse"
        }
        
        for key, val in replacements.items():
            content = content.replace(key, str(val))

        # Create Execution Record
        new_execution = AutomationExecution(
            rule_id=rule.id,
            lead_id=lead_id,
            status='executed',
            executed_at=now
        )
        db.session.add(new_execution)
        db.session.flush()

        # Create Message Queue Entry
        new_msg = MessageQueue(
            company_id=lead.company_id,
            lead_id=lead_id,
            phone=lead.phone,
            content=content,
            status='pending',
            scheduled_at=now + timedelta(hours=rule.delay_hours),
            rule_id=rule.id,
            execution_id=new_execution.id
        )
        db.session.add(new_msg)
        queued_count += 1

    if queued_count > 0:
        db.session.commit()
        return True

    return False
