from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template, current_app, Response
from flask_login import login_required, current_user
from models import db, Integration, WhatsAppMessage, Lead, Client, QuickMessage
from services.whatsapp_service import WhatsAppService
import json

whatsapp_bp = Blueprint('whatsapp', __name__)

# --- TEMPLATE FILTERS ---
@whatsapp_bp.app_template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value)
    except:
        return {}

# --- CONFIG ---
@whatsapp_bp.route('/api/whatsapp/config', methods=['POST'])
@login_required
def configure():
    instance_id = request.form.get('instance_id')
    token = request.form.get('token')
    api_url = request.form.get('api_url') or 'https://api.z-api.io'
    client_token = request.form.get('client_token')
    
    if not instance_id or not token:
        flash('Instance ID e Token são obrigatórios.', 'error')
        return redirect(url_for('admin.settings_integrations'))
        
    # Logic kept here as it's Admin/CRUD specific, or could move to Service setup
    integration = Integration.query.filter_by(company_id=current_user.company_id, service='z_api').first()
    if not integration:
        integration = Integration(company_id=current_user.company_id, service='z_api')
        db.session.add(integration)
    
    integration.api_key = token
    integration.config_json = json.dumps({
        'instance_id': instance_id,
        'api_url': api_url.rstrip('/'),
        'client_token': client_token
    })
    integration.is_active = True
    
    try:
        db.session.commit()
        flash('Configuração salva.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {e}', 'error')
        
    return redirect(url_for('admin.settings_integrations'))

@whatsapp_bp.route('/api/whatsapp/test', methods=['POST'])
@login_required
def test_connection():
    config = WhatsAppService.get_config(current_user.company_id)
    if not config: return "Não configurado", 400
    
    import requests
    headers = {}
    if config.get('client_token'): headers['Client-Token'] = config['client_token']
    url = f"{config['api_url']}/instances/{config['instance_id']}/token/{config['token']}/status"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        if 'error' in data: 
            return f"Erro Z-API: {data['error']} (URL: {url.replace(config['token'], '***')})"
        if data.get('connected'): return "Conectado! ✅"
        return "Desconectado (ou QR Code necessário)."
    except Exception as e:
        return f"Erro de conexão: {e} (URL: {url.replace(config['token'], '***')})"

@whatsapp_bp.route('/api/whatsapp/setup-webhook', methods=['POST'])
@login_required
def setup_webhook():
    root = request.url_root.rstrip('/')
    # Force HTTPS if not localhost (Vercel/Production)
    if 'localhost' not in root and '127.0.0.1' not in root:
        root = root.replace('http://', 'https://')
        
    webhook_url = f"{root}/api/webhooks/zapi/{current_user.company_id}"
    try:
        WhatsAppService.configure_webhook(current_user.company_id, webhook_url)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- VIEWS ---
@whatsapp_bp.route('/whatsapp')
@login_required
def inbox():
    return render_template('whatsapp_inbox.html')

# --- API ---

@whatsapp_bp.route('/api/whatsapp/conversations')
@login_required
def get_conversations():
    try:
        data = WhatsAppService.get_inbox_conversations(current_user.company_id)
        return jsonify({'conversations': data})
    except Exception as e:
        current_app.logger.error(f"Inbox Error: {e}")
        return jsonify({'error': str(e)}), 500

@whatsapp_bp.route('/api/whatsapp/<string:type>/<string:contact_id>/messages', methods=['GET'])
@whatsapp_bp.route('/api/whatsapp/lead/<int:id>/messages', methods=['GET'], endpoint='get_lead_messages_legacy')
@whatsapp_bp.route('/api/whatsapp/client/<int:id>/messages', methods=['GET'], endpoint='get_client_messages_legacy')
@login_required
def get_history(type='lead', contact_id=None, id=None):
    # Use contact_id from path, or id from legacy routes
    contact_id = contact_id or id
    
    if not contact_id:
        return jsonify({'error': 'Missing contact ID'}), 400
    if 'lead' in request.endpoint: 
        type = 'lead'
    if 'client' in request.endpoint: 
        type = 'client'
    
    # Check Auth & Get Messages
    filters = {'company_id': current_user.company_id}
    
    if type == 'lead':
        obj = Lead.query.get_or_404(contact_id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        filters['lead_id'] = obj.id
    elif type == 'client':
        obj = Client.query.get_or_404(contact_id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        filters['client_id'] = obj.id
    elif type == 'atendimento':
        # Unknown contact, lookup by phone
        filters['phone'] = contact_id
        filters['lead_id'] = None
        filters['client_id'] = None
    else:
        return jsonify({'error': 'Invalid type'}), 400
        
    msgs = WhatsAppMessage.query.filter_by(**filters).order_by(WhatsAppMessage.created_at.asc()).all()
    
    return jsonify({
        'messages': [{
            'id': m.id,
            'content': m.content,
            'direction': m.direction,
            'status': m.status,
            'type': m.type or 'text',
            'attachment_url': m.attachment_url,
            'timestamp': m.created_at.isoformat()
        } for m in msgs]
    })

@whatsapp_bp.route('/api/whatsapp/send', methods=['POST'])
@login_required
def send_msg():
    data = request.json
    content = data.get('content')
    if not content: return jsonify({'error': 'No content'}), 400
    
    try:
        if data.get('lead_id'):
            msg = WhatsAppService.send_message(current_user.company_id, 'lead', data['lead_id'], content)
        elif data.get('client_id'):
            msg = WhatsAppService.send_message(current_user.company_id, 'client', data['client_id'], content)
        else:
            return jsonify({'error': 'Target missing'}), 400
            
        return jsonify({'success': True, 'message': {'id': msg.id, 'content': msg.content, 'timestamp': msg.created_at.isoformat()}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@whatsapp_bp.route('/api/whatsapp/send-media', methods=['POST'])
@login_required
def send_media():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    
    try:
        if request.form.get('lead_id'):
            WhatsAppService.send_message(current_user.company_id, 'lead', request.form['lead_id'], None, media_file=file)
        elif request.form.get('client_id'):
            WhatsAppService.send_message(current_user.company_id, 'client', request.form['client_id'], None, media_file=file)
        else:
            return jsonify({'error': 'Target missing'}), 400
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- WEBHOOK ---(Public)
@whatsapp_bp.route('/api/webhooks/zapi/<int:company_id>', methods=['POST'])
def webhook(company_id):
    try:
        res = WhatsAppService.process_webhook(company_id, request.json)
        return jsonify(res)
    except Exception as e:
        current_app.logger.error(f"Webhook Fatal: {e}")
        return jsonify({'error': str(e)}), 500

# --- QUICK MESSAGES (CRUD) ---
@whatsapp_bp.route('/api/whatsapp/quick-messages', methods=['GET'])
@login_required
def list_quick_messages():
    qms = QuickMessage.query.filter_by(company_id=current_user.company_id).order_by(QuickMessage.title).all()
    return jsonify({'quick_messages': [{
        'id': q.id, 'title': q.title, 'content': q.content, 'shortcut': q.shortcut
    } for q in qms]})

@whatsapp_bp.route('/api/whatsapp/quick-messages', methods=['POST'])
@login_required
def create_quick_message():
    data = request.json
    qm = QuickMessage(
        company_id=current_user.company_id,
        title=data['title'],
        content=data['content'],
        shortcut=data.get('shortcut')
    )
    db.session.add(qm)
    db.session.commit()
    return jsonify({'success': True})

@whatsapp_bp.route('/api/whatsapp/quick-messages/<int:id>', methods=['DELETE'])
@login_required
def delete_quick_message(id):
    qm = QuickMessage.query.get_or_404(id)
    if qm.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(qm)
    db.session.commit()
    return jsonify({'success': True})

@whatsapp_bp.route('/api/whatsapp/sync-profile', methods=['POST'])
@login_required
def sync_profile():
    data = request.json
    c_type = data.get('type')
    c_id = data.get('id')
    
    if not c_type or not c_id:
        return jsonify({'error': 'Missing parameters'}), 400
        
    try:
        contact = None
        if c_type == 'lead':
            contact = Lead.query.get(c_id)
        elif c_type == 'client':
            contact = Client.query.get(c_id)
            
        if not contact or contact.company_id != current_user.company_id:
            return jsonify({'error': 'Contact not found'}), 404
            
        # Fetch Logic
        # We need the phone to fetch
        pic_url = WhatsAppService.fetch_profile_picture(current_user.company_id, contact.phone)
        
        if pic_url:
            contact.profile_pic_url = pic_url
            db.session.commit()
            return jsonify({'success': True, 'url': pic_url})
        else:
            return jsonify({'success': False, 'message': 'Foto não encontrada ou erro na busca.'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@whatsapp_bp.route('/api/whatsapp/<string:type>/<string:id>/details', methods=['GET'])
@login_required
def get_details(type, id):
    obj = None
    if type == 'lead':
        obj = Lead.query.get_or_404(id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        
        # Tags Logic
        tags = []
        if obj.status: tags.append({'text': obj.status, 'color': 'red' if obj.status == 'new' else 'gray'})
        if obj.source: tags.append({'text': obj.source, 'color': 'blue'})
        
        deal_value = obj.bant_budget or 'R$ 0,00'
        notes = obj.notes or ''
        name = obj.name
        
    elif type == 'client':
        obj = Client.query.get_or_404(id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        
        tags = []
        if obj.status: tags.append({'text': obj.status, 'color': 'green' if obj.status == 'ativo' else 'red'})
        if obj.service: tags.append({'text': obj.service, 'color': 'purple'})
        
        deal_value = f"R$ {obj.monthly_value:,.2f}" if obj.monthly_value else 'R$ 0,00'
        notes = obj.notes or ''
        name = obj.name
    elif type == 'atendimento':
        # Unknown contact
        tags = [{'text': 'Desconhecido', 'color': 'gray'}]
        deal_value = 'R$ 0,00'
        notes = 'Este contato ainda não foi adicionado ao CRM.'
        name = id # Phone
    else:
        return jsonify({'error': 'Invalid type'}), 400
        
    return jsonify({
        'name': name,
        'tags': tags,
        'deal_value': deal_value,
        'notes': notes,
        'is_unknown': type == 'atendimento'
    })

@whatsapp_bp.route('/api/whatsapp/atendimento/convert', methods=['POST'])
@login_required
def convert_unknown_to_lead():
    data = request.json
    phone = data.get('phone')
    name = data.get('name')
    if not phone or not name: return jsonify({'error': 'Missing phone or name'}), 400
    
    # Create Lead
    lead = Lead(
        company_id=current_user.company_id,
        name=name,
        phone=phone,
        status='new',
        source='whatsapp'
    )
    db.session.add(lead)
    db.session.flush() # Get ID
    
    # Associate orphan messages
    WhatsAppMessage.query.filter_by(company_id=current_user.company_id, phone=phone, lead_id=None, client_id=None)\
        .update({WhatsAppMessage.lead_id: lead.id})
    
    db.session.commit()
    return jsonify({'success': True, 'lead_id': lead.id})

@whatsapp_bp.route('/api/whatsapp/<string:type>/<int:id>/notes', methods=['POST'])
@login_required
def update_notes(type, id):
    content = request.json.get('notes')
    if content is None: return jsonify({'error': 'Missing content'}), 400
    
    if type == 'lead':
        obj = Lead.query.get_or_404(id)
    elif type == 'client':
        obj = Client.query.get_or_404(id)
    else:
        return jsonify({'error': 'Invalid type'}), 400
        
    if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
    
    obj.notes = content
    db.session.commit()
    return jsonify({'success': True})
