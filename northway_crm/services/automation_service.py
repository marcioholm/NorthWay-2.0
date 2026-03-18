from models import db, Task, Lead, Contract, ServiceOrder
from datetime import datetime, timedelta
from services.task_service import TaskService

class AutomationService:
    @staticmethod
    def check_leads_followup():
        """
        Main logic for the BDR cadence.
        Refactored to pull steps from AutomationRule in the database.
        """
        from models import Lead, Task, AutomationRule
        from services.task_service import TaskService
        from datetime import datetime
        
        # 1. Fetch all leads that are not won/lost
        leads = Lead.query.filter(
            Lead.status != 'won', 
            Lead.status != 'lost'
        ).all()
        
        if not leads:
            return 0
            
        created_count = 0
        now = datetime.utcnow()
        
        # We group rules by company to avoid redundant queries in the loop if needed,
        # but since we are usually running in a context of one company (triggered by CRON or user),
        # we can fetch rules per lead's company if they differ, or just the current context.
        # For this implementation, we'll assume we process rules for all companies found in the leads list.
        company_ids = set(l.company_id for l in leads if l.company_id)
        
        for comp_id in company_ids:
            # Fetch active BDR Cadence rules for this company
            bdr_rules_list = AutomationRule.query.filter_by(
                company_id=comp_id, 
                trigger_type='lead_age', 
                active=True
            ).all()
            
            if not bdr_rules_list:
                continue
                
            bdr_rules = {rule.target_day: rule for rule in bdr_rules_list}
            comp_leads = [l for l in leads if l.company_id == comp_id]
            
            for lead in comp_leads:
                if not lead.created_at:
                    continue
                    
                days_elapsed = (now - lead.created_at).days
                
                # Check if we have a rule for this specific age
                if days_elapsed in bdr_rules:
                    rule = bdr_rules[days_elapsed]
                    
                    # Expected title uses the rule name to ensure uniqueness for that day
                    expected_title = f"{rule.name}: {lead.name}"
                    
                    # Check if a task for this specific cadence step already exists for this lead
                    has_task_for_step = Task.query.filter_by(
                        lead_id=lead.id, 
                        title=expected_title
                    ).first()
                    
                    if not has_task_for_step:
                         TaskService.create_task({
                             'title': expected_title,
                             'description': rule.description_template or rule.message_template or f"Cadência BDR Dia {days_elapsed}",
                             'priority': rule.priority or 'media',
                             'due_date': now,
                             'company_id': lead.company_id,
                             'assigned_to_id': lead.assigned_to_id,
                             'source_type': 'LEAD',
                             'auto_generated': True,
                             'lead_id': lead.id
                         }, user_id=None)
                         created_count += 1
                         
        db.session.commit()
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
