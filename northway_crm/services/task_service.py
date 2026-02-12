from models import db, Task, TaskEvent, User
from datetime import datetime

class TaskService:
    @staticmethod
    def get_kanban_tasks(user_id, filters=None):
        """
        Returns tasks for a user organized by status for Kanban view.
        Supported filters: client_id, lead_id, pipeline_stage_id, date_start, date_end
        """
        from sqlalchemy.orm import joinedload
        query = Task.query.options(
            joinedload(Task.client),
            joinedload(Task.lead),
            joinedload(Task.responsible)
        ).filter((Task.assigned_to_id == user_id) | (Task.created_by_user_id == user_id))
        
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
        from models import Lead, Contract, Interaction, Task, db, LEAD_STATUS_WON, LEAD_STATUS_LOST
        from datetime import datetime, timedelta
        from sqlalchemy import and_, or_, not_
        
        # 1. Overdue Tasks -> Q1 (Urgent + Important)
        # Bulk update for performance
        Task.query.filter(
            Task.assigned_to_id == user_id,
            Task.status != 'concluida',
            Task.due_date < datetime.utcnow()
        ).update({Task.is_urgent: True, Task.is_important: True}, synchronize_session=False)

        # 2. Leads without follow-up (48h) -> Urgent
        # Logic: Leads ACTIVE (not won/lost) where:
        # (No interactions AND Created > 48h ago) OR (Last interaction > 48h ago)
        # Optimization: Exclude leads that HAVE an interaction in the last 48h OR were created < 48h ago.
        
        threshold_48h = datetime.utcnow() - timedelta(hours=48)
        
        # Subquery: Leads with recent interactions
        recent_interactions = db.session.query(Interaction.lead_id).filter(
            Interaction.created_at >= threshold_48h,
            Interaction.lead_id != None
        ).scalar_subquery()
        
        # Find Neglected Leads
        neglected_leads_query = db.session.query(Lead.id).filter(
            Lead.company_id == company_id,
            Lead.assigned_to_id == user_id,
            Lead.status.notin_([LEAD_STATUS_WON, LEAD_STATUS_LOST]),
            # Condition: Not created recently (grace period) AND No recent interactions
            Lead.created_at < threshold_48h,
            ~Lead.id.in_(recent_interactions)
        )
        
        neglected_lead_ids = [r[0] for r in neglected_leads_query.all()]
        
        if neglected_lead_ids:
            Task.query.filter(
                Task.lead_id.in_(neglected_lead_ids),
                Task.status != 'concluida'
            ).update({Task.is_urgent: True}, synchronize_session=False)

        # 3. Contract related tasks due soon -> Urgent
        # Bulk update
        Task.query.filter(
            Task.assigned_to_id == user_id,
            Task.contract_id != None,
            Task.status != 'concluida',
            Task.due_date <= datetime.utcnow() + timedelta(days=3)
        ).update({Task.is_urgent: True}, synchronize_session=False)

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
