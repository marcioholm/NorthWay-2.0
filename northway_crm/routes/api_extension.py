from flask import Blueprint, request, jsonify, current_app, redirect
from models import db, User, Lead, Client, Pipeline, PipelineStage, Task, Interaction
from flask_login import login_user
import jwt
import datetime
from functools import wraps
from werkzeug.security import check_password_hash

api_ext = Blueprint('api_ext', __name__)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                raise Exception('User not found')
        except Exception as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

@api_ext.route('/api/ext/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Could not verify', 'error': 'Missing credentials'}), 401

    user = User.query.filter_by(email=data.get('email')).first()
    
    if not user:
         return jsonify({'message': 'Could not verify', 'error': 'User not found'}), 401

    if check_password_hash(user.password_hash, data.get('password')):
        token = jwt.encode({
            'user_id': user.id,
            'company_id': user.company_id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }, current_app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'company_id': user.company_id,
                'avatar_url': f"{request.host_url.rstrip('/')}/static/uploads/profiles/{user.profile_image}" if user.profile_image else None
            }
        })
    
    return jsonify({'message': 'Could not verify', 'error': 'Wrong password'}), 401

@api_ext.route('/api/ext/verify', methods=['GET'])
@token_required
def verify_token(current_user):
    return jsonify({
        'valid': True,
        'user': {
            'id': current_user.id,
            'name': current_user.name,
            'email': current_user.email,
            'company_id': current_user.company_id,
            'avatar_url': f"{request.host_url.rstrip('/')}/static/uploads/profiles/{current_user.profile_image}" if current_user.profile_image else None
        }
    })

@api_ext.route('/seed-fix')
def seed_fix_manual():
    try:
        from models import db
        import traceback
        
        # 1. Ensure Tables Exist
        db.create_all()
        
        # 2. Run Rich Data Seeder using ORM
        from seed_orm import seed_rich_data
        seed_rich_data(db.session, user_email="admin@northway.com")
        
        # 3. Verify Data
        from models import Client, Lead, Transaction, User, Contract, Task
        u = User.query.filter_by(email="admin@northway.com").first()
        cid = u.company_id if u else "None"
        
        clients = Client.query.filter_by(company_id=cid).count()
        leads = Lead.query.filter_by(company_id=cid).count()
        transactions = Transaction.query.filter_by(company_id=cid).count()
        contracts_count = Contract.query.filter_by(company_id=cid).count()
        tasks_count = Task.query.filter_by(company_id=cid).count()
            
        return jsonify({
            "status": "success", 
            "message": "Rich Data Seeding Complete.",
            "debug": {
                "user_email": "admin@northway.com",
                "company_id": cid,
                "clients_count": clients,
                "leads_count": leads,
                "transactions_count": transactions,
                "contracts_count": contracts_count,
                "tasks_count": tasks_count,
                "db_url": str(db.engine.url)
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fix failed: {str(e)}", "trace": traceback.format_exc()}), 500

@api_ext.route('/extension/check-auth', methods=['GET'])
def sso_jump():
    token = request.args.get('token')
    if not token:
        return redirect('https://crm.northwaycompany.com.br/login')
    
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        user = User.query.get(data['user_id'])
        
        if user:
            # Establish the browser session
            login_user(user, remember=True)
            return redirect('https://crm.northwaycompany.com.br/home')
        
    except Exception as e:
        print(f"SSO Jump Error: {str(e)}")
        
    return redirect('https://crm.northwaycompany.com.br/login')

# --- Contact Management ---

@api_ext.route('/api/ext/contact/search', methods=['GET'])
@token_required
def search_contact(current_user):
    phone = request.args.get('phone')
    name_query = request.args.get('name')
    
    if not phone and not name_query:
        return jsonify({'error': 'Phone or Name parameter required'}), 400
        
    lead = None
    client = None
    
    # 1. Search by Phone
    if phone:
        clean_phone = ''.join(filter(str.isdigit, phone))
        if len(clean_phone) > 6: # Minimum length to avoid false positives
            lead = Lead.query.filter(
                Lead.company_id == current_user.company_id,
                Lead.phone.ilike(f'%{clean_phone}%') 
            ).first()
            
            if not lead:
                client = Client.query.filter(
                    Client.company_id == current_user.company_id,
                    Client.phone.ilike(f'%{clean_phone}%')
                ).first()

    # 2. Search by Name (Fallback)
    if not lead and not client and name_query:
        # Simple name match (insensitive)
        lead = Lead.query.filter(
            Lead.company_id == current_user.company_id,
            Lead.name.ilike(f'%{name_query}%')
        ).first()
        
        if not lead:
             client = Client.query.filter(
                Client.company_id == current_user.company_id,
                Client.name.ilike(f'%{name_query}%')
            ).first()
    
    if lead:
        return jsonify({
            'type': 'lead',
            'data': {
                'id': lead.id,
                'name': lead.name,
                'phone': lead.phone,
                'status': lead.status,
                'pipeline_stage_id': lead.pipeline_stage_id,
                'pipeline_id': lead.pipeline_id,
                'notes': lead.notes,
                'bant_need': lead.bant_need
            }
        })
        
    if client:
        return jsonify({
            'type': 'client',
            'data': {
                'id': client.id,
                'name': client.name,
                'phone': client.phone,
                'status': client.status,
                'notes': client.notes
            }
        })
        
    return jsonify({'found': False}), 404

@api_ext.route('/api/ext/pipelines', methods=['GET'])
@token_required
def get_pipelines(current_user):
    pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
    result = []
    
    for p in pipelines:
        stages = PipelineStage.query.filter_by(pipeline_id=p.id).order_by(PipelineStage.order).all()
        result.append({
            'id': p.id,
            'name': p.name,
            'stages': [{'id': s.id, 'name': s.name, 'order': s.order} for s in stages]
        })
        
    return jsonify(result)

@api_ext.route('/api/ext/leads', methods=['POST'])
@token_required
def create_lead(current_user):
    data = request.get_json()
    
    name = data.get('name')
    phone = data.get('phone')
    
    if not name or not phone:
        return jsonify({'error': 'Name and phone required'}), 400
        
    # Get Metadata
    pipeline_id = data.get('pipeline_id')
    stage_id = data.get('stage_id') or data.get('pipeline_stage_id')
    
    # If stage is selected, ensure we use its pipeline
    if stage_id:
        stage = PipelineStage.query.get(stage_id)
        if stage and stage.company_id == current_user.company_id:
            pipeline_id = stage.pipeline_id
    
    # If no pipeline specified (and no valid stage), get default
    if not pipeline_id:
        pipeline = Pipeline.query.filter_by(company_id=current_user.company_id).first()
        if pipeline:
            pipeline_id = pipeline.id
            if not stage_id:
                stage = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).first()
                if stage:
                    stage_id = stage.id
    
    new_lead = Lead(
        name=name,
        phone=phone,
        email=data.get('email'),
        source="WhatsApp Extension",
        notes=data.get('notes'),
        company_id=current_user.company_id,
        status='new',
        assigned_to_id=current_user.id,
        pipeline_id=pipeline_id,
        pipeline_stage_id=stage_id,
        bant_need=data.get('bant_need'),
        profile_pic_url=data.get('avatar_url')
    )
    
    db.session.add(new_lead)
    db.session.flush() # Flush to get ID
    
    # Create Interaction for the Note (so it appears in timeline)
    if new_lead.notes:
        interaction = Interaction(
             lead_id=new_lead.id,
             user_id=current_user.id,
             company_id=current_user.company_id,
             type='note',
             content=new_lead.notes,
             created_at=datetime.datetime.utcnow()
        )
        db.session.add(interaction)

    db.session.commit()
    
    return jsonify({
        'success': True, 
        'lead': {
            'id': new_lead.id,
            'name': new_lead.name,
            'phone': new_lead.phone,
            'status': new_lead.status,
            'pipeline_stage_id': new_lead.pipeline_stage_id,
            'pipeline_id': new_lead.pipeline_id,
            'notes': new_lead.notes,
            'bant_need': new_lead.bant_need
        }
    })

@api_ext.route('/api/ext/leads/<int:id>', methods=['PUT'])
@token_required
def update_lead(current_user, id):
    lead = Lead.query.get_or_404(id)
    
    if lead.company_id != current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    
    if 'notes' in data:
        old_notes = lead.notes
        lead.notes = data['notes']
        
        # Determine if we should create a timeline event
        # Only if content changed and is not empty
        if lead.notes and lead.notes != old_notes:
            interaction = Interaction(
                lead_id=lead.id,
                user_id=current_user.id,
                company_id=current_user.company_id,
                type='note',
                content=lead.notes, # Or f"Nota atualizada via extensão: {lead.notes}"
                created_at=datetime.datetime.utcnow()
            )
            db.session.add(interaction)
        
    if 'pipeline_stage_id' in data:
        lead.pipeline_stage_id = data['pipeline_stage_id']
        lead.status = 'in_progress' # Auto update status if stage moves
        
    if 'bant_need' in data: # Using this for tags roughly
        lead.bant_need = data['bant_need']
        
    if 'avatar_url' in data:
        lead.profile_pic_url = data['avatar_url']
        
    db.session.commit()
    
    return jsonify({'success': True})

@api_ext.route('/debug-status')
def debug_status():
    """Diagnostic route to check WHY the user sees nothing."""
    from flask_login import current_user
    import os
    
    debug_info = {
        "is_authenticated": current_user.is_authenticated,
        "db_url_masked": str(db.engine.url).replace(str(db.engine.url).split('@')[0], '***') if '@' in str(db.engine.url) else str(db.engine.url),
    }
    
    if current_user.is_authenticated:
        debug_info.update({
            "user_id": current_user.id,
            "user_email": current_user.email,
            "company_id": current_user.company_id,
            # Count data SPECIFICALLY for this user's company
            "my_clients": Client.query.filter_by(company_id=current_user.company_id).count(),
            "my_leads": Lead.query.filter_by(company_id=current_user.company_id).count(),
            "my_contracts": Contract.query.filter_by(company_id=current_user.company_id).count(),
            "my_tasks": Task.query.filter_by(company_id=current_user.company_id).count(),
        })
        
        # Check if Admin EXISTS in DB (Collision Check)
        admin_user = User.query.filter_by(email="admin@northway.com").first()
        if admin_user:
             debug_info["admin_check"] = {
                 "id": admin_user.id,
                 "company_id": admin_user.company_id,
                 "matches_current": (admin_user.id == current_user.id)
             }
    else:
        debug_info["message"] = "Not logged in. Please log in and revisit this page."
        
    return jsonify(debug_info)
