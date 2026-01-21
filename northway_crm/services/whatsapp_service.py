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
        try:
            cid = int(company_id)
        except:
            current_app.logger.error(f"Z-API ERROR: Invalid company_id: {company_id}")
            return None

        integration = Integration.query.filter_by(company_id=cid, service='z_api').first()
        
        if not integration:
            current_app.logger.warning(f"Z-API ERROR: No integration record found for company {cid} in service 'z_api'")
            return None
            
        if not integration.is_active:
            current_app.logger.warning(f"Z-API ERROR: Integration found but NOT ACTIVE for company {cid}")
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
        """
        Force canonical format: 55 + DDD + Number.
        Removes all formatting and ensures BR country code.
        """
        if not phone: return None
        
        # 1. Clean digits
        clean = re.sub(r'\D', '', str(phone))
        if not clean: return None
        
        # 2. Add Country Code if missing (assuming Brazil)
        # If 10 or 11 digits (DDD + 8 or 9 digits)
        if len(clean) in [10, 11]:
            clean = '55' + clean
            
        return clean

    @staticmethod
    def find_contact(phone, company_id):
        """Finds a Lead or Client by phone number (trying various aggressive matching formats)."""
        if not phone: return None, None
        
        # 1. Clean digits
        clean = re.sub(r'\D', '', phone)
        if not clean: return None, None
        
        # 2. Extract variants
        # Variant A: Full (e.g. 554299896358)
        # Variant B: Local (e.g. 4299896358) - remove '55' if exists
        local = clean[2:] if clean.startswith('55') and len(clean) > 10 else clean
        
        # Variant C: 9th digit adjustment
        # If it has the extra 9 (length 11 local or 13 full), generates a version without it
        # If it DOESN'T have it, generates a version with it (assuming 55 + 2 DDD + 8 digits)
        variants = {clean, local}
        
        if len(local) == 11 and local[2] == '9': # 42 9 9989 6358
            no_9 = local[:2] + local[3:]
            variants.add(no_9)
            variants.add('55' + no_9)
        elif len(local) == 10: # 42 9989 6358 (common legacy or Z-API format)
            with_9 = local[:2] + '9' + local[2:]
            variants.add(with_9)
            variants.add('55' + with_9)
            
        # 3. Search Loop
        # We use a broad filter then filter in-memory or more complex query
        from models import Lead, Client
        
        for v in variants:
            # Search Lead
            lead = Lead.query.filter_by(company_id=company_id).filter(
                (Lead.phone.ilike(f"%{v}"))
            ).first()
            if lead: return 'lead', lead
            
            # Search Client
            client = Client.query.filter_by(company_id=company_id).filter(
                (Client.phone.ilike(f"%{v}"))
            ).first()
            if client: return 'client', client
            
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
                    phone=WhatsAppService.normalize_phone(target.phone),
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
                phone=WhatsAppService.normalize_phone(target.phone),
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
    def store_media_in_supabase(company_id, media_url, file_extension):
        """Downloads media from Z-API and stores it in Supabase for persistence."""
        from flask import current_app
        supabase = getattr(current_app, 'supabase', None)
        if not supabase:
            return media_url

        try:
            # 1. Download from Z-API
            res = requests.get(media_url, timeout=20)
            if res.status_code != 200:
                return media_url
            
            # 2. Prepare Path
            import uuid
            filename = f"{uuid.uuid4()}.{file_extension}"
            path = f"company_{company_id}/{filename}"
            bucket = "whatsapp_media"
            
            # 3. Upload to Supabase
            supabase.storage.from_(bucket).upload(
                path=path,
                file=res.content,
                file_options={"content-type": res.headers.get('Content-Type', 'application/octet-stream')}
            )
            
            # 4. Get Public URL
            public_url = supabase.storage.from_(bucket).get_public_url(path)
            current_app.logger.info(f"WhatsApp media stored successfully: {public_url}")
            return public_url
        except Exception as e:
            current_app.logger.error(f"Supabase Media Storage Error for URL {media_url}: {str(e)}")
            # Try to provide more detail if available
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                current_app.logger.error(f"Supabase Response: {e.response.text}")
            return media_url

    @staticmethod
    def get_inbox_conversations(company_id, limit=300):
        """
        Fetches recent messages and groups them into unique conversations by PHONE.
        Ensures that multiple contacts with the same phone appear as one thread.
        Uses eager loading to prevent N+1 overhead.
        """
        try:
            from sqlalchemy.orm import joinedload
            from models import Contact
            
            # 1. Fetch recent messages with relations pre-loaded
            messages = WhatsAppMessage.query.options(
                joinedload(WhatsAppMessage.contact).joinedload(Contact.leads),
                joinedload(WhatsAppMessage.contact).joinedload(Contact.clients)
            ).filter_by(company_id=company_id)\
                .order_by(WhatsAppMessage.created_at.desc())\
                .limit(limit).all()
            
            if not messages:
                return []

            # 3. Group by Contact UUID
            conversations = {} 
            import uuid
            
            for m in messages:
                # Primary Grouping Key: Contact UUID
                key = m.contact_uuid
                
                # Fallback for legacy/unlinked (shouldn't happen after migration)
                if not key:
                   norm = WhatsAppService.normalize_phone(m.phone)
                   key = f"phone_{norm}"
                   
                if key not in conversations:
                    # Resolve Display Info
                    name = m.sender_name or m.phone
                    c_type = 'atendimento'
                    c_id = m.phone or f"unknown_{uuid.uuid4()}" # Fallback
                    pic_url = m.profile_pic_url
                    
                    if m.contact:
                         # Prefer Client > Lead info if linked
                         if m.contact.clients:
                             client = m.contact.clients[0]
                             name = client.name
                             c_type = 'client'
                             c_id = client.id
                             pic_url = pic_url or getattr(client, 'profile_pic_url', None)
                         elif m.contact.leads:
                             lead = m.contact.leads[0]
                             name = lead.name
                             c_type = 'lead'
                             c_id = lead.id
                             pic_url = pic_url or getattr(lead, 'profile_pic_url', None)
                             
                    conversations[key] = {
                        'key': key, # Internal tracking
                        'type': c_type,
                        'id': c_id, # This is the ID used for routes/links
                        'name': name,
                        'phone': m.contact.phone if m.contact else m.phone,
                        'last_message_content': m.content,
                        'last_message_at': m.created_at.isoformat(),
                        'last_message_dir': m.direction,
                        'last_message_status': m.status,
                        # Unread count needs to be aggregated by CONTACT_UUID now
                        'unread_count': 0, 
                        'profile_pic_url': pic_url
                    }
                    
            # 4. Fill Unread Counts (by Contact UUID)
            unread_stats = db.session.query(
                WhatsAppMessage.contact_uuid,
                db.func.count(WhatsAppMessage.id)
            ).filter(
                WhatsAppMessage.company_id == company_id,
                WhatsAppMessage.direction == 'in',
                WhatsAppMessage.status != 'read',
                WhatsAppMessage.contact_uuid != None
            ).group_by(
                WhatsAppMessage.contact_uuid
            ).all()
            
            unread_map = {u: c for u, c in unread_stats}
            
            for k, v in conversations.items():
                if k in unread_map:
                    v['unread_count'] = unread_map[k]
                    
        except Exception as e:
            current_app.logger.error(f"Error in get_inbox_conversations: {e}")
            raise e
        
        result = sorted(conversations.values(), key=lambda x: x['last_message_at'], reverse=True)
        return result

    @staticmethod
    def get_unread_summary(company_id):
        """Returns total unread count and count by tab efficiently (no N+1)."""
        try:
            counts = db.session.query(
                db.case(
                    (WhatsAppMessage.lead_id != None, 'lead'),
                    (WhatsAppMessage.client_id != None, 'client'),
                    else_='atendimento'
                ).label('type'),
                db.func.count(WhatsAppMessage.id)
            ).filter(
                WhatsAppMessage.company_id == company_id,
                WhatsAppMessage.direction == 'in',
                WhatsAppMessage.status != 'read'
            ).group_by('type').all()
            
            total = 0
            by_tab = {'lead': 0, 'client': 0, 'atendimento': 0}
            
            for c_type, count in counts:
                total += count
                if c_type in by_tab:
                    by_tab[c_type] = count
            
            return total, by_tab
        except Exception as e:
            current_app.logger.error(f"Error in get_unread_summary: {e}")
            return 0, {'lead': 0, 'client': 0, 'atendimento': 0}

    @staticmethod
    def mark_as_read(company_id, phone):
        """Marks all incoming messages from a contact as read (resilient matching)."""
        try:
            # 1. Normalize phone to ensure consistency
            norm_phone = WhatsAppService.normalize_phone(phone)
            
            # 2. Find Contact/Lead/Client
            c_type, contact_obj = WhatsAppService.find_contact(norm_phone, company_id)
            
            # 3. Build Query
            query = WhatsAppMessage.query.filter_by(company_id=company_id, direction='in')
            
            # 4. Filter by ID if available (Strong Match)
            if c_type == 'lead':
                query = query.filter(db.or_(WhatsAppMessage.lead_id == contact_obj.id, WhatsAppMessage.phone == norm_phone))
                # Update lead profile pic if missing and message has one
                last_msg = WhatsAppMessage.query.filter_by(lead_id=contact_obj.id).order_by(WhatsAppMessage.created_at.desc()).first()
                if last_msg and last_msg.profile_pic_url and not contact_obj.profile_pic_url:
                    contact_obj.profile_pic_url = last_msg.profile_pic_url
            elif c_type == 'client':
                query = query.filter(db.or_(WhatsAppMessage.client_id == contact_obj.id, WhatsAppMessage.phone == norm_phone))
            else:
                # Fallback to Phone/Contact UUID (Loose Match)
                from models import Contact
                contact = Contact.query.filter_by(company_id=company_id, phone=norm_phone).first()
                if contact:
                    query = query.filter(db.or_(WhatsAppMessage.contact_uuid == contact.uuid, WhatsAppMessage.phone == norm_phone))
                else:
                    query = query.filter_by(phone=norm_phone)

            # 5. Execute Update
            query.filter(WhatsAppMessage.status != 'read').update({WhatsAppMessage.status: 'read'}, synchronize_session=False)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in mark_as_read: {e}")
            return False
            current_app.logger.error(f"Error marking as read: {e}")
            return False

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
        from_me = data.get('fromMe', False)
        phone = data.get('phone')
        
        # If it's fromMe, the 'phone' field in Z-API might be the sender's phone, 
        # while 'to' is the actual contact.
        if from_me and data.get('to'):
            phone = data.get('to')
            
        if not phone and 'sender' in data:
             sender = data['sender']
             if isinstance(sender, dict): phone = sender.get('phone')
             elif isinstance(sender, str): phone = sender.split('@')[0]
             
        if not phone:
            return {'ignored': True, 'reason': 'missing_phone'}

        norm_phone = WhatsAppService.normalize_phone(phone)
        attachment_url = None
        msg_type = 'text'
        body = "" # FIX: Initialize body to avoid UnboundLocalError

        if 'text' in data:
            body = data.get('text', {}).get('message')
        elif 'image' in data:
            img_data = data.get('image', {})
            raw_url = img_data.get('url') or img_data.get('imageUrl')
            # Persistent storage
            attachment_url = WhatsAppService.store_media_in_supabase(company_id, raw_url, 'jpg')
            body = img_data.get('caption') or "[FOTO]"
            msg_type = 'image'
        elif 'audio' in data:
            raw_url = data.get('audio', {}).get('url')
            # Persistent storage (Z-API audios are usually .ogg or .mp3)
            attachment_url = WhatsAppService.store_media_in_supabase(company_id, raw_url, 'ogg')
            body = "[ÁUDIO]"
            msg_type = 'audio'
        elif 'video' in data:
            raw_url = data.get('video', {}).get('url')
            attachment_url = WhatsAppService.store_media_in_supabase(company_id, raw_url, 'mp4')
            body = "[VÍDEO]"
            msg_type = 'video'
        elif 'document' in data:
            doc_data = data.get('document', {})
            raw_url = doc_data.get('url')
            ext = doc_data.get('fileName', '').split('.')[-1] if '.' in doc_data.get('fileName', '') else 'dat'
            attachment_url = WhatsAppService.store_media_in_supabase(company_id, raw_url, ext)
            body = doc_data.get('fileName') or "[ARQUIVO]"
            msg_type = 'document'
        
        # Fallback if body still empty but message/content exists in roots
        if not body:
            body = data.get('message') or data.get('content') or ""

        if not phone or not body:
            return {'ignored': True, 'reason': 'missing_data'}
            
        # 3. Find or Create Contact
        from models import Contact
        import uuid
        
        contact = Contact.query.filter_by(company_id=company_id, phone=norm_phone).first()
        if not contact:
            contact = Contact(
                uuid=str(uuid.uuid4()),
                company_id=company_id,
                phone=norm_phone,
                created_at=datetime.utcnow()
            )
            db.session.add(contact)
            db.session.flush()

        # 4. Profile Picture
        incoming_pic = data.get('senderImage') or data.get('photo')
        if incoming_pic:
             contact.profile_pic_url = incoming_pic

        # 5. Link to Lead/Client (Strict then Loose)
        lead_id = contact.leads[0].id if contact.leads else None
        client_id = contact.clients[0].id if contact.clients else None
        
        if not lead_id and not client_id:
             c_type, found_obj = WhatsAppService.find_contact(norm_phone, company_id)
             if c_type == 'lead':
                 lead_id = found_obj.id
                 found_obj.contact_uuid = contact.uuid # Sync UUID
             elif c_type == 'client':
                 client_id = found_obj.id
                 found_obj.contact_uuid = contact.uuid # Sync UUID

        # 6. Save Message
        sender_name = data.get('senderName')
        try:
            msg = WhatsAppMessage(
                company_id=company_id,
                lead_id=lead_id,
                client_id=client_id,
                contact_uuid=contact.uuid,
                phone=norm_phone,
                sender_name=sender_name,
                direction='out' if from_me else 'in',
                type=msg_type,
                content=body,
                attachment_url=attachment_url,
                profile_pic_url=incoming_pic,
                status='sent' if from_me else 'delivered',
                external_id=data.get('messageId')
            )
            db.session.add(msg)
            db.session.commit()
            
            update_integration_health(company_id, 'z_api')
            # Return UUID to allow frontend to update the correct thread
            return {'success': True, 'msg_id': msg.id, 'contact_uuid': contact.uuid}
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
