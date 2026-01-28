from flask import Blueprint, request, jsonify, current_app
from models import db, User, Lead, Client, Pipeline, PipelineStage, Task, Interaction
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
                'company_id': user.company_id
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
            'company_id': current_user.company_id
        }
    })

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
        bant_need=data.get('bant_need')
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
             created_at=datetime.utcnow()
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
        lead.notes = data['notes']
        
    if 'pipeline_stage_id' in data:
        lead.pipeline_stage_id = data['pipeline_stage_id']
        lead.status = 'in_progress' # Auto update status if stage moves
        
    if 'bant_need' in data: # Using this for tags roughly
        lead.bant_need = data['bant_need']
        
    db.session.commit()
    
    return jsonify({'success': True})
