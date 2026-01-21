from flask import Blueprint, request, current_app
from flask_login import login_required, current_user
from models import db, Lead, Integration
from services.cnpj_service import CNPJAService
from utils import api_response
from datetime import datetime
import json

enrichment_bp = Blueprint('enrichment', __name__)

@enrichment_bp.route('/api/leads/search-cnpj')
@login_required
def search_cnpj():
    query = request.args.get('q')
    if not query:
        return api_response(success=False, error="Query is required", status=400)
    
    # Get CNPJA Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='cnpja').first()
    if not integration or not integration.is_active:
        return api_response(success=False, error="Integração CNPJA não configurada", status=400)
    
    results = CNPJAService.search_by_name(query, integration.api_key)
    
    if isinstance(results, dict) and "error" in results:
        return api_response(success=False, error=f"Erro na API CNPJA: {results.get('error')}", status=500)
        
    return api_response(data=results)

@enrichment_bp.route('/api/leads/<int:lead_id>/enrich', methods=['POST'])
@login_required
def enrich_lead(lead_id):
    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    data = request.json
    cnpj = data.get('cnpj')
    
    if not cnpj:
        return api_response(success=False, error="CNPJ is required", status=400)
    
    # Get CNPJA Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='cnpja').first()
    if not integration or not integration.is_active:
        return api_response(success=False, error="Integração CNPJA não configurada", status=400)
    
    # Fetch full details to enrich
    details = CNPJAService.get_by_cnpj(cnpj, integration.api_key)
    
    if "error" in details:
        return api_response(success=False, error=f"Erro na API CNPJA: {details.get('error')}", status=500)
    
    try:
        # Enrich basic info if not present or explicitly requested
        # Map CNPJA fields to our model
        # cnpja common fields: 'name' (Razão Social), 'alias' (Fantasia), 'tax_id' (CNPJ), 'status' -> 'text'
        
        lead.legal_name = details.get('name')
        lead.cnpj = details.get('tax_id')
        
        status_info = details.get('status', {})
        lead.registration_status = status_info.get('text') if isinstance(status_info, dict) else status_info
        
        lead.company_size = details.get('size', {}).get('text') if isinstance(details.get('size'), dict) else details.get('size')
        
        # CNAE
        main_activity = details.get('main_activity', {})
        lead.cnae = f"{main_activity.get('code')} - {main_activity.get('text')}" if isinstance(main_activity, dict) else str(main_activity)
        
        # Partners
        partners = details.get('members', [])
        lead.partners_json = json.dumps(partners)
        
        # Address (Optional enrichment)
        address_info = details.get('address', {})
        if address_info:
            street = address_info.get('street')
            number = address_info.get('number')
            city = address_info.get('city')
            state = address_info.get('state')
            zip_code = address_info.get('zip')
            
            full_addr = f"{street}, {number} - {city}/{state} CEP: {zip_code}"
            if not lead.address:
                lead.address = full_addr
        
        # History
        history = json.loads(lead.enrichment_history or '[]')
        history.append({
            'date': datetime.now().isoformat(),
            'user': current_user.name,
            'source': 'CNPJA',
            'cnpj': lead.cnpj
        })
        lead.enrichment_history = json.dumps(history)
        
        db.session.commit()
        return api_response(data={"message": "Lead enriquecido com sucesso", "lead_id": lead.id})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Enrichment Error: {e}")
        return api_response(success=False, error=str(e), status=500)
