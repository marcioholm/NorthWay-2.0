
from flask import Blueprint, request, jsonify, current_app, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, FormInstance, User, LibraryTemplate, LibraryTemplateGrant, FormSubmission
from services.form_service import FormService
import secrets
import re

forms_bp = Blueprint('forms', __name__)

# ==========================================
# PUBLIC ROUTES
# ==========================================

@forms_bp.route('/public/<slug>', methods=['GET'])
def get_form_schema(slug):
    """
    Public Endpoint: Get Form Schema & Access Token
    """
    instance = FormInstance.query.filter_by(public_slug=slug, status='active').first()
    if not instance:
        return jsonify({"error": "Form not found or inactive"}), 404
        
    # Generate Token
    token = FormService.generate_public_token(instance.id)
    
    # Get Company Logo
    company_logo = None
    if instance.owner.company:
        if instance.owner.company.logo_filename:
             company_logo = url_for('static', filename='uploads/logos/' + instance.owner.company.logo_filename, _external=True)
        elif instance.owner.company.logo_base64:
             company_logo = instance.owner.company.logo_base64
             
    # Default fallback
    if not company_logo:
        company_logo = "https://crm.northwaycompany.com.br/static/img/logo-white.png?v=2"

    return render_template('forms/public_diagnostic.html', 
        instance=instance, 
        token=token, 
        schema=instance.template.schema_json,
        company_logo=company_logo
    )

@forms_bp.route('/public/submit', methods=['POST'])
def submit_form():
    """
    Public Endpoint: Submit Form
    Header: Authorization: Bearer <token>
    Body: { slug: "...", contact: {...}, answers: {...} }
    """
    # 1. Get Token
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Missing or invalid token"}), 401
    
    token = auth_header.split(' ')[1]
    
    # 2. Get Payload
    data = request.json
    slug = data.get('slug')
    
    if not slug:
        return jsonify({"error": "Missing slug"}), 400
        
    instance = FormInstance.query.filter_by(public_slug=slug, status='active').first()
    if not instance:
        return jsonify({"error": "Form not found"}), 404
        
    # 3. Verify Token
    if not FormService.verify_token(token, instance.id):
        return jsonify({"error": "Invalid or expired token"}), 401
        
    # 4. Process
    try:
        submission = FormService.process_submission(instance, data)
        
        return jsonify({
            "status": "success",
            "results": {
                "score_total": submission.score_total,
                "stars": submission.stars,
                "classification": submission.classification,
                "pillars": {
                    "Atrair": submission.score_atrair,
                    "Engajar": submission.score_engajar,
                    "Vender": submission.score_vender,
                    "Reter": submission.score_reter
                }
            }
        })
    except Exception as e:
        current_app.logger.error(f"Form Submission Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

# ==========================================
# INTERNAL ROUTES (USER PANEL)
# ==========================================

@forms_bp.route('/my-diagnostic')
@login_required
def my_diagnostic():
    key = "diagnostico_northway_v1"
    template = LibraryTemplate.query.filter_by(key=key).first()
    
    if not template:
        # Fallback if migration hasn't run
        return render_template('error.html', message="Template de diagnóstico não encontrado."), 404

    # Check Grant
    grant = LibraryTemplateGrant.query.filter_by(
        user_id=current_user.id, 
        template_id=template.id, 
        status='active'
    ).first()
    
    if not grant:
        # Check if user is Super Admin -> Auto Grant
        if getattr(current_user, 'is_super_admin', False) or current_user.email == 'master@northway.com':
             grant = LibraryTemplateGrant(
                 tenant_id=current_user.company_id,
                 template_id=template.id,
                 user_id=current_user.id,
                 granted_by_user_id=current_user.id,
                 status='active'
             )
             db.session.add(grant)
             db.session.commit()
        else:
            return render_template('forms/no_access.html')

    # Get/Create Instance
    instance = FormInstance.query.filter_by(
        owner_user_id=current_user.id,
        template_id=template.id,
        tenant_id=current_user.company_id
    ).first()
    
    if not instance:
        # Create Instance
        slug_base = f"diagnostico-{current_user.name.split()[0].lower()}-{secrets.token_hex(4)}"
        # Sanitize slug
        slug_base = re.sub(r'[^a-zA-Z0-9-]', '', slug_base)
        
        instance = FormInstance(
            tenant_id=current_user.company_id,
            template_id=template.id,
            owner_user_id=current_user.id,
            public_slug=slug_base,
            status='active'
        )
        db.session.add(instance)
        db.session.commit()
        
    # Get Submissions
    submissions = FormSubmission.query.filter_by(form_instance_id=instance.id).order_by(FormSubmission.created_at.desc()).all()
    
    
    # Calculate Stats
    total_leads = len(set(s.lead_id for s in submissions if s.lead_id))
    avg_stars = 0
    if submissions:
        avg_stars = sum(s.stars for s in submissions) / len(submissions)

    # Admin Context Data
    company_users = []
    grants_map = {}
    
    if current_user.is_super_admin:
        # Super Admin sees ALL users
        company_users = User.query.order_by(User.company_id, User.name).all()
        # Fetch active grants for ALL users
        active_grants = LibraryTemplateGrant.query.filter(
            LibraryTemplateGrant.template_id == template.id,
            LibraryTemplateGrant.status == 'active'
        ).all()
        grants_map = {g.user_id: True for g in active_grants}
        
    elif current_user.role == 'admin':
        # Company Admin sees users in their company
        company_users = User.query.filter_by(company_id=current_user.company_id).all()
        active_grants = LibraryTemplateGrant.query.filter(
            LibraryTemplateGrant.user_id.in_([u.id for u in company_users]),
            LibraryTemplateGrant.template_id == template.id,
            LibraryTemplateGrant.status == 'active'
        ).all()
        grants_map = {g.user_id: True for g in active_grants}
    
    return render_template('forms/my_diagnostic.html',  
                         instance=instance, 
                         submissions=submissions,
                         stats={'total': len(submissions), 'leads': total_leads, 'avg_stars': round(avg_stars, 1)},
                         company_users=company_users,
                         grants_map=grants_map)

# ==========================================
# ADMIN ACCESS MANAGEMENT
# ==========================================

@forms_bp.route('/access/grant', methods=['POST'])
@login_required
def grant_access():
    if not (current_user.is_super_admin or current_user.role == 'admin'):
        return jsonify({"error": "Unauthorized"}), 403
        
    user_id = request.form.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400
        
    # Get Template
    key = "diagnostico_northway_v1"
    template = LibraryTemplate.query.filter_by(key=key).first()
    if not template:
        return jsonify({"error": "Template not initialized"}), 500
        
    # Check existing
    grant = LibraryTemplateGrant.query.filter_by(
        user_id=user_id, 
        template_id=template.id
    ).first()
    
    if grant:
        grant.status = 'active'
    else:
        grant = LibraryTemplateGrant(
             tenant_id=current_user.company_id,
             template_id=template.id,
             user_id=user_id,
             granted_by_user_id=current_user.id,
             status='active'
         )
        db.session.add(grant)
        
    db.session.commit()
    flash('Acesso liberado com sucesso!', 'success')
    return redirect(url_for('forms.my_diagnostic'))

@forms_bp.route('/access/revoke', methods=['POST'])
@login_required
def revoke_access():
    if not (current_user.is_super_admin or current_user.role == 'admin'):
        return jsonify({"error": "Unauthorized"}), 403
        
    user_id = request.form.get('user_id')
    # Get Template
    key = "diagnostico_northway_v1"
    template = LibraryTemplate.query.filter_by(key=key).first()
    
    grant = LibraryTemplateGrant.query.filter_by(
        user_id=user_id, 
        template_id=template.id
    ).first()
    
    if grant:
        grant.status = 'revoked'
        db.session.commit()
        
    flash('Acesso revogado.', 'warning')
    return redirect(url_for('forms.my_diagnostic'))
