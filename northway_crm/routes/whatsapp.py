from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template, current_app, Response
from flask_login import login_required, current_user
from models import db, Integration, Lead, Client, QuickMessage, WhatsappInstance, WhatsappConversation, WhatsappMessage, WhatsappGroupMember
from services.evolution_service import EvolutionService
import json
import uuid
import base64
from extensions import limiter
from datetime import datetime

whatsapp_bp = Blueprint('whatsapp', __name__)

@whatsapp_bp.before_request
def check_feature_access():
    if request.method == 'OPTIONS': return
    
    # Allow Webhook (Public)
    if 'webhooks' in request.path:
        return
        
    # Check Feature Flag
    if current_user.is_authenticated:
        if not current_user.company.has_feature('whatsapp'):
            if request.is_json: # API
                return jsonify({'error': 'Feature Disabled for this Company'}), 403
            else: # UI
                flash('Módulo WhatsApp desativado pela administração.', 'error')
                return redirect(url_for('dashboard.home'))

# --- TEMPLATE FILTERS ---
@whatsapp_bp.app_template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value)
    except:
        return {}

@whatsapp_bp.route('/api/whatsapp/config', methods=['POST'])
@login_required
def configure_instance():
    instance_name = request.form.get('instance_name', '').strip()
    
    if not instance_name:
        company_slug = current_user.company.name.lower().replace(' ', '_').replace('-', '_')
        instance_name = f"northway_{company_slug}_{current_user.company_id}"
        
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        instance = WhatsappInstance(company_id=current_user.company_id, instance_name=instance_name)
        db.session.add(instance)
    else:
        instance.instance_name = instance_name
        
    try:
        # Create instance in Evolution
        res = EvolutionService.create_instance(instance_name)
        instance.status = 'connecting'
        db.session.commit()
        
        flash('Instância Evolution criada com sucesso. Webhooks requerem configuração via n8n/Nora.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro na Evolution API: {e}', 'error')
        
    return redirect(url_for('admin.settings_integrations'))

@whatsapp_bp.route('/api/whatsapp/test', methods=['POST'])
@login_required
def test_connection():
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({'connected': False, 'message': "Instância não configurada."})
    
    try:
        res = EvolutionService.get_connection_status(instance.instance_name)
        state = res.get('instance', {}).get('state', 'disconnected')
        
        instance.status = state
        db.session.commit()
        
        if state == 'open':
            return jsonify({'connected': True, 'message': "Conectado! ✅"})
        elif state == 'connecting':
            return jsonify({'connected': False, 'message': "Conectando / Aguardando QR Code."})
        else:
            return jsonify({'connected': False, 'message': f"Status: {state}"})
            
    except Exception as e:
        return jsonify({'connected': False, 'message': f"Erro: {str(e)}"})

@whatsapp_bp.route('/api/whatsapp/remove', methods=['POST'])
@login_required
def remove_instance():
    instance_name = request.args.get('instance_name') or request.form.get('instance_name')
    if not instance_name:
        return jsonify({'error': 'Instance name required'}), 400
        
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id, instance_name=instance_name).first()
    if not instance:
        return jsonify({'error': 'Instance not found'}), 404
        
    try:
        # Delete from Evolution
        EvolutionService.delete_instance(instance_name)
        
        # Delete from DB
        db.session.delete(instance)
        db.session.commit()
        
        flash(f'Instância {instance_name} removida.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover: {e}', 'error')
        
    return redirect(url_for('admin.settings_integrations'))

@whatsapp_bp.route('/api/whatsapp/instances/<string:instance_name>/status')
@login_required
def get_instance_status(instance_name):
    # Security check: User must belong to the same company
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id, instance_name=instance_name).first()
    if not instance:
        return jsonify({'error': 'Unauthorized or Not Found'}), 403
        
    try:
        res = EvolutionService.get_connection_status(instance_name)
        # Evolution status check
        # Response might contain "base64" for QR if state is "connecting"
        state = res.get('instance', {}).get('state', 'disconnected')
        
        qr_code_base64 = None
        if state == 'connecting' or state == 'close':
            # Try to get QR Code if not provided in the first response
            qr_res = EvolutionService.create_instance(instance_name) # RE-create instance might provide QR if it's not open
            qr_code_base64 = qr_res.get('qrcode', {}).get('base64')
            
        instance.status = state
        db.session.commit()
        
        return jsonify({
            'status': state,
            'qr_code_base64': qr_code_base64
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- VIEWS ---
@whatsapp_bp.route('/whatsapp')
@login_required
def inbox():
    from models import Pipeline, User
    pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
    users = User.query.filter_by(company_id=current_user.company_id).all()
    return render_template('whatsapp_inbox.html', pipelines=pipelines, users=users)

@whatsapp_bp.route('/whatsapp/groups')
@login_required
def groups():
    return render_template('whatsapp_groups.html')

# --- API ---
@whatsapp_bp.route('/api/whatsapp/conversations')
@login_required
def get_conversations():
    try:
        instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
        if not instance:
            return jsonify({'conversations': []})
            
        conversations = WhatsappConversation.query.filter_by(instance_id=instance.id).order_by(WhatsappConversation.updated_at.desc()).all()
        
        data = []
        for c in conversations:
            contact_type = 'atendimento'
            contact_id = c.remote_jid
            if c.lead_id:
                contact_type = 'lead'
                contact_id = c.lead_id
            elif c.client_id:
                contact_type = 'client'
                contact_id = c.client_id
                
            data.append({
                'id': contact_id,
                'type': contact_type,
                'phone': c.remote_jid,
                'name': c.name or c.remote_jid.split('@')[0],
                'profile_pic_url': c.profile_pic_url,
                'last_message_content': c.last_message_preview,
                'last_message_at': c.updated_at.isoformat() if c.updated_at else None,
                'last_message_dir': c.last_message_dir,
                'last_message_status': c.last_message_status,
                'unread_count': c.unread_count,
                'is_group': "@g.us" in c.remote_jid
            })
            
        return jsonify({'conversations': data})
    except Exception as e:
        current_app.logger.error(f"Inbox Error: {e}")
        return jsonify({'error': str(e)}), 500

@whatsapp_bp.route('/api/whatsapp/<string:type>/<string:contact_id>/messages', methods=['GET'])
@whatsapp_bp.route('/api/whatsapp/lead/<int:id>/messages', methods=['GET'], endpoint='get_lead_messages_legacy')
@whatsapp_bp.route('/api/whatsapp/client/<int:id>/messages', methods=['GET'], endpoint='get_client_messages_legacy')
@login_required
def get_history(type='lead', contact_id=None, id=None):
    contact_id = contact_id or id
    
    if not contact_id:
        return jsonify({'error': 'Missing contact ID'}), 400
    if 'lead' in request.endpoint: type = 'lead'
    if 'client' in request.endpoint: type = 'client'
    
    filters = []
    remote_jid = None
    
    if type == 'lead':
        obj = Lead.query.get_or_404(contact_id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        remote_jid = f"{obj.phone}@s.whatsapp.net" if obj.phone and "@" not in obj.phone else obj.phone
    elif type == 'client':
        obj = Client.query.get_or_404(contact_id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        remote_jid = f"{obj.phone}@s.whatsapp.net" if obj.phone and "@" not in obj.phone else obj.phone
    elif type == 'atendimento':
        remote_jid = contact_id
        if "@" not in remote_jid: remote_jid = f"{remote_jid}@s.whatsapp.net"
    else:
        return jsonify({'error': 'Invalid type'}), 400
        
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({'messages': []})
        
    conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
    if not conv:
        return jsonify({'messages': []})
        
    msgs = WhatsappMessage.query.filter_by(conversation_id=conv.id).order_by(WhatsappMessage.timestamp.asc()).all()
    
    return jsonify({
        'messages': [{
            'id': m.id,
            'message_id': m.message_id,
            'content': m.content,
            'direction': m.direction,
            'status': m.status,
            'type': m.type or 'text',
            'attachment_url': m.media_url,
            'timestamp': m.timestamp.isoformat() if m.timestamp else m.created_at.isoformat(),
            'sender_name': m.sender_name
        } for m in msgs]
    })

@whatsapp_bp.route('/api/whatsapp/send', methods=['POST'])
@login_required
def send_msg():
    data = request.json
    content = data.get('content')
    if not content: return jsonify({'error': 'No content'}), 400
    
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance: return jsonify({'error': 'No instance configured'}), 400
    
    remote_jid = data.get('remote_jid')
    if not remote_jid:
        if data.get('lead_id'):
            obj = Lead.query.get(data['lead_id'])
            remote_jid = obj.phone
        elif data.get('client_id'):
            obj = Client.query.get(data['client_id'])
            remote_jid = obj.phone
        else:
            return jsonify({'error': 'Target missing'}), 400
            
    if remote_jid and "@" not in remote_jid:
        remote_jid = f"{remote_jid}@s.whatsapp.net"
    
    try:
        res = EvolutionService.send_text(instance.instance_name, remote_jid, content)
        
        # Determine msg_id from response
        try:
            msg_id = res.get('key', {}).get('id', str(uuid.uuid4()))
        except:
            msg_id = str(uuid.uuid4())
            
        # Ensure conversation exists
        conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
        if not conv:
            conv = WhatsappConversation(
                company_id=current_user.company_id,
                instance_id=instance.id,
                remote_jid=remote_jid,
                lead_id=data.get('lead_id'),
                client_id=data.get('client_id'),
                last_message_preview=content
            )
            db.session.add(conv)
            db.session.flush()
        else:
            conv.last_message_preview = content
            conv.updated_at = datetime.utcnow()
            
        new_msg = WhatsappMessage(
            company_id=current_user.company_id,
            conversation_id=conv.id,
            message_id=msg_id,
            direction='out',
            type='text',
            content=content,
            status='sent'
        )
        db.session.add(new_msg)
        db.session.commit()
        
        return jsonify({'success': True, 'message': {'id': new_msg.id, 'content': new_msg.content, 'timestamp': datetime.utcnow().isoformat()}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@whatsapp_bp.route('/api/whatsapp/send-media', methods=['POST'])
@login_required
def send_media():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    
    lead_id = request.form.get('lead_id')
    client_id = request.form.get('client_id')
    
    if not lead_id and not client_id:
        return jsonify({'error': 'Target missing'}), 400
        
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance: return jsonify({'error': 'No instance configured'}), 400
    
    remote_jid = None
    if lead_id:
        obj = Lead.query.get(lead_id)
        remote_jid = obj.phone
    else:
        obj = Client.query.get(client_id)
        remote_jid = obj.phone
        
    if remote_jid and "@" not in remote_jid:
        remote_jid = f"{remote_jid}@s.whatsapp.net"

    mimetype = file.mimetype or 'application/octet-stream'
    filename = file.filename
    file_bytes = file.read()
    b64_data = base64.b64encode(file_bytes).decode('utf-8')
    
    # Evolution APIs accept media encoded cleanly or as data URI. Evolution v1/v2 expects base64 without data URI for media if it's sendMedia, but wait, usually you pass the base64 string directly or use data URL. 
    # Evolution supports data URL data:image/png;base64,..... or raw base64 depending on endpoint.
    # To be safe, we prepend data uri scheme. Let's prepend it as Evolution v1 parses it.
    base64_string = f"data:{mimetype};base64,{b64_data}"
    
    media_type = "document"
    if "image" in mimetype: media_type = "image"
    elif "video" in mimetype: media_type = "video"
    elif "audio" in mimetype: media_type = "audio"
    
    try:
        if media_type == 'audio':
            res = EvolutionService.send_audio(instance.instance_name, remote_jid, base64_string)
        else:
            res = EvolutionService.send_media(instance.instance_name, remote_jid, base64_string, media_type=media_type, caption=filename)
        
        # Determine msg_id
        try:
            msg_id = res.get('key', {}).get('id', str(uuid.uuid4()))
        except:
            msg_id = str(uuid.uuid4())
            
        conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
        if not conv:
            conv = WhatsappConversation(
                company_id=current_user.company_id,
                instance_id=instance.id,
                remote_jid=remote_jid,
                lead_id=lead_id,
                client_id=client_id,
                last_message_preview=f"[{media_type}] {filename}"
            )
            db.session.add(conv)
            db.session.flush()
        else:
            conv.last_message_preview = f"[{media_type}] {filename}"
            conv.updated_at = datetime.utcnow()
            
        new_msg = WhatsappMessage(
            company_id=current_user.company_id,
            conversation_id=conv.id,
            message_id=msg_id,
            direction='out',
            type=media_type,
            content=filename,
            media_url=base64_string, # In a real scale app you'd NOT save base64 in DB, but a URL
            status='sent'
        )
        db.session.add(new_msg)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- GROUPS (Evolution) ---
@whatsapp_bp.route('/api/whatsapp/groups', methods=['GET'])
@login_required
def get_groups():
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance: return jsonify({'groups': []})
    try:
        res = EvolutionService.get_all_groups(instance.instance_name)
        # Evolution usually returns an array or an object with groups list
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@whatsapp_bp.route('/api/whatsapp/groups/send', methods=['POST'])
@login_required
def send_group_msg():
    data = request.json
    group_jid = data.get('group_jid')
    content = data.get('content')
    if not group_jid or not content: return jsonify({'error': 'Missing data'}), 400
    
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance: return jsonify({'error': 'No instance'})
    
    try:
        res = EvolutionService.send_text(instance.instance_name, group_jid, content)
        return jsonify({'success': True, 'res': res})
    except Exception as e:
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

@whatsapp_bp.route('/api/whatsapp/read/<string:remote_jid>', methods=['POST'])
@login_required
def mark_read(remote_jid):
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance: return jsonify({'success': False})
    
    conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
    if conv:
        conv.unread_count = 0
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@whatsapp_bp.route('/api/whatsapp/unread-counts')
@login_required
@limiter.limit("600 per hour")
def get_unread_counts():
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance: return jsonify({'total': 0, 'by_tab': {}})
    
    convs = WhatsappConversation.query.filter_by(instance_id=instance.id).filter(WhatsappConversation.unread_count > 0).all()
    total = sum(c.unread_count for c in convs)
    
    return jsonify({
        'total': total,
        'by_tab': {'inbox': total} # Can be separated if needed
    })

@whatsapp_bp.route('/api/whatsapp/<string:type>/<string:id>/details', methods=['GET'])
@login_required
def get_details(type, id):
    obj = None
    if type == 'lead':
        obj = Lead.query.get_or_404(id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        
        tags = []
        if obj.status: tags.append({'text': obj.status, 'color': 'red' if obj.status == 'new' else 'gray'})
        if obj.source: tags.append({'text': obj.source, 'color': 'blue'})
        
        deal_value = obj.bant_budget or 'R$ 0,00'
        notes = obj.notes or ''
        name = obj.name
        pipeline_id = obj.pipeline_id
        stage_id = obj.pipeline_stage_id
        
    elif type == 'client':
        obj = Client.query.get_or_404(id)
        if obj.company_id != current_user.company_id: return jsonify({'error': 'Unauthorized'}), 403
        
        tags = []
        if obj.status: tags.append({'text': obj.status, 'color': 'green' if obj.status == 'ativo' else 'red'})
        if obj.service: tags.append({'text': obj.service, 'color': 'purple'})
        
        deal_value = f"R$ {obj.monthly_value:,.2f}" if obj.monthly_value else 'R$ 0,00'
        notes = obj.notes or ''
        name = obj.name
        pipeline_id = None
        stage_id = None
        
    elif type == 'atendimento':
        tags = [{'text': 'Desconhecido', 'color': 'gray'}]
        deal_value = 'R$ 0,00'
        notes = 'Este contato ainda não foi adicionado ao CRM.'
        pipeline_id = None
        stage_id = None
        
        instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
        name = id
        if instance:
            conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=id).first()
            if conv and conv.name: name = conv.name
    else:
        return jsonify({'error': 'Invalid type'}), 400
        
    return jsonify({
        'name': name,
        'tags': tags,
        'deal_value': deal_value,
        'notes': notes,
        'is_unknown': type == 'atendimento',
        'pipeline_id': pipeline_id,
        'stage_id': stage_id
    })

@whatsapp_bp.route('/api/whatsapp/atendimento/convert', methods=['POST'])
@login_required
def convert_unknown_to_lead():
    data = request.json
    phone = data.get('phone')
    name = data.get('name')
    email = data.get('email')
    
    if not phone or not name: 
        return jsonify({'error': 'Missing phone or name'}), 400
        
    from models import Pipeline, PipelineStage
    pipeline_id = data.get('pipeline_id')
    stage_id = data.get('stage_id')
    user_id = data.get('user_id') or current_user.id
    
    if not pipeline_id:
        pipeline = Pipeline.query.filter_by(company_id=current_user.company_id).first()
        if pipeline:
            pipeline_id = pipeline.id
            first_stage = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).first()
            if first_stage:
                stage_id = first_stage.id

    lead = Lead(
        company_id=current_user.company_id,
        name=name,
        phone=phone,
        email=email,
        status='new',
        source='whatsapp',
        assigned_to_id=user_id,
        pipeline_id=pipeline_id,
        pipeline_stage_id=stage_id
    )
    db.session.add(lead)
    db.session.flush()
    
    # Associate conversation
    remote_jid = f"{phone}@s.whatsapp.net" if "@" not in phone else phone
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if instance:
        conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
        if conv:
            conv.lead_id = lead.id
            
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
