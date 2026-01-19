from models import db, Integration, WhatsAppMessage, Lead, Client
from flask import current_app
from utils import update_integration_health, retry_request
import requests
import json
import re
from datetime import datetime
import base64

class WhatsAppService:
    @staticmethod
    def get_config(company_id):
        """Retrieves and validates Z-API configuration for a company."""
        integration = Integration.query.filter_by(company_id=company_id, service='z_api', is_active=True).first()
        if not integration:
            return None
        
        try:
            config = json.loads(integration.config_json) if integration.config_json else {}
            api_url = config.get('api_url', 'https://api.z-api.io')
            
            # Robustness: Remove instance/token/method if user pasted full URL
            if '/instances/' in api_url:
                api_url = api_url.split('/instances/')[0]
            api_url = api_url.rstrip('/')
                
            return {
                'instance_id': config.get('instance_id'),
                'api_url': api_url,
                'client_token': config.get('client_token'),
                'token': integration.api_key
            }
        except Exception as e:
            current_app.logger.error(f"Error parsing Z-API config: {e}")
            return None

    @staticmethod
    def normalize_phone(phone):
        """Cleans phone number: removes chars, ensures 55 prefix (BR standard)."""
        if not phone: return None
        
        # Remove non-digits
        clean = re.sub(r'\D', '', phone)
        
        if not clean: return None
        
        # Basic Brazil rule: if 10 or 11 chars, add 55
        if len(clean) in [10, 11]:
            clean = '55' + clean
            
        return clean

    @staticmethod
    def find_contact(phone, company_id):
        """Finds a Lead or Client by phone number (trying various formats)."""
        if not phone: return None, None # type, obj
        
        # Possible formats stored in DB vs Invoice
        # Incoming often has 55...
        # DB might have (XX) ... or 55...
        
        # Strategy: normalize incoming to clean digits
        clean_incoming = re.sub(r'\D', '', phone)
        # Remove 55 if exists for searching local numbers
        local_incoming = clean_incoming[2:] if clean_incoming.startswith('55') else clean_incoming
        
        # Try finding Lead
        # We search matching the exact number or the number without country code
        # Ideally DB phones should be normalized, but we handle legacy dirty data
        
        # Search Client FIRST (Priority)
        client = Client.query.filter(
            (Client.phone == clean_incoming) | 
            (Client.phone == local_incoming) |
            (Client.phone == f"+{clean_incoming}") |
            (Client.phone == f"+{local_incoming}")
        ).filter_by(company_id=company_id).first()
        
        if client: return 'client', client

        # Search Lead
        lead = Lead.query.filter(
            (Lead.phone == clean_incoming) | 
            (Lead.phone == local_incoming) |
            (Lead.phone == f"+{clean_incoming}") |
            (Lead.phone == f"+{local_incoming}")
        ).filter_by(company_id=company_id).first()
        
        if lead: return 'lead', lead
        
        return None, None

    @staticmethod
    def send_message(company_id, target_type, target_id, content, media_file=None):
        """Sends a text or media message via Z-API."""
        config = WhatsAppService.get_config(company_id)
        if not config:
            raise Exception("WhatsApp não configurado para esta empresa.")

        # Get Target
        if target_type == 'lead':
            target = Lead.query.get(target_id)
        elif target_type == 'client':
            target = Client.query.get(target_id)
        else:
            raise Exception("Tipo de contato inválido.")
            
        if not target or target.company_id != company_id:
            raise Exception("Contato não encontrado ou sem permissão.")

        phone = WhatsAppService.normalize_phone(target.phone)
        if not phone:
             raise Exception("Contato sem telefone válido.")

        # Prepare Headers
        headers = {}
        if config.get('client_token'):
            headers['Client-Token'] = config['client_token']

        # API Base
        base_url = f"{config['api_url']}/instances/{config['instance_id']}/token/{config['token']}"
        
        payload = {"phone": phone}
        endpoint = "send-text"
        
        if media_file:
            # Handle Media
            file_content = media_file.read()
            b64_data = "data:{};base64,{}".format(
                media_file.mimetype or 'application/octet-stream',
                base64.b64encode(file_content).decode('utf-8')
            )
            
            if media_file.mimetype and media_file.mimetype.startswith('audio'):
                 endpoint = "send-audio"
                 payload["audio"] = b64_data
            elif media_file.mimetype and media_file.mimetype.startswith('image'):
                 endpoint = "send-image"
                 payload["image"] = b64_data
                 payload["caption"] = content or media_file.filename
            else:
                 endpoint = "send-document"
                 payload["document"] = b64_data
                 payload["fileName"] = media_file.filename
        else:
            payload["message"] = content

        try:
            url = f"{base_url}/{endpoint}"
            
            @retry_request()
            def perform_send(payload_data):
                return requests.post(url, json=payload_data, headers=headers, timeout=15)
            
            res = perform_send(payload)
            data = res.json()
            
            # 9th Digit Fallback (Brazil)
            # If fail or if it's a 13-digit BR number, Z-API sometimes accepts but doesn't deliver
            # To be safe, if the first try returns an error or if we want to ensure delivery:
            error_msg = data.get('error') or data.get('errorMessage')
            if (res.status_code >= 400 or error_msg) and len(phone) == 13 and phone.startswith('55'):
                # Try without the 9 (e.g., 55 42 9 8888 8888 -> 55 42 8888 8888)
                phone_no_9 = phone[:4] + phone[5:]
                payload["phone"] = phone_no_9
                res = perform_send(payload)
                data = res.json()
                error_msg = data.get('error') or data.get('errorMessage')

            # Z-API error handling
            if res.status_code >= 400 or error_msg:
                # Save as FAILED
                msg = WhatsAppMessage(
                    company_id=company_id,
                    lead_id=target.id if target_type == 'lead' else None,
                    client_id=target.id if target_type == 'client' else None,
                    direction='out',
                    content=content if not media_file else f"[{'FOTO' if 'image' in endpoint else 'ARQUIVO'}] {media_file.filename}",
                    status='failed'
                )
                db.session.add(msg)
                db.session.commit()
                
                err_text = f"Z-API Error ({res.status_code}): {error_msg}"
                update_integration_health(company_id, 'z_api', error=err_text)
                raise Exception(err_text)

            # Save to DB as SUCCESS
            msg = WhatsAppMessage(
                company_id=company_id,
                lead_id=target.id if target_type == 'lead' else None,
                client_id=target.id if target_type == 'client' else None,
                direction='out',
                content=content if not media_file else f"[{'FOTO' if 'image' in endpoint else 'ARQUIVO'}] {media_file.filename}",
                status='sent',
                external_id=data.get('messageId')
            )
            db.session.add(msg)
            db.session.commit()
            
            update_integration_health(company_id, 'z_api')
            return msg
            
        except Exception as e:
            current_app.logger.error(f"Z-API Send Error: {e}")
            # If it's not a known Z-API error (e.g. timeout, connection), still log it
            if not isinstance(e, Exception) or "Z-API Error" not in str(e):
                update_integration_health(company_id, 'z_api', error=str(e))
            raise e
    @staticmethod
    def fetch_profile_picture(company_id, phone):
        """Fetches the profile picture URL from Z-API."""
        config = WhatsAppService.get_config(company_id)
        if not config: return None

        clean_phone = WhatsAppService.normalize_phone(phone)
        if not clean_phone: return None

        url = f"{config['api_url']}/instances/{config['instance_id']}/token/{config['token']}/profile-picture"
        headers = {'Client-Token': config['client_token']} if config.get('client_token') else {}
        
        try:
            @retry_request()
            def perform_fetch(p):
                return requests.get(url, params={'phone': p}, headers=headers, timeout=10)
            
            # 1. Try standard phone
            res = perform_fetch(clean_phone)
            data = res.json()
            
            link = data.get('link')
            if link and link != "null": 
                update_integration_health(company_id, 'z_api')
                return link
                
            if data.get('errorMessage') == 'item-not-found':
                clean_phone_full = f"{clean_phone}@c.us" # Try c.us
                res = perform_fetch(clean_phone_full)
                data = res.json()
                
                link = data.get('link')
                if link and link != "null": 
                    update_integration_health(company_id, 'z_api')
                    return link

            # 3. Retry without 9th digit (Common Brazil Issue)
            # If length is 13 (55 + 2 DDD + 9 + 8 digits)
            if len(clean_phone) == 13 and clean_phone.startswith('55'):
                # 55 42 9 8888 8888 -> Index 4 is the extra 9
                clean_no_9 = clean_phone[:4] + clean_phone[5:]
                clean_no_9_full = f"{clean_no_9}@c.us"
                
                res = perform_fetch(clean_no_9_full)
                data = res.json()
                
                link = data.get('link')
                if link and link != "null": 
                    update_integration_health(company_id, 'z_api')
                    return link

            if 'eurl' in data and data['eurl']: 
                update_integration_health(company_id, 'z_api')
                return data['eurl']
            if 'imgUrl' in data and data['imgUrl']: 
                update_integration_health(company_id, 'z_api')
                return data['imgUrl']
                 
            return None
        except Exception as e:
            current_app.logger.error(f"Error fetching profile pic: {e}")
            update_integration_health(company_id, 'z_api', error=e)
            return None
    @staticmethod
    def get_inbox_conversations(company_id, limit=500):
        """
        Fetches recent messages and groups them into unique conversations.
        Returns a list of conversation dicts ready for frontend.
        """
        # Fetch recent messages
        messages = WhatsAppMessage.query.filter_by(company_id=company_id)\
            .order_by(WhatsAppMessage.created_at.desc())\
            .limit(limit).all()
            
        conversations = {} # Key: "type_id" -> Data
        
        for m in messages:
            if m.lead_id:
                key = f"lead_{m.lead_id}"
                c_type = 'lead'
                c_id = m.lead_id
            elif m.client_id:
                key = f"client_{m.client_id}"
                c_type = 'client'
                c_id = m.client_id
            else:
                continue # Orphan message
                
            if key not in conversations:
                # First time seeing this contact (since we ordered by desc, this IS the latest msg)
                
                # Fetch Name lazily (n+1 problem, but usually okay for small inbox page size)
                # Optimization: Could preload contacts, but lets keep it simple first
                name = "Desconhecido"
                phone = ""
                unread = 0 # Todo: Implement
                
                if c_type == 'lead':
                    obj = Lead.query.get(c_id)
                else:
                    obj = Client.query.get(c_id)
                    
                if obj:
                    name = obj.name
                    phone = obj.phone
                
                conversations[key] = {
                    'type': c_type,
                    'id': c_id,
                    'name': name,
                    'phone': phone,
                    'last_message_content': m.content,
                    'last_message_at': m.created_at.isoformat(),
                    'last_message_dir': m.direction,
                    'last_message_status': m.status,
                    'last_message_status': m.status,
                    'unread_count': unread,
                    'profile_pic_url': getattr(obj, 'profile_pic_url', None)
                }
                
        return list(conversations.values())

    @staticmethod
    def process_webhook(company_id, data):
        """Processes incoming Z-API webhook payload."""
        
        # 1. Handle Status Updates (Checkmarks)
        if 'status' in data and 'messageId' in data:
            ext_id = data.get('messageId')
            new_status = data.get('status', '').lower()
            # Map Z-API status to our status
            # Z-API: RECEIVED, READ, etc.
            status_map = {
                'received': 'delivered',
                'read': 'read',
                'sent': 'sent'
            }
            final_status = status_map.get(new_status, new_status)
            
            msg = WhatsAppMessage.query.filter_by(company_id=company_id, external_id=ext_id).first()
            if msg:
                msg.status = final_status
                db.session.commit()
                return {'success': True, 'type': 'status_update'}

        # 2. Extract Phone and Body
        phone = data.get('phone')
        if not phone and 'sender' in data:
             sender = data['sender']
             if isinstance(sender, dict): phone = sender.get('phone')
             elif isinstance(sender, str): phone = sender.split('@')[0]
             
        from_me = data.get('fromMe', False)

        # Get Body - handle different types
        body = data.get('message') or data.get('content')
        if not body:
            if 'text' in data:
                body = data.get('text', {}).get('message')
            elif 'image' in data:
                body = f"[FOTO] {data.get('image', {}).get('caption', '')}".strip()
            elif 'audio' in data:
                body = "[ÁUDIO]"
            elif 'video' in data:
                body = "[VÍDEO]"
            elif 'document' in data:
                body = f"[ARQUIVO] {data.get('document', {}).get('fileName', '')}".strip()

        if not phone or not body:
            return {'ignored': True, 'reason': 'missing_data'}
            
        # 3. Find Contact
        c_type, contact = WhatsAppService.find_contact(phone, company_id)

        # 3a. Update Profile Pic (if present)
        sender_image = data.get('senderImage') or data.get('photo')
        if contact and sender_image:
            contact.profile_pic_url = sender_image
        
        if not contact:
            current_app.logger.warning(f"Inbound from unknown: {phone}")
            return {'status': 'unknown_contact', 'phone': phone}
            
        try:
            # 4. Save Message
            msg = WhatsAppMessage(
                company_id=company_id,
                lead_id=contact.id if c_type == 'lead' else None,
                client_id=contact.id if c_type == 'client' else None,
                direction='out' if from_me else 'in',
                content=body,
                status='sent' if from_me else 'delivered',
                external_id=data.get('messageId')
            )
            db.session.add(msg)
            db.session.commit()
            
            update_integration_health(company_id, 'z_api')
            return {'success': True, 'msg_id': msg.id}
        except Exception as e:
            db.session.rollback()
            update_integration_health(company_id, 'z_api', error=e)
            raise e

    @staticmethod
    def configure_webhook(company_id, webhook_url):
        """
        Configures the Z-API webhooks programmatically.
        Updates all relevant webhook endpoints.
        """
        config = WhatsAppService.get_config(company_id)
        if not config:
            raise Exception("WhatsApp não configurado.")

        base_url = f"{config['api_url']}/instances/{config['instance_id']}/token/{config['token']}"
        headers = {'Client-Token': config['client_token']} if config.get('client_token') else {}
        
        # Endpoints to update
        endpoints = [
            "update-webhook-received",
            "update-webhook-sent",
            "update-webhook-disconnected",
            "update-webhook-connected",
            "update-webhook-message-status"
        ]
        
        results = []
        failed_endpoints = []
        for endp in endpoints:
            try:
                url = f"{base_url}/{endp}"
                payload = {"value": webhook_url}
                
                @retry_request()
                def perform_put():
                    return requests.put(url, json=payload, headers=headers, timeout=10)
                
                res = perform_put()
                if res.status_code not in [200, 201]:
                    failed_endpoints.append(f"{endp} ({res.status_code}: {res.text[:100]})")
                    results.append(False)
                else:
                    results.append(True)
            except Exception as e:
                current_app.logger.error(f"Error updating Z-API webhook {endp}: {e}")
                failed_endpoints.append(f"{endp} (Exception: {str(e)})")
                results.append(False)
                
        if all(results):
            return True
        else:
            error_details = ", ".join(failed_endpoints)
            raise Exception(f"Falha ao configurar webhooks: {error_details}")
