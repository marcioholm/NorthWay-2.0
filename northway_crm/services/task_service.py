from models import db, Task, TaskEvent, User
from datetime import datetime

class TaskService:
    @staticmethod
    def get_kanban_tasks(user_id, filters=None):
        """
        Returns tasks for a user organized by status for Kanban view.
        Supported filters: client_id, lead_id, pipeline_stage_id, date_start, date_end
        """
        query = Task.query.filter((Task.assigned_to_id == user_id) | (Task.created_by_user_id == user_id))
        
        if filters:
            if filters.get('client_id'):
                query = query.filter(Task.client_id == filters['client_id'])
            if filters.get('lead_id'):
                query = query.filter(Task.lead_id == filters['lead_id'])
            if filters.get('pipeline_stage_id'):
                from models import Lead
                query = query.join(Lead, Task.lead_id == Lead.id).filter(Lead.pipeline_stage_id == filters['pipeline_stage_id'])
            if filters.get('date_start'):
                query = query.filter(Task.due_date >= filters['date_start'])
            if filters.get('date_end'):
                query = query.filter(Task.due_date <= filters['date_end'])
            
        tasks = query.all()
        
        # Organize by status (Mapping old statuses to new workflow if needed)
        kanban = {
            'a_fazer': [],
            'em_andamento': [],
            'aguardando': [],
            'validacao': [],
            'concluida': []
        }
        
        legacy_map = {
            'pendente': 'a_fazer',
            'concluida': 'concluida'
        }
        
        for task in tasks:
            status_key = task.status
            if status_key in legacy_map:
                status_key = legacy_map[status_key]
            
            if status_key not in kanban:
                # Fallback for unknown statuses
                if status_key not in kanban:
                    # Maybe add to 'a_fazer' default?
                    kanban['a_fazer'].append(task)
                    continue
            
            kanban[status_key].append(task)
            
        return kanban

    @staticmethod
    def create_task(data, user_id):
        """
        Creates a new task and logs the event.
        data: dict containing title, description, priority, due_date, etc.
        user_id: ID of the actor creating the task
        """
        try:
            new_task = Task(
                title=data.get('title'),
                description=data.get('description'),
                priority=data.get('priority', 'media'),
                due_date=data.get('due_date'),
                status='a_fazer',
                company_id=data.get('company_id'), # Should be passed or inferred
                assigned_to_id=data.get('assigned_to_id', user_id),
                is_urgent=data.get('is_urgent', False),
                is_important=data.get('is_important', False),
                created_by_user_id=user_id,
                source_type=data.get('source_type', 'MANUAL'),
                auto_generated=data.get('auto_generated', False),
                
                # Links
                lead_id=data.get('lead_id'),
                client_id=data.get('client_id'),
                contract_id=data.get('contract_id'),
                service_order_id=data.get('service_order_id')
            )
            
            db.session.add(new_task)
            db.session.flush() # Get ID
            
            # Log Event
            TaskService.log_event(
                task_id=new_task.id,
                actor_id=user_id,
                event_type='CREATED',
                payload={'title': new_task.title, 'priority': new_task.priority}
            )
            
            db.session.commit()
            return new_task
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_status(task_id, new_status, actor_id):
        """
        Updates task status and logs event.
        """
        task = Task.query.get(task_id)
        if not task:
            raise ValueError("Task not found")
            
        old_status = task.status
        task.status = new_status
        
        if new_status == 'concluida' and not task.completed_at:
            task.completed_at = datetime.utcnow()
        
        # Log Event
        TaskService.log_event(
            task_id=task.id,
            actor_id=actor_id,
            event_type='STATUS_CHANGED',
            payload={'old': old_status, 'new': new_status}
        )
        
        db.session.commit()
        return task

    @staticmethod
    def apply_auto_rules(user_id, company_id):
        """
        Applies strategic automation rules for a specific user:
        1. Lead 48h no follow-up -> Urgent
        2. Task Overdue -> Urgent + Important
        3. Contract expiring in 3 days -> Urgent
        """
        from models import Lead, Contract, Interaction
        from datetime import datetime, timedelta
        
        # 1. Overdue Tasks -> Q1 (Urgent + Important)
        overdue_tasks = Task.query.filter(
            Task.assigned_to_id == user_id,
            Task.status != 'concluida',
            Task.due_date < datetime.utcnow()
        ).all()
        for t in overdue_tasks:
            t.is_urgent = True
            t.is_important = True

        # 2. Leads without follow-up (48h) -> Urgent
        threshold_48h = datetime.utcnow() - timedelta(hours=48)
        leads_to_flag = Lead.query.filter(
            Lead.company_id == company_id,
            Lead.assigned_to_id == user_id,
            Lead.status != 'CONVERTED' # Adjust based on actual converted status name
        ).all()
        
        for lead in leads_to_flag:
            # Check last interaction
            last_interaction = Interaction.query.filter_by(lead_id=lead.id).order_by(Interaction.created_at.desc()).first()
            last_date = last_interaction.created_at if last_interaction else lead.created_at
            
            if last_date < threshold_48h:
                # Flag associated tasks or mark new ones? 
                # USER goal: "Lead sem follow-up 48h -> marcar automaticamente como urgente"
                # This usually refers to the tasks associated with that lead.
                for task in lead.tasks:
                    if task.status != 'concluida':
                        task.is_urgent = True

        # 3. Contract expiring in 3 days -> Urgent
        # Note: Need to check how expiration data is stored. 
        # Contract model viewed earlier didn't have a clear expiry date but usually it's in form_data or added via Vigencia.
        # However, Task often has a due_date linked to a contract action.
        # Let's check for tasks linked to contracts with short due dates.
        contract_tasks = Task.query.filter(
            Task.assigned_to_id == user_id,
            Task.contract_id != None,
            Task.status != 'concluida',
            Task.due_date <= datetime.utcnow() + timedelta(days=3)
        ).all()
        for ct in contract_tasks:
            ct.is_urgent = True

        db.session.commit()

    @staticmethod
    def log_event(task_id, actor_id, event_type, payload=None, actor_type='USER'):
        event = TaskEvent(
            task_id=task_id,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type=event_type,
            payload=payload
        )
        db.session.add(event)
