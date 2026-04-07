from flask import Blueprint, request, jsonify, current_app
from models import db, WhatsappInstance, WhatsappConversation, WhatsappMessage
from services.evolution_service import EvolutionService
import requests
import os
from datetime import datetime

evolution_webhook_bp = Blueprint('evolution_webhook', __name__)

@evolution_webhook_bp.route('/api/webhooks/evolution', methods=['GET', 'POST'])
def evolution_webhook():
    if request.method == 'GET':
        return jsonify({'status': 'webhook endpoint active', 'method': 'GET', 'info': 'Send a POST request with Evolution API payload here.'})

    try:
        from northway_crm.utils.webhook_logger import log_webhook_event
    except ImportError:
        from utils.webhook_logger import log_webhook_event
        
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    
    # Store for debug inspection
    log_webhook_event(data)
        
    event = data.get('event')
    instance_name = data.get('instance')
    
    # NORMALIZATION: Robust matching for instance names (case-insensitive, ignore hyphens/spaces)
    def normalize(s):
        if not s: return ""
        return s.lower().replace(' ', '').replace('-', '').replace('_', '')

    normalized_name = normalize(instance_name)
    
    current_app.logger.info(f"Evolution Webhook Event: {event} for instance {instance_name} (normalized: {normalized_name})")
    
    # 1. Verification of instance
    instance = None
    all_instances = WhatsappInstance.query.all()
    for inst in all_instances:
        if normalize(inst.instance_name) == normalized_name:
            instance = inst
            break

    if not instance:
        current_app.logger.warning(f"Webhook from unknown instance: {instance_name}. Known instances: {[i.instance_name for i in all_instances]}")
        # Save raw debug info for the administrator if it's missing
        try:
            with open('/tmp/last_whatsapp_webhook_error.json', 'w') as f:
                import json
                json.dump(data, f)
        except: pass
        return jsonify({'success': True}), 200 # Accept but ignore
        
    company_id = instance.company_id
    
    # NORMALIZATION: Map common event names
    event_upper = event.upper().replace('.', '_')
    
    # 2. Handle Connection State changes
    if event_upper == 'CONNECTION_UPDATE':
        state = data.get('data', {}).get('state')
        if state:
            instance.status = state
            db.session.commit()
            
    # 3. Handle New Messages
    elif event_upper == 'MESSAGES_UPSERT' or event_upper == 'MESSAGES_SET':
        # Evolution v2 often sends a list of messages in 'data.messages' or 'data.message'
        webhook_data = data.get('data', {})
        messages = webhook_data.get('messages', [])
        if not messages and webhook_data.get('message'):
            messages = [webhook_data.get('message')]
            
        if not messages:
            return jsonify({'success': True}), 200
            
        for message_data in messages:
            try:
                # 3.1. Parsing basic identifiers
                key = message_data.get('key', {})
                is_from_me = key.get('fromMe', False)
                direction = 'out' if is_from_me else 'in'
                
                remote_jid = key.get('remoteJid')
                message_id = key.get('id')
                push_name = message_data.get('pushName') or (remote_jid.split('@')[0] if remote_jid else "Unknown")
                
                current_app.logger.info(f"Processing message {message_id} from {remote_jid} ({direction})")
                
                # 3.2. Content Extraction
                content = ""
                msg_type = "text"
                msg_object = message_data.get('message', {})
                media_url = None
                
                if 'conversation' in msg_object:
                    content = msg_object['conversation']
                elif 'extendedTextMessage' in msg_object:
                    content = msg_object['extendedTextMessage'].get('text', '')
                elif 'imageMessage' in msg_object:
                    msg_type = "image"
                    content = msg_object['imageMessage'].get('caption', '')
                    media_url = "image_media" # Placeholder, actual media handle depends on API
                elif 'audioMessage' in msg_object:
                    msg_type = "audio"
                elif 'videoMessage' in msg_object:
                    msg_type = "video"
                elif 'documentMessage' in msg_object:
                    msg_type = "document"
                    
                if not content and msg_type == 'text':
                    content = "[Mensagem do Sistema]"
                
                # 3.3. Conversation Management
                conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
                if not conv:
                    current_app.logger.info(f"Creating new conversation for {remote_jid}")
                    conv = WhatsappConversation(
                        company_id=company_id,
                        instance_id=instance.id,
                        remote_jid=remote_jid,
                        name=push_name,
                        last_message_preview=content[:200]
                    )
                    db.session.add(conv)
                    db.session.flush()
                
                conv.last_message_preview = content[:255]
                conv.last_message_at = datetime.utcnow()
                conv.last_message_dir = direction
                conv.last_message_status = 'sent' if direction == 'out' else 'received'
                conv.updated_at = datetime.utcnow()
                
                if direction == 'in':
                    conv.unread_count = (conv.unread_count or 0) + 1
                    if push_name and (not conv.name or conv.name == remote_jid.split('@')[0]):
                        conv.name = push_name
                
                # 3.4. Message Persistence
                existing_msg = WhatsappMessage.query.filter_by(message_id=message_id).first()
                if not existing_msg:
                    timestamp = message_data.get('messageTimestamp')
                    dt_timestamp = datetime.utcfromtimestamp(timestamp) if timestamp else datetime.utcnow()
                    
                    new_msg = WhatsappMessage(
                        company_id=company_id,
                        conversation_id=conv.id,
                        message_id=message_id,
                        direction=direction,
                        type=msg_type,
                        content=content,
                        media_url=media_url,
                        status=conv.last_message_status,
                        timestamp=dt_timestamp,
                        sender_name=push_name if direction == 'in' else "Você"
                    )
                    db.session.add(new_msg)
                    db.session.commit()
                    current_app.logger.info(f"Successfully saved message {message_id}")
                    
                    # 3.5. Forward to NORA (n8n Webhook)
                    if direction == 'in':
                        nora_url = os.environ.get('NORA_WEBHOOK_URL')
                        if nora_url:
                            try:
                                nora_payload = {
                                    'company_id': company_id,
                                    'remote_jid': remote_jid,
                                    'message_id': message_id,
                                    'content': content,
                                    'type': msg_type,
                                    'sender_name': push_name,
                                    'lead_id': conv.lead_id,
                                    'client_id': conv.client_id
                                }
                                requests.post(nora_url, json=nora_payload, timeout=5)
                            except Exception as e:
                                current_app.logger.error(f"Error forwarding to Nora: {e}")
                else:
                    db.session.commit() # Update conversation state
            except Exception as e:
                current_app.logger.error(f"Error processing message in loop: {e}")
                db.session.rollback()

    # 4. Handle Message Status Updates (Delivered, Read etc)
    elif event == 'MESSAGES_UPDATE':
        # Evolution can send a list of updates
        updates = data.get('data', [])
        if not isinstance(updates, list):
            updates = [updates]
            
        for update in updates:
            msg_id = update.get('key', {}).get('id')
            status_map = {1: 'sent', 2: 'delivered', 3: 'read', 4: 'played'}
            num_status = update.get('update', {}).get('status')
            
            if msg_id and num_status in status_map:
                msg = WhatsappMessage.query.filter_by(message_id=msg_id).first()
                if msg:
                    new_status = status_map[num_status]
                    msg.status = new_status
                    
                    # Also update conversation if this was the last message
                    conv = WhatsappConversation.query.get(msg.conversation_id)
                    if conv:
                        conv.last_message_status = new_status
                        
                    db.session.commit()
                    
    return jsonify({'success': True}), 200
