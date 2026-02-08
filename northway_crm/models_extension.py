
# ... existing code ...

# ==========================================
# DIAGNOSTIC FORM SYSTEM MODELS
# ==========================================

class LibraryTemplate(db.Model):
    __tablename__ = 'library_template'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = db.Column(db.String(50), unique=True, nullable=False) # e.g., "diagnostico_northway_v1"
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    schema_json = db.Column(db.JSON, nullable=False) # Questions, options, scoring rules
    version = db.Column(db.Integer, default=1)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_now_br)
    updated_at = db.Column(db.DateTime, default=get_now_br, onupdate=get_now_br)

class LibraryTemplateGrant(db.Model):
    __tablename__ = 'library_template_grant'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False) # Maps to Company
    template_id = db.Column(db.String(36), db.ForeignKey('library_template.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    granted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='active') # active, revoked
    created_at = db.Column(db.DateTime, default=get_now_br)
    updated_at = db.Column(db.DateTime, default=get_now_br, onupdate=get_now_br)

    __table_args__ = (db.UniqueConstraint('tenant_id', 'template_id', 'user_id', name='unique_grant'),)

class FormInstance(db.Model):
    __tablename__ = 'form_instance'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    template_id = db.Column(db.String(36), db.ForeignKey('library_template.id'), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    public_slug = db.Column(db.String(100), unique=True, nullable=False) # Random slug
    status = db.Column(db.String(20), default='active') # active, inactive
    created_at = db.Column(db.DateTime, default=get_now_br)
    updated_at = db.Column(db.DateTime, default=get_now_br, onupdate=get_now_br)

    __table_args__ = (db.UniqueConstraint('tenant_id', 'template_id', 'owner_user_id', name='unique_instance'),)
    
    # Relations
    template = db.relationship('LibraryTemplate', backref='instances')
    owner = db.relationship('User', foreign_keys=[owner_user_id], backref='form_instances')
    company = db.relationship('Company', backref='form_instances')

class FormSubmission(db.Model):
    __tablename__ = 'form_submission'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    form_instance_id = db.Column(db.String(36), db.ForeignKey('form_instance.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=True)
    
    payload = db.Column(db.JSON, nullable=False) # Answers
    
    # Scoring
    score_total = db.Column(db.Integer, default=0)
    score_atrair = db.Column(db.Integer, default=0)
    score_engajar = db.Column(db.Integer, default=0)
    score_vender = db.Column(db.Integer, default=0)
    score_reter = db.Column(db.Integer, default=0)
    
    stars = db.Column(db.Float, default=0.0) # Numeric(2,1)
    classification = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=get_now_br)
    
    # Relations
    instance = db.relationship('FormInstance', backref='submissions')
    lead = db.relationship('Lead', backref='submissions')
