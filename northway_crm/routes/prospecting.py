from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import requests
from models import db, Lead, Interaction, ProspectingSearch, Company
from datetime import datetime

prospecting_bp = Blueprint('prospecting', __name__)

@prospecting_bp.route('/prospecting')
@login_required
def index():
    if not current_user.company.has_feature('prospecting'):
        flash('Sua empresa não possui acesso a este módulo.', 'error')
        return redirect(url_for('dashboard.home'))
    return render_template('prospecting.html')

@prospecting_bp.route('/api/prospecting/search')
@login_required
def search_places():
    query = request.args.get('query')
    city = request.args.get('city')
    state = request.args.get('state')
    radius = request.args.get('radius', type=int) # in km
    min_rating = request.args.get('min_rating', type=float)
    min_reviews = request.args.get('min_reviews', type=int)
    pagetoken = request.args.get('pagetoken')
    
    if not query and not pagetoken:
        return api_response(success=False, error='Query or pagetoken is required', status=400)
        
    # Get API Key
    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    api_key = integration.api_key if integration and integration.is_active else None
    
    if not api_key:
        return api_response(success=False, error='API Key not configured', status=500)

    all_results = []
    next_page_token = None
    
    try:
        # If we have a pagetoken, we just fetch the next page directly
        if pagetoken:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                'pagetoken': pagetoken,
                'key': api_key
            }
            # Google needs a small delay before the token becomes valid
            import time
            time.sleep(1.5)
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            all_results = data.get('results', [])
            next_page_token = data.get('next_page_token')
        else:
            # New search
            cities = [c.strip() for c in city.split(',')] if city else [None]
            for current_city in cities:
                search_query = query
                if current_city: search_query += f", {current_city}"
                if state: search_query += f", {state}"
                search_query += ", Brasil"

                url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                params = {
                    'query': search_query,
                    'key': api_key,
                    'language': 'pt-BR'
                }
                
                # Radius logic: needs location (lat,lng)
                if radius and current_city:
                    # Geocode city to get coordinates
                    geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
                    geo_params = {'address': f"{current_city}, {state or ''}, Brasil", 'key': api_key}
                    geo_resp = requests.get(geo_url, params=geo_params).json()
                    if geo_resp.get('status') == 'OK':
                        loc = geo_resp['results'][0]['geometry']['location']
                        params['location'] = f"{loc['lat']},{loc['lng']}"
                        params['radius'] = radius * 1000 # maps api uses meters
                
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                if data.get('status') == 'OK':
                    all_results.extend(data.get('results', []))
                    if not next_page_token:
                        next_page_token = data.get('next_page_token')

        # Deduplicate and Filter
        unique_results = {p['place_id']: p for p in all_results}.values()
        existing_place_ids = {l.google_place_id for l in Lead.query.filter_by(company_id=current_user.company_id).filter(Lead.google_place_id != None).all()}
        
        final_results = []
        for place in unique_results:
            rating = place.get('rating', 0)
            reviews = place.get('user_ratings_total', 0)
            
            if min_rating and rating < min_rating: continue
            if min_reviews and reviews < min_reviews: continue
            
            place_id = place.get('place_id')
            is_duplicate = place_id in existing_place_ids
            
            final_results.append({
                'place_id': place_id,
                'name': place.get('name'),
                'formatted_address': place.get('formatted_address'),
                'rating': rating,
                'user_ratings_total': reviews,
                'types': place.get('types', []),
                'is_duplicate': is_duplicate,
                'phone': place.get('formatted_phone_number'), 
                'website': place.get('website')
            })

        return api_response(data={
            'results': final_results,
            'count': len(final_results),
            'next_page_token': next_page_token
        })
        
    except Exception as e:
        return api_response(success=False, error=str(e), status=500)

@prospecting_bp.route('/api/prospecting/favorites', methods=['GET', 'POST'])
@login_required
def handle_favorites():
    if request.method == 'POST':
        data = request.json
        new_fav = ProspectingSearch(
            name=data.get('name'),
            query=data.get('query'),
            city=data.get('city'),
            state=data.get('state'),
            radius=data.get('radius'),
            min_rating=data.get('min_rating'),
            min_reviews=data.get('min_reviews'),
            company_id=current_user.company_id
        )
        db.session.add(new_fav)
        db.session.commit()
        return api_response(data={'id': new_fav.id})
    else:
        favs = ProspectingSearch.query.filter_by(company_id=current_user.company_id).order_by(ProspectingSearch.created_at.desc()).all()
        return api_response(data=[{
            'id': f.id, 'name': f.name, 'query': f.query, 'city': f.city, 
            'state': f.state, 'radius': f.radius, 'min_rating': f.min_rating, 'min_reviews': f.min_reviews
        } for f in favs])

@prospecting_bp.route('/api/prospecting/favorites/<int:fav_id>', methods=['DELETE'])
@login_required
def delete_favorite(fav_id):
    fav = ProspectingSearch.query.filter_by(id=fav_id, company_id=current_user.company_id).first_or_404()
    db.session.delete(fav)
    db.session.commit()
    return api_response(success=True)

@prospecting_bp.route('/api/prospecting/history')
@login_required
def get_import_history():
    """Returns recent imports for the current company."""
    # Simplified: Get last 50 leads with google_place_id
    history = Lead.query.filter(
        Lead.company_id == current_user.company_id,
        Lead.google_place_id != None
    ).order_by(Lead.created_at.desc()).limit(50).all()
    
    return jsonify({
        'success': True,
        'data': [{
            'id': l.id,
            'name': l.name,
            'imported_at': l.created_at.isoformat() if l.created_at else None
        } for l in history]
    })

@prospecting_bp.route('/api/prospecting/pipelines')
@login_required
def get_prospecting_pipelines():
    """Helper for the web UI to get stages for import selection."""
    from models import Pipeline, PipelineStage
    pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
    result = []
    for p in pipelines:
        stages = PipelineStage.query.filter_by(pipeline_id=p.id).order_by(PipelineStage.order).all()
        result.append({
            'id': p.id,
            'name': p.name,
            'stages': [{'id': s.id, 'name': s.name} for s in stages]
        })
    return jsonify({'success': True, 'data': result})

@prospecting_bp.route('/api/prospecting/import', methods=['POST'])
@login_required
def import_lead():
    data = request.json
    places = data.get('places', [])
    stage_id = data.get('stage_id')
    
    if not places and data.get('place_id'):
        places = [data]

    if not places:
        return api_response(success=False, error='places is required', status=400)

    from models import Pipeline, PipelineStage
    target_stage_id = stage_id
    target_pipeline_id = None
    
    if target_stage_id:
        s = PipelineStage.query.get(target_stage_id)
        if s: target_pipeline_id = s.pipeline_id

    if not target_stage_id or not target_pipeline_id:
        default_p = Pipeline.query.filter_by(company_id=current_user.company_id).first()
        if default_p:
            target_pipeline_id = default_p.id
            first_s = PipelineStage.query.filter_by(pipeline_id=default_p.id).order_by(PipelineStage.order).first()
            if first_s: target_stage_id = first_s.id

    from models import Integration
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    api_key = integration.api_key if integration and integration.is_active else None

    imported_count = 0
    errors = []
    
    for p in places:
        place_id = p.get('place_id')
        if not place_id: continue
        
        phone = p.get('phone')
        website = p.get('website')
        
        # Hydrate missing phone data via Place Details API if possible
        if api_key and not phone:
            try:
                import requests
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_params = {
                    'place_id': place_id,
                    'fields': 'formatted_phone_number,international_phone_number,website',
                    'key': api_key
                }
                res = requests.get(details_url, params=details_params, timeout=5).json()
                if res.get('status') == 'OK':
                    result_data = res.get('result', {})
                    phone = result_data.get('international_phone_number') or result_data.get('formatted_phone_number') or phone
                    website = result_data.get('website') or website
            except:
                pass
        
        try:
            if Lead.query.filter_by(company_id=current_user.company_id, google_place_id=place_id).first():
                continue
            
            new_lead = Lead(
                name=p.get('name'),
                company_id=current_user.company_id,
                assigned_to_id=current_user.id,
                status='new',
                pipeline_id=target_pipeline_id,
                pipeline_stage_id=target_stage_id,
                source='google_maps',
                phone=phone,
                website=website,
                address=p.get('formatted_address'),
                google_place_id=place_id,
                gmb_rating=p.get('rating', 0),
                gmb_reviews=p.get('user_ratings_total', 0),
                notes=f"Importado via Google Maps em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
            db.session.add(new_lead)
            imported_count += 1
        except Exception as e:
            errors.append(f"Error {p.get('name')}: {str(e)}")

    db.session.commit()
    return api_response(data={'imported_count': imported_count, 'errors': errors})

@prospecting_bp.route('/api/prospecting/backfill-phones', methods=['POST'])
@login_required
def backfill_phones():
    from models import Integration, Lead
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='google_maps').first()
    api_key = integration.api_key if integration and integration.is_active else None

    if not api_key:
        return api_response(success=False, error='API Key not configured', status=500)
        
    data = request.json or {}
    lead_ids = data.get('lead_ids', [])

    # Find leads that have a google place id but NO phone
    query = Lead.query.filter(
        Lead.company_id == current_user.company_id,
        Lead.google_place_id != None,
        (Lead.phone == None) | (Lead.phone == '')
    )
    
    if lead_ids:
        query = query.filter(Lead.id.in_(lead_ids))
        
    leads = query.all()

    import requests
    import time
    
    updated_count = 0
    errors = []

    for lead in leads:
        try:
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                'place_id': lead.google_place_id,
                'fields': 'formatted_phone_number,international_phone_number,website',
                'key': api_key
            }
            res = requests.get(details_url, params=details_params, timeout=10).json()
            if res.get('status') == 'OK':
                result_data = res.get('result', {})
                phone = result_data.get('international_phone_number') or result_data.get('formatted_phone_number')
                website = result_data.get('website')
                
                if phone:
                    lead.phone = phone
                    updated_count += 1
                if website and not lead.website:
                    lead.website = website
            
            # Sleep slightly to avoid rate limit spikes
            time.sleep(0.3)
        except Exception as e:
            errors.append(f"Error {lead.id}: {str(e)}")

    db.session.commit()
    return api_response(data={'updated_count': updated_count, 'errors': errors, 'total_scanned': len(leads)})

def api_response(success=True, data=None, error=None, status=200):
    return jsonify({
        'success': success,
        'data': data,
        'error': error
    }), status
