from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# Enums (using simple strings for MVP sqlite compatibility/simplicity)
ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'gestor'
ROLE_SALES = 'vendedor'

LEAD_STATUS_NEW = 'new'
LEAD_STATUS_IN_PROGRESS = 'in_progress'
LEAD_STATUS_WON = 'won'
LEAD_STATUS_LOST = 'lost'



# Many-to-Many relationship between User and Pipeline
user_pipeline_association = db.Table('user_pipeline_association',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('pipeline_id', db.Integer, db.ForeignKey('pipeline.id'))
)

# Many-to-Many relationship between ContractTemplate and Company (Access Control)
template_company_association = db.Table('template_company_association',
    db.Column('template_id', db.Integer, db.ForeignKey('contract_template.id')),
    db.Column('company_id', db.Integer, db.ForeignKey('company.id'))
)

# Many-to-Many relationship between LibraryBook and Company (Access Control)
library_book_company_association = db.Table('library_book_company_association',
    db.Column('book_id', db.Integer, db.ForeignKey('library_book.id')),
    db.Column('company_id', db.Integer, db.ForeignKey('company.id'))
)

class LibraryBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(50), default='Outros') # Apresentacao, Processos, Treinamento
    cover_image = db.Column(db.String(200), nullable=True) # URL or Filename
    route_name = db.Column(db.String(100), nullable=True) # For legacy static routes (e.g., 'docs.user_manual')
    content = db.Column(db.Text, nullable=True) # HTML content for new books
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Access Control Relationship
    allowed_companies = db.relationship('Company', secondary=library_book_company_association, backref=db.backref('accessible_books', lazy='dynamic'))

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    # Using JSON type for permissions (list of strings)
    # For SQLite compatibility in some versions, this maps to TEXT/JSON
    permissions = db.Column(db.JSON, nullable=True) 
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    
    users = db.relationship('User', backref='user_role', lazy=True)


class Pipeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    stages = db.relationship('PipelineStage', backref='pipeline', lazy=True, cascade="all, delete-orphan")
    leads = db.relationship('Lead', backref='pipeline', lazy=True)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    users = db.relationship('User', backref='company', lazy=True)
    # referrals to leads might be redundant if accessed via pipelines, but good for global stats
    leads = db.relationship('Lead', backref='company', lazy=True) 
    pipelines = db.relationship('Pipeline', backref='company', lazy=True)
    
    # Enhanced Contract Data
    document = db.Column(db.String(20), nullable=True) # CNPJ
    address_street = db.Column(db.String(150), nullable=True)
    address_number = db.Column(db.String(20), nullable=True)
    address_neighborhood = db.Column(db.String(100), nullable=True)
    address_city = db.Column(db.String(100), nullable=True)
    address_state = db.Column(db.String(2), nullable=True)
    address_zip = db.Column(db.String(10), nullable=True)
    representative = db.Column(db.String(100), nullable=True)
    representative_cpf = db.Column(db.String(20), nullable=True)
    
    # Branding
    logo_filename = db.Column(db.String(150), nullable=True)
    primary_color = db.Column(db.String(7), default='#fa0102') # Default Northway Red
    secondary_color = db.Column(db.String(7), default='#111827') # Default Dark Gray
    
    # SaaS Management Fields
    status = db.Column(db.String(20), default='active') # active, suspended, cancelled
    plan = db.Column(db.String(50), default='pro') # free, starter, pro, enterprise
    max_users = db.Column(db.Integer, default=5)
    max_leads = db.Column(db.Integer, default=1000)
    max_storage_gb = db.Column(db.Float, default=1.0)
    
    # Timestamps
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def address(self):
        parts = []
        if self.address_street: parts.append(self.address_street)
        if self.address_number: parts.append(f"nº {self.address_number}")
        if self.address_neighborhood: parts.append(f"- {self.address_neighborhood}")
        if self.address_city and self.address_state: parts.append(f"- {self.address_city}/{self.address_state}")
        elif self.address_city: parts.append(f"- {self.address_city}")
        if self.address_zip: parts.append(f"CEP: {self.address_zip}")
        return " ".join(parts) if parts else ""

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    supabase_uid = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_SALES) # Legacy/Fallback
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True) # New RBAC
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Nullable for Supabase Auth Triggers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Profile Fields
    profile_image = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    status_message = db.Column(db.String(100), nullable=True)
    
    # Master Access
    is_super_admin = db.Column(db.Boolean, default=False)

    # Onboarding
    onboarding_dismissed = db.Column(db.Boolean, default=False)

    leads = db.relationship('Lead', backref='assigned_user', lazy=True)
    allowed_pipelines = db.relationship('Pipeline', secondary=user_pipeline_association, backref=db.backref('allowed_users', lazy='dynamic'))

    def has_permission(self, permission):
        """
        Checks if the user has a specific permission.
        Prioritizes:
        1. Super Admin (Always True)
        2. Role-based permissions (if role_id is set)
        3. Legacy Role Fallback (if role_id is missing or permissions empty)
        """
        # 1. Super Admin
        if self.is_super_admin:
            return True

        # 2. Role-based Permissions
        if self.user_role and self.user_role.permissions:
            # permissions is a JSON list of strings
            return permission in self.user_role.permissions

        # 3. Legacy Fallback
        # Define default permissions for legacy roles
        legacy_permissions = {
            ROLE_ADMIN: [
                'dashboard_view', 'financial_view', 'leads_view', 'pipeline_view', 
                'goals_view', 'tasks_view', 'clients_view', 'whatsapp_view', 
                'company_settings_view', 'processes_view', 'library_view', 'prospecting_view', 'admin_view'
            ],
            ROLE_MANAGER: [
                'dashboard_view', 'financial_view', 'leads_view', 'pipeline_view', 
                'goals_view', 'tasks_view', 'clients_view', 'whatsapp_view', 
                'processes_view', 'library_view', 'prospecting_view'
            ],
            ROLE_SALES: [
                'dashboard_view', 'leads_view', 'pipeline_view', 'tasks_view', 
                'clients_view', 'whatsapp_view', 'prospecting_view', 'goals_view', 'library_view'
            ]
        }

        # Normalize role to lowercase to match keys (admin, gestor, vendedor)
        user_role_key = self.role.lower() if self.role else ROLE_SALES
        return permission in legacy_permissions.get(user_role_key, [])

class PipelineStage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipeline.id'), nullable=False)
    # company_id is technically redundant but useful for easy filtering
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    source = db.Column(db.String(50))
    
    status = db.Column(db.String(20), default=LEAD_STATUS_NEW)
    interest = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipeline.id'), nullable=True) # Nullable for transition / inbox
    pipeline_stage_id = db.Column(db.Integer, db.ForeignKey('pipeline_stage.id'))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    interactions = db.relationship('Interaction', backref='lead', lazy=True)
    tasks = db.relationship('Task', backref='lead', lazy=True)
    # Link back to client if converted
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)

    # BANT Methodology Fields
    bant_budget = db.Column(db.String(100), nullable=True) # Orbe/Faixa
    bant_authority = db.Column(db.String(100), nullable=True) # Decisor/Influenciador
    bant_need = db.Column(db.Text, nullable=True) # Necessidade detalhada
    bant_timeline = db.Column(db.String(100), nullable=True) # Prazo estimado
    
    # Prospecting Fields
    website = db.Column(db.String(200), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    profile_pic_url = db.Column(db.String(500), nullable=True) # WhatsApp Profile Pic

    @property
    def task_progress(self):
        total = len(self.tasks)
        if total == 0: return {'total': 0, 'completed': 0, 'percent': 0}
        completed = len([t for t in self.tasks if t.status == 'concluida'])
        return {
            'total': total,
            'completed': completed,
            'percent': int((completed / total) * 100)
        }

    @property
    def days_inactive(self):
        """Calculates days since last interaction or creation"""
        last_activity = self.created_at
        if self.interactions:
            # Sort to find the latest
            last_interaction = max(self.interactions, key=lambda x: x.created_at)
            if last_interaction.created_at > last_activity:
                last_activity = last_interaction.created_at
        
        delta = datetime.utcnow() - last_activity
        return delta.days


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    account_manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True) # Origin lead
    
    status = db.Column(db.String(20), default='onboarding') # onboarding, ativo, pausado, cancelado
    health_status = db.Column(db.String(20), default='verde') # verde, amarelo, vermelho
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    
    service = db.Column(db.String(100))
    contract_type = db.Column(db.String(50)) # mensal, trimestral, anual
    monthly_value = db.Column(db.Float)
    renewal_date = db.Column(db.Date)
    niche = db.Column(db.String(100), nullable=True) # Added Niche field
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Enhanced Contract Data
    document = db.Column(db.String(20), nullable=True) # CPF/CNPJ
    address_street = db.Column(db.String(150), nullable=True)
    address_number = db.Column(db.String(20), nullable=True)
    address_neighborhood = db.Column(db.String(100), nullable=True)
    address_city = db.Column(db.String(100), nullable=True)
    address_state = db.Column(db.String(2), nullable=True)
    address_zip = db.Column(db.String(10), nullable=True)
    representative = db.Column(db.String(100), nullable=True)
    representative_cpf = db.Column(db.String(20), nullable=True)
    email_contact = db.Column(db.String(120), nullable=True) # Specific contact email if diff from main
    profile_pic_url = db.Column(db.String(500), nullable=True) # WhatsApp Profile Pic
    
    # Relationships
    company = db.relationship('Company', backref='clients')
    account_manager = db.relationship('User', backref='managed_clients')
    # lead relationship is defined in Lead via backref or we can add here if needed, 
    # but Lead.client_id is sufficient for the link. 
    # Actually, for bidirectional access:
    origin_lead = db.relationship('Lead', backref=db.backref('converted_client', uselist=False), foreign_keys=[lead_id])
    
    interactions = db.relationship('Interaction', backref='client', lazy=True)

    @property
    def address(self):
        parts = []
        if self.address_street: parts.append(self.address_street)
        if self.address_number: parts.append(f"nº {self.address_number}")
        if self.address_neighborhood: parts.append(f"- {self.address_neighborhood}")
        if self.address_city and self.address_state: parts.append(f"- {self.address_city}/{self.address_state}")
        elif self.address_city: parts.append(f"- {self.address_city}")
        if self.address_zip: parts.append(f"CEP: {self.address_zip}")
        return " ".join(parts) if parts else ""

class ContractTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), default='contract') # contract, attachment
    content = db.Column(db.Text, nullable=False) # HTML/Text with {{variables}}
    active = db.Column(db.Boolean, default=True)
    is_global = db.Column(db.Boolean, default=False)
    is_global = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Access Control Relationship
    allowed_companies = db.relationship('Company', secondary=template_company_association, backref=db.backref('accessible_templates', lazy='dynamic'))

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('contract_template.id'), nullable=False)
    
    generated_content = db.Column(db.Text, nullable=True) # Nullable for drafts
    form_data = db.Column(db.Text, nullable=True) # JSON store for draft inputs
    status = db.Column(db.String(20), default='draft') # draft, issued, signed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref='contracts')
    company = db.relationship('Company', backref='contracts')
    template = db.relationship('ContractTemplate')

class Integration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    service = db.Column(db.String(50), nullable=False) # e.g. 'google_maps', 'whatsapp'
    api_key = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    config_json = db.Column(db.Text, nullable=True) # Extra config (instance_id, phone, etc)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WhatsAppMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    direction = db.Column(db.String(10), nullable=False) # 'in' or 'out'
    type = db.Column(db.String(20), default='text') # text, image, file
    content = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='sent') # sent, delivered, read, failed
    external_id = db.Column(db.String(100), nullable=True) # Z-API Message ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuickMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False) # e.g. "Presentation"
    content = db.Column(db.Text, nullable=False)
    shortcut = db.Column(db.String(20)) # e.g. "/intro"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True) # Allow interactions on clients too
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Who created it
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Multitenancy (Null for migration)
    type = db.Column(db.String(50), nullable=True) # ligacao, reuniao, email, nota, tarefa_criada
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False) # lead_assigned, task_assigned, task_due, lead_converted, client_status_changed
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500), nullable=True)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='notifications')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True) # Added for details
    due_date = db.Column(db.DateTime)
    priority = db.Column(db.String(20), default='media') # baixa, media, alta, urgente
    status = db.Column(db.String(20), default='pendente') # pendente, concluida
    reminder_sent = db.Column(db.Boolean, default=False)
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence = db.Column(db.String(20)) # 'mensal'
    completed_at = db.Column(db.DateTime) # New column for sorting
    
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True) # Link to client
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

    # Relationships are backref'd from Lead/Client usually, or here:
    # lead = db.relationship('Lead', backref='tasks') -- already in Lead
    client = db.relationship('Client', backref='tasks')
    responsible = db.relationship('User', foreign_keys=[assigned_to_id], backref='assigned_tasks')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Multitenancy
    description = db.Column(db.String(200), nullable=False) # e.g. "Mensalidade 1/12"
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, paid, overdue, cancelled
    paid_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ASAAS Integration Fields
    asaas_id = db.Column(db.String(50), nullable=True)
    asaas_invoice_url = db.Column(db.String(500), nullable=True)
    installment_number = db.Column(db.Integer, nullable=True)
    total_installments = db.Column(db.Integer, nullable=True)
    
    contract = db.relationship('Contract', backref=db.backref('transactions', cascade='all, delete-orphan'))

class FinancialEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True) # Optional link
    event_type = db.Column(db.String(50), nullable=False) # PAYMENT_RECEIVED, PAYMENT_OVERDUE
    payload = db.Column(db.JSON, nullable=True) # Full webhook payload
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FinancialCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False) # revenue, expense, cost
    is_default = db.Column(db.Boolean, default=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    
    expenses = db.relationship('Expense', backref='category', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='paid') # pending, paid
    
    category_id = db.Column(db.Integer, db.ForeignKey('financial_category.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Who registered it
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProcessTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    steps = db.Column(db.JSON, nullable=False) # List of sections: [{"title": "Checklist 1", "items": ["Item A"]}]
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ClientChecklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('process_template.id'), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Multitenancy
    name = db.Column(db.String(100), nullable=False)
    progress = db.Column(db.JSON, nullable=False) # Snapshot with status: [{"title": "...", "items": [{"text": "...", "done": True}]}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = db.relationship('Client', backref='checklists')
    template = db.relationship('ProcessTemplate')

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Null = Company Goal
    
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    target_amount = db.Column(db.Float, nullable=False, default=0.0)
    type = db.Column(db.String(20), default='revenue') # revenue (MRR), deals_count
    min_new_sales = db.Column(db.Float, default=0.0) # New Goal Condition


