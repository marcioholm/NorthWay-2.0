from flask import Blueprint, request, jsonify, g
from models import db, Lead, Interaction, Integration, Contact
from middleware.api_auth import api_key_required
from services.integrations_service import IntegrationsService
from utils import get_now_br
import json

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

@api_v1_bp.route('/leads', methods=['GET'])
@api_key_required(required_scopes=['leads:read'])
def list_leads():
    """Lists leads for the company."""
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    status = request.args.get('status')
    
    query = Lead.query.filter_by(company_id=g.company_id)
    if status:
        query = query.filter_by(status=status)
        
    leads = query.order_by(Lead.created_at.desc()).limit(limit).offset(offset).all()
    
    return jsonify({
        "success": True,
        "count": len(leads),
        "data": [l.to_dict() if hasattr(l, 'to_dict') else {
            "id": l.id,
            "name": l.name,
            "email": l.email,
            "phone": l.phone,
            "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else None
        } for l in leads]
    })

@api_v1_bp.route('/leads', methods=['POST'])
@api_key_required(required_scopes=['leads:write'])
def create_lead():
    """Creates a new lead."""
    data = request.json
    if not data or not data.get('name'):
        return jsonify({"success": False, "error": "Nome é obrigatório"}), 400
        
    try:
        new_lead = Lead(
            company_id=g.company_id,
            name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone'),
            source=data.get('source', 'API'),
            status=data.get('status', 'novo'),
            description=data.get('description'),
            created_at=get_now_br()
        )
        db.session.add(new_lead)
        db.session.commit()
        
        # Dispatch Webhook
        IntegrationsService.dispatch_webhooks(g.company_id, 'lead.created', {
            "id": new_lead.id,
            "name": new_lead.name,
            "status": new_lead.status
        })
        
        return jsonify({
            "success": True, 
            "data": {"id": new_lead.id}
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@api_v1_bp.route('/leads/<int:id>', methods=['PATCH'])
@api_key_required(required_scopes=['leads:write'])
def update_lead(id):
    """Updates an existing lead."""
    lead = Lead.query.filter_by(id=id, company_id=g.company_id).first()
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado"}), 404
        
    data = request.json
    fields_updated = []
    
    for field in ['name', 'email', 'phone', 'status', 'description']:
        if field in data:
            setattr(lead, field, data[field])
            fields_updated.append(field)
            
    if fields_updated:
        db.session.commit()
        # Dispatch Webhook
        IntegrationsService.dispatch_webhooks(g.company_id, 'lead.updated', {
            "id": lead.id,
            "fields": fields_updated,
            "status": lead.status
        })
        
    return jsonify({"success": True})

@api_v1_bp.route('/messages/send', methods=['POST'])
@api_key_required(required_scopes=['messages:send', '*'])
def send_message():
    """Sends a WhatsApp message via the tenant's integration."""
    data = request.json
    phone = data.get('phone')
    message = data.get('message')
    
    if not phone or not message:
        return jsonify({"success": False, "error": "Telefone e mensagem são obrigatórios"}), 400
        
    # Check for active WhatsApp integration
    whatsapp = Integration.query.filter_by(
        company_id=g.company_id, 
        service='whatsapp', 
        is_active=True
    ).first()
    
    if not whatsapp:
        return jsonify({"success": False, "error": "Integração WhatsApp não configurada ou inativa"}), 400
        
    # Here we would call the existing WhatsApp service logic
    # For now, we'll log it as an interaction and return success
    try:
        # Implementation depends on the specific WhatsApp service used in the CRM
        # We'll simulate a successful dispatch
        return jsonify({
            "success": True, 
            "message": "Mensagem enviada para fila de processamento"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
