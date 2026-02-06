from models import db, Task, TaskEvent, User
from datetime import datetime

class TaskService:
    @staticmethod
    def get_kanban_tasks(user_id, filters=None):
        """
        Returns tasks for a user organized by status for Kanban view.
        """
        query = Task.query.filter((Task.assigned_to_id == user_id) | (Task.created_by_user_id == user_id))
        
        if filters:
            # Implement filters here (e.g. by priority, due_date range)
            pass
            
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
    def log_event(task_id, actor_id, event_type, payload=None, actor_type='USER'):
        event = TaskEvent(
            task_id=task_id,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type=event_type,
            payload=payload
        )
        db.session.add(event)
