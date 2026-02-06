from models import db, Task, Lead, Contract, ServiceOrder
from datetime import datetime, timedelta
from services.task_service import TaskService

class AutomationService:
    @staticmethod
    def check_leads_followup():
        """
        Rule 1: Leads without interaction for X days.
        """
        # Config: 3 days default
        days_limit = 3
        limit_date = datetime.utcnow() - timedelta(days=days_limit)
        
        # Find leads with last status update or creation before limit_date
        # Ideally we check interactions, but assuming created_at/updated_at for MVP
        leads = Lead.query.filter(
            Lead.status != 'won', 
            Lead.status != 'lost',
            Lead.created_at < limit_date
            # Simple logic: check if ANY task exists, if not create one?
            # Or strict "no interaction". MVP: Create task if no OPEN task exists.
        ).all()
        
        created_count = 0
        for lead in leads:
            # Check if there is an active task
            has_task = Task.query.filter_by(
                lead_id=lead.id, 
                status='a_fazer'
            ).first()
            
            if not has_task:
                 TaskService.create_task({
                     'title': f"Follow-up: {lead.name}",
                     'description': "Lead sem interação recente. Entrar em contato.",
                     'priority': 'media',
                     'due_date': datetime.utcnow(),
                     'company_id': lead.company_id,
                     'assigned_to_id': lead.assigned_to_id, # Owner
                     'source_type': 'LEAD',
                     'auto_generated': True,
                     'lead_id': lead.id
                 }, user_id=None) # System
                 created_count += 1
                 
        return created_count

    @staticmethod
    def handle_new_contract(contract):
        """
        Rule 4: New Contract -> Onboarding Task
        """
        try:
             # Find Account Manager of Client
            responsible_id = contract.client.account_manager_id if contract.client.account_manager_id else contract.company.users[0].id

            TaskService.create_task({
                 'title': f"Onboarding: {contract.client.name}",
                 'description': "Realizar reuni?o de onboarding e configurar ambiente.",
                 'priority': 'media',
                 'due_date': datetime.utcnow() + timedelta(days=2),
                 'company_id': contract.company_id,
                 'assigned_to_id': responsible_id,
                 'source_type': 'CONTRACT',
                 'auto_generated': True,
                 'contract_id': contract.id,
                 'client_id': contract.client_id
             }, user_id=None)
        except Exception as e:
            print(f"Error autom. new contract: {e}")

    @staticmethod
    def handle_os_paid(service_order):
        """
        Rule 2: OS Paid -> Execute Task
        """
        TaskService.create_task({
             'title': f"Executar OS #{service_order.id}",
             'description': f"Servi?o: {service_order.title}",
             'priority': 'alta',
             'due_date': datetime.utcnow() + timedelta(days=5), # Default SLA
             'company_id': service_order.company_id,
             'assigned_to_id': service_order.created_by_user_id or service_order.company.users[0].id, # Fallback
             'source_type': 'SERVICE_ORDER',
             'auto_generated': True,
             'service_order_id': service_order.id,
             'client_id': service_order.client_id
         }, user_id=None)

    @staticmethod
    def check_os_overdue():
        """
        Rule 3: OS Overdue -> Collection Task
        """
        overdue_os = ServiceOrder.query.filter(
            ServiceOrder.status == 'AGUARDANDO_PAGAMENTO',
            ServiceOrder.created_at < (datetime.utcnow() - timedelta(days=1)) # simple check logic, ideally due_date
        ).all()
        
        for os in overdue_os:
             # Check if task already exists
            has_task = Task.query.filter_by(
                service_order_id=os.id, 
                title=f"Cobrar Pagamento OS #{os.id}"
            ).first()
            
            if not has_task:
                 TaskService.create_task({
                     'title': f"Cobrar Pagamento OS #{os.id}",
                     'description': "Cliente em atraso.",
                     'priority': 'urgente',
                     'due_date': datetime.utcnow(),
                     'company_id': os.company_id,
                     'assigned_to_id': os.created_by_user_id,
                     'source_type': 'SERVICE_ORDER',
                     'auto_generated': True,
                     'service_order_id': os.id,
                     'client_id': os.client_id
                 }, user_id=None)
