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
        # CNPJA Commercial API uses 'taxId' and 'company' object
        
        lead.legal_name = details.get('company', {}).get('name') or details.get('alias')
        lead.cnpj = details.get('taxId')
        
        status_info = details.get('status', {})
        lead.registration_status = status_info.get('text') if isinstance(status_info, dict) else status_info
        
        # Company Size
        size_info = details.get('company', {}).get('size', {})
        lead.company_size = size_info.get('text') if isinstance(size_info, dict) else str(size_info)
        
        # Capital Social
        lead.equity = details.get('company', {}).get('equity')
        
        # Data de Abertura
        lead.foundation_date = details.get('founded')
        
        # Email & Telefone (Receita)
        emails = details.get('emails', [])
        if emails and isinstance(emails, list):
            lead.legal_email = emails[0].get('address')
            
        phones = details.get('phones', [])
        if phones and isinstance(phones, list):
            area = phones[0].get('area')
            number = phones[0].get('number')
            lead.legal_phone = f"({area}) {number}" if area and number else number
        
        # CNAE (mainActivity)
        main_activity = details.get('mainActivity', {})
        if isinstance(main_activity, dict):
            code = main_activity.get('id') or main_activity.get('code')
            text = main_activity.get('text')
            lead.cnae = f"{code} - {text}" if code else text
        else:
            lead.cnae = str(main_activity)
        
        # Partners (members inside company)
        partners = details.get('company', {}).get('members', [])
        lead.partners_json = json.dumps(partners)
        
        # Address
        address_info = details.get('address', {})
        if address_info:
            street = address_info.get('street') or ''
            number = address_info.get('number') or 'S/N'
            district = address_info.get('district') or ''
            city = address_info.get('city') or ''
            state = address_info.get('state') or ''
            zip_code = address_info.get('zip') or ''
            
            full_addr = f"{street}, {number} - {district}, {city}/{state} CEP: {zip_code}"
            # Always update or set if empty
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
