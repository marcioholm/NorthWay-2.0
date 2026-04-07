from flask import Blueprint, request, jsonify, current_app
from models import db, WhatsappInstance, WhatsappConversation, WhatsappMessage
from services.evolution_service import EvolutionService
import requests
import os
from datetime import datetime

evolution_webhook_bp = Blueprint('evolution_webhook', __name__)

@evolution_webhook_bp.route('/api/webhooks/evolution', methods=['POST'])
def evolution_webhook():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
        
    event = data.get('event')
    instance_name = data.get('instance')
    
    current_app.logger.info(f"Evolution Webhook Event: {event} for instance {instance_name}")
    
    # 1. Verification of instance
    instance = WhatsappInstance.query.filter_by(instance_name=instance_name).first()
    if not instance:
        current_app.logger.warning(f"Webhook from unknown instance: {instance_name}")
        return jsonify({'success': True}), 200 # Accept but ignore
        
    company_id = instance.company_id
    
    # 2. Handle Connection State changes
    if event == 'CONNECTION_UPDATE':
        state = data.get('data', {}).get('state')
        if state:
            instance.status = state
            db.session.commit()
            
    # 3. Handle New Messages
    elif event == 'MESSAGES_UPSERT':
        # Evolution v2 often sends a list of messages in 'data.messages' or 'data.message'
        webhook_data = data.get('data', {})
        messages = webhook_data.get('messages', [])
        if not messages and webhook_data.get('message'):
            messages = [webhook_data.get('message')]
            
        if not messages:
            return jsonify({'success': True}), 200
            
        for message_data in messages:
            # Determine if it's sent from the instance (me) or incoming from remote
            key = message_data.get('key', {})
            is_from_me = key.get('fromMe', False)
            direction = 'out' if is_from_me else 'in'
            
            remote_jid = key.get('remoteJid')
            message_id = key.get('id')
            push_name = message_data.get('pushName') or (remote_jid.split('@')[0] if remote_jid else "Unknown")
        
        # Parse content (simplistic for text, image, etc.)
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
            media_url = "image_placeholder_url_or_base64" # Evolution provides base64 via API if needed
        elif 'audioMessage' in msg_object:
            msg_type = "audio"
        elif 'videoMessage' in msg_object:
            msg_type = "video"
        elif 'documentMessage' in msg_object:
            msg_type = "document"
            
        # If it's a completely empty system message, we can ignore
        if not content and msg_type == 'text':
            content = "[Mensagem do Sistema]"
            
        # Find or create Conversation
        conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
        if not conv:
            conv = WhatsappConversation(
                company_id=company_id,
                instance_id=instance.id,
                remote_jid=remote_jid,
                name=push_name,
                last_message_preview=content
            )
            db.session.add(conv)
            db.session.flush()
            
        conv.last_message_preview = content
        conv.last_message_dir = direction
        conv.last_message_status = 'sent' if direction == 'out' else 'received'
        conv.updated_at = datetime.utcnow()
        if direction == 'in':
            conv.unread_count += 1
            if push_name and not conv.name:
                conv.name = push_name
                
        # Check if message already exists
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
            
            # Forward to NORA (n8n Webhook) if it's an incoming message
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
            # If msg exists, update status
            db.session.commit()

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
