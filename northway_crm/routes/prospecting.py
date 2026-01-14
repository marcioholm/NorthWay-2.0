from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
import requests
import os
import json
from models import db, Lead, Interaction

prospecting_bp = Blueprint('prospecting', __name__)

@prospecting_bp.route('/prospecting')
@login_required
def index():
    return render_template('prospecting.html')

@prospecting_bp.route('/api/prospecting/search')
@login_required
def search_places():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
        
    # Get API Key: Priority DB -> Env -> Config
    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    
    api_key = None
    if integration and integration.is_active:
        api_key = integration.api_key
        
    if not api_key:
        return jsonify({'error': 'API Key not configured for this company'}), 500

    # Google Places Text Search
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        'query': query,
        'key': api_key,
        'language': 'pt-BR'
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        print(f"DEBUG GOOGLE MAPS: {json.dumps(data, indent=2)}") # Debugging
        
        if data.get('status') not in ['OK', 'ZERO_RESULTS']:
            return jsonify({'error': f"Google API Error: {data.get('status')}", 'details': data.get('error_message')}), 400
            
        # Clean data for frontend (minimize data transfer)
        results = []
        for place in data.get('results', []):
            results.append({
                'place_id': place.get('place_id'),
                'name': place.get('name'),
                'formatted_address': place.get('formatted_address'),
                'business_status': place.get('business_status'),
                'rating': place.get('rating'),
                'user_ratings_total': place.get('user_ratings_total'),
                'types': place.get('types', [])
            })
            
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@prospecting_bp.route('/api/prospecting/import', methods=['POST'])
@login_required
def import_lead():
    data = request.json
    place_id = data.get('place_id')
    
    if not place_id:
        return jsonify({'error': 'place_id is required'}), 400

    # Get API Key: Priority DB -> Env -> Config
    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    
    api_key = None
    if integration and integration.is_active:
        api_key = integration.api_key
        
    if not api_key:
        return jsonify({'error': 'API Key not configured for this company'}), 500

    # Google Place Details API
    # We fetch specific fields to save costs and get contact info
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    fields = "name,formatted_address,formatted_phone_number,website,url"
    params = {
        'place_id': place_id,
        'fields': fields,
        'key': api_key,
        'language': 'pt-BR'
    }
    
    try:
        response = requests.get(url, params=params)
        details_data = response.json()
        
        if details_data.get('status') != 'OK':
             return jsonify({'error': f"Google API Error: {details_data.get('status')}"}), 400
             
        result = details_data.get('result', {})
        
        # Check if already exists (Simple duplicity check by name or address could be better, 
        # but for now we trust the user clicking import)
        
        # Find Default Pipeline (First one for company)
        from models import Pipeline, PipelineStage 
        
        default_pipeline = Pipeline.query.filter_by(company_id=current_user.company_id).first()
        first_stage = None
        if default_pipeline:
             first_stage = PipelineStage.query.filter_by(pipeline_id=default_pipeline.id).order_by(PipelineStage.order).first()
        
        # Create Lead
        new_lead = Lead(
            name=result.get('name'),
            company_id=current_user.company_id,
            assigned_to_id=current_user.id,
            status='new', # Standard status
            pipeline_id=default_pipeline.id if default_pipeline else None,
            pipeline_stage_id=first_stage.id if first_stage else None,
            source='google_maps',
            phone=result.get('formatted_phone_number'),
            website=result.get('website'),
            address=result.get('formatted_address'),
            email=None, 
            notes=f"Link do Google Maps: {result.get('url')}" 
        )
        
        db.session.add(new_lead)
        db.session.commit()
        
        return jsonify({'success': True, 'lead_id': new_lead.id, 'lead_name': new_lead.name})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
