from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

def get_now_br():
    return datetime.utcnow() - timedelta(hours=3)

db = SQLAlchemy()

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False) # UUID string
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    phone = db.Column(db.String(50), nullable=False) # Canonical E.164
    created_at = db.Column(db.DateTime, default=get_now_br)
    
    # Relationships
    leads = db.relationship('Lead', backref='contact', lazy=True)
    clients = db.relationship('Client', backref='contact', lazy=True)
    messages = db.relationship('WhatsAppMessage', backref='contact', lazy=True)

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
    created_at = db.Column(db.DateTime, default=get_now_br)
    
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
    created_at = db.Column(db.DateTime, default=get_now_br)
    
    stages = db.relationship('PipelineStage', backref='pipeline', lazy=True, cascade="all, delete-orphan")
    leads = db.relationship('Lead', backref='pipeline', lazy=True)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=get_now_br)
    
    users = db.relationship('User', backref='company', lazy=True)
    # referrals to leads might be redundant if accessed via pipelines, but good for global stats
    leads = db.relationship('Lead', backref='company', lazy=True) 
    pipelines = db.relationship('Pipeline', backref='company', lazy=True)
    
    # Enhanced Contract Data
    document = db.Column(db.String(20), nullable=True) # CNPJ (Legacy/Contract) - We might merge this with new cpf_cnpj
    cpf_cnpj = db.Column(db.String(20), unique=True, nullable=True) # Strict Identity
    
    # SaaS Subscription & Billing
    plan_id = db.Column(db.String(50), nullable=True) # UUID of the plan
    asaas_customer_id = db.Column(db.String(50), nullable=True)
    subscription_id = db.Column(db.String(50), nullable=True) # Asaas Subscription ID
    
    # Status Control
    # ENUM: trial, pending, active, overdue, blocked, canceled
    payment_status = db.Column(db.String(20), default='trial') 
    platform_inoperante = db.Column(db.Boolean, default=False) # MASTER SWITCH
    overdue_since = db.Column(db.DateTime, nullable=True) # D+0 reference
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    last_payment_at = db.Column(db.DateTime, nullable=True)
    next_due_date = db.Column(db.Date, nullable=True) # Next Invoice Date

    # Trial Control
    trial_start_date = db.Column(db.DateTime, nullable=True)
    trial_end_date = db.Column(db.DateTime, nullable=True)
    
    # Legacy fields mapping (kept for compatibility)
    subscription_status = db.Column(db.String(20), default='inactive') 
    plan_type = db.Column(db.String(20), default='free') 
    
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
    logo_base64 = db.Column(db.Text, nullable=True) 
    primary_color = db.Column(db.String(7), default='#fa0102') 
    secondary_color = db.Column(db.String(7), default='#111827') 
    
    # SaaS Management Fields
    status = db.Column(db.String(20), default='active') 
    plan = db.Column(db.String(50), default='pro') 
    max_users = db.Column(db.Integer, default=5)
    max_leads = db.Column(db.Integer, default=1000)
    max_storage_gb = db.Column(db.Float, default=1.0)
    
    # Timestamps
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = db.Column(db.DateTime, nullable=True)

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
    role = db.Column(db.String(20), nullable=False, default=ROLE_SALES) # Legacy/Fallback
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True) # New RBAC
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Nullable for Supabase Auth Triggers
    created_at = db.Column(db.DateTime, default=get_now_br)
    last_login = db.Column(db.DateTime, nullable=True)

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
    contact_uuid = db.Column(db.String(36), db.ForeignKey('contact.uuid'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_now_br)
    
    interactions = db.relationship('Interaction', backref='lead', lazy=True)
    tasks = db.relationship('Task', backref='lead', lazy=True)
    pipeline_stage = db.relationship('PipelineStage', backref='stage_leads')
    # Link back to client if converted
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)

    # BANT Methodology Fields
    bant_budget = db.Column(db.String(100), nullable=True) # Orbe/Faixa
    bant_authority = db.Column(db.String(100), nullable=True) # Decisor/Influenciador
    bant_need = db.Column(db.Text, nullable=True) # Necessidade detalhada
    bant_timeline = db.Column(db.String(100), nullable=True) # Prazo estimado
    
    # Prospecting & Enrichment Fields
    website = db.Column(db.String(200), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    profile_pic_url = db.Column(db.String(500), nullable=True) # WhatsApp Profile Pic

    # GMB / Maps Data
    gmb_link = db.Column(db.String(500), nullable=True)
    gmb_rating = db.Column(db.Float, default=0.0)
    gmb_reviews = db.Column(db.Integer, default=0)
    gmb_photos = db.Column(db.Integer, default=0)
    gmb_last_sync = db.Column(db.DateTime, nullable=True)
    
    # CNPJ Enrichment
    legal_name = db.Column(db.String(200), nullable=True) # Razão Social
    cnpj = db.Column(db.String(20), nullable=True)
    registration_status = db.Column(db.String(50), nullable=True) # Situação Cadastral
    company_size = db.Column(db.String(50), nullable=True) # Porte
    equity = db.Column(db.Float, nullable=True) # Capital Social
    foundation_date = db.Column(db.String(20), nullable=True) # Data de Abertura
    legal_email = db.Column(db.String(120), nullable=True) # Email na Receita
    legal_phone = db.Column(db.String(50), nullable=True) # Telefone na Receita
    cnae = db.Column(db.String(200), nullable=True) # Atividade Principal
    partners_json = db.Column(db.Text, nullable=True) # List of partners
    enrichment_history = db.Column(db.Text, nullable=True) # Log of updates

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
    
    created_at = db.Column(db.DateTime, default=get_now_br)
    contact_uuid = db.Column(db.String(36), db.ForeignKey('contact.uuid'), nullable=True)

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
    
    # GMB / Maps Data
    gmb_link = db.Column(db.String(500), nullable=True)
    gmb_rating = db.Column(db.Float, default=0.0)
    gmb_reviews = db.Column(db.Integer, default=0)
    gmb_photos = db.Column(db.Integer, default=0)
    gmb_last_sync = db.Column(db.DateTime, nullable=True)

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
    description = db.Column(db.String(500), nullable=True)
    type = db.Column(db.String(20), default='contract') # contract, attachment, library_doc
    content = db.Column(db.Text, nullable=False) # HTML/Text with {{variables}}
    active = db.Column(db.Boolean, default=True)
    is_global = db.Column(db.Boolean, default=False)
    is_library = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_now_br)
    
    # Access Control Relationship
    allowed_companies = db.relationship('Company', secondary=template_company_association, backref=db.backref('accessible_templates', lazy='dynamic'))

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('contract_template.id'), nullable=False)
    
    code = db.Column(db.String(50), nullable=True) # Unique Identification Code (e.g. CTR-2024-001)
    
    generated_content = db.Column(db.Text, nullable=True) # Nullable for drafts
    form_data = db.Column(db.Text, nullable=True) # JSON store for draft inputs
    status = db.Column(db.String(20), default='draft') # draft, issued, signed
    contact_uuid = db.Column(db.String(36), db.ForeignKey('contact.uuid'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_now_br)
    
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
    last_error = db.Column(db.Text, nullable=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)
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
    phone = db.Column(db.String(50), nullable=True) # For unknown contacts
    sender_name = db.Column(db.String(100), nullable=True) # From WhatsApp profile
    profile_pic_url = db.Column(db.String(500), nullable=True) # URL from webhook
    attachment_url = db.Column(db.String(1000), nullable=True) # Media URL (image, audio, etc.)
    contact_uuid = db.Column(db.String(36), db.ForeignKey('contact.uuid'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_now_br)

class QuickMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False) # e.g. "Presentation"
    content = db.Column(db.Text, nullable=False)
    shortcut = db.Column(db.String(20)) # e.g. "/intro"

    created_at = db.Column(db.DateTime, default=get_now_br)

class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True) # Allow interactions on clients too
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Who created it
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Multitenancy (Null for migration)
    type = db.Column(db.String(50), nullable=True) # ligacao, reuniao, email, nota, tarefa_criada
    content = db.Column(db.Text, nullable=True)
    contact_uuid = db.Column(db.String(36), db.ForeignKey('contact.uuid'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_now_br)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False) # lead_assigned, task_assigned, task_due, lead_converted, client_status_changed
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500), nullable=True)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_now_br)
    
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
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'), nullable=True) # Now nullable for manual charges
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True) # Direct link for easier querying/manual charges
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Multitenancy
    description = db.Column(db.String(200), nullable=False) # e.g. "Mensalidade 1/12"
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, paid, overdue, cancelled
    paid_date = db.Column(db.Date, nullable=True)
    contact_uuid = db.Column(db.String(36), db.ForeignKey('contact.uuid'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_now_br)
    
    # ASAAS Integration Fields
    asaas_id = db.Column(db.String(50), nullable=True)
    asaas_invoice_url = db.Column(db.String(500), nullable=True)
    installment_number = db.Column(db.Integer, nullable=True)
    total_installments = db.Column(db.Integer, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    
    contract = db.relationship('Contract', backref=db.backref('transactions', cascade='all, delete-orphan'))
    client = db.relationship('Client', backref=db.backref('transactions', lazy=True))

class BillingEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Nullable if we can't identify company yet
    event_type = db.Column(db.String(50), nullable=False) # PAYMENT_RECEIVED, PAYMENT_OVERDUE
    payload = db.Column(db.JSON, nullable=True) # Full webhook payload
    processed_at = db.Column(db.DateTime, nullable=True)
    idempotency_key = db.Column(db.String(100), unique=True, nullable=True) # payment_id + event
    created_at = db.Column(db.DateTime, default=get_now_br)

class FinancialEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True) # Optional link
    event_type = db.Column(db.String(50), nullable=False) # PAYMENT_RECEIVED, PAYMENT_OVERDUE
    payload = db.Column(db.JSON, nullable=True) # Full webhook payload
    created_at = db.Column(db.DateTime, default=get_now_br)

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
    
    created_at = db.Column(db.DateTime, default=get_now_br)

class ProcessTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    steps = db.Column(db.JSON, nullable=False) # List of sections: [{"title": "Checklist 1", "items": ["Item A"]}]
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_now_br)

class ClientChecklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('process_template.id'), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True) # Multitenancy
    name = db.Column(db.String(100), nullable=False)
    progress = db.Column(db.JSON, nullable=False) # Snapshot with status: [{"title": "...", "items": [{"text": "...", "done": True}]}]
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=get_now_br)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = db.relationship('Client', backref='checklists')
    template = db.relationship('ProcessTemplate')
    assigned_to = db.relationship('User', backref='assigned_checklists')

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Null = Company Goal
    
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    target_amount = db.Column(db.Float, nullable=False, default=0.0)
    type = db.Column(db.String(20), default='revenue') # revenue (MRR), deals_count
    min_new_sales = db.Column(db.Float, default=0.0) # New Goal Condition


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_hash = db.Column(db.String(128), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_now_br)

    user = db.relationship('User', backref=db.backref('reset_tokens', lazy=True))

from enum import Enum

class EMAIL_TEMPLATES(Enum):
    welcome = "welcome"
    verify_email = "verify_email"
    reset_password = "reset_password"
    password_changed = "password_changed"
    invite_user = "invite_user"
    new_login = "new_login"
    subscription_active = "subscription_active"
    trial_expired = "trial_expired"

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    email_to = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    template = db.Column(db.String(50), nullable=True) # Stores the ENUM value
    status = db.Column(db.String(50), default='sent') # sent, failed, delivered
    provider = db.Column(db.String(50), default='resend')
    provider_message_id = db.Column(db.String(100), nullable=True) # Resend ID
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_now_br)

    company = db.relationship('Company', backref='email_logs')
    user = db.relationship('User', backref='email_logs')

    @classmethod
    def create_log(cls, company_id, user_id, email_to, subject, status, provider='resend', error_message=None, provider_message_id=None, template=None):
        try:
            # Validate Template if provided
            template_val = None
            if template:
                if isinstance(template, EMAIL_TEMPLATES):
                    template_val = template.value
                elif isinstance(template, str) and template in [e.value for e in EMAIL_TEMPLATES]:
                     template_val = template
                else:
                     # Log warning but don't crash, or strictly enforce? 
                     # User said: "Não permitir valores fora dessa ENUM (validação em runtime...)"
                     # We will strictly enforce in EmailService, here we just store.
                     template_val = str(template)

            log = cls(
                company_id=company_id,
                user_id=user_id,
                email_to=email_to,
                subject=subject,
                template=template_val,
                status=status,
                provider=provider,
                error_message=error_message,
                provider_message_id=provider_message_id
            )
            db.session.add(log)
            db.session.commit()
            return log
        except Exception as e:
            print(f"Error saving email log: {e}")
            db.session.rollback()
            return None

class ServiceOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    value = db.Column(db.Float, default=0.0)
    
    # Status: SOLICITADA, AGUARDANDO_ACEITE, AGUARDANDO_PAGAMENTO, AUTORIZADA, EM_EXECUCAO, CONCLUIDA, CANCELADA
    status = db.Column(db.String(50), default='SOLICITADA')
    
    # Asaas Integration
    asaas_payment_id = db.Column(db.String(50), nullable=True)
    asaas_invoice_url = db.Column(db.String(500), nullable=True)
    
    # Cancellation Audit
    canceled_at = db.Column(db.DateTime, nullable=True)
    canceled_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # cancel_category: DESISTENCIA_CLIENTE, ERRO_CADASTRO, DUPLICIDADE, ALTERACAO_DE_ESCOPO, INADIMPLENCIA, OUTROS
    cancel_category = db.Column(db.String(50), nullable=True)
    cancel_reason = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=get_now_br)
    updated_at = db.Column(db.DateTime, default=get_now_br, onupdate=get_now_br)

    client = db.relationship('Client', backref=db.backref('service_orders', lazy=True))
    canceled_by = db.relationship('User', foreign_keys=[canceled_by_user_id])
