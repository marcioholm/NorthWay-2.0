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
    try:
        if request.method == 'OPTIONS': return
        
        # Allow Webhook and Public Diagnostic routes
        if any(x in request.path for x in ['webhooks', 'ping', 'test-loopback', 'debug-schema']):
            return
            
        # Check Feature Flag
        if current_user and current_user.is_authenticated:
            # Use a more robust check for company_id directly to avoid lazy-load crashes
            if not current_user.company_id:
                return # Allow users without company to reach basic dashboards or error pages
                
            company = getattr(current_user, 'company', None)
            # If company is not loaded, just skip the check to avoid blocking the user with a 500
            if company and hasattr(company, 'has_feature'):
                if not company.has_feature('whatsapp'):
                    if request.is_json: # API
                        return jsonify({'error': 'Feature Disabled for this Company'}), 403
                    else: # UI
                        flash('Módulo WhatsApp desativado pela administração.', 'error')
                        return redirect(url_for('dashboard.home'))
    except Exception as e:
        current_app.logger.error(f"WhatsApp Feature Check Error: {e}")
        # Fail open: don't break the whole app if feature check fails
        return

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
        
    # Slugify instance name to be URL and ID safe
    instance_name = instance_name.lower().replace(' ', '-').replace('_', '-')
    
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        instance = WhatsappInstance(company_id=current_user.company_id, instance_name=instance_name)
        db.session.add(instance)
    else:
        # If updating, let's keep the name consistent or update it
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
        # Try a flexible search if direct match fails (e.g. spaces vs hyphens)
        alt_name = instance_name.replace(' ', '-').lower()
        instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id, instance_name=alt_name).first()
        
    if not instance:
        return jsonify({
            'error': 'Instance not found in DB',
            'debug': f"Searched for: {instance_name}"
        }), 404
        
    try:
        res = EvolutionService.get_connection_status(instance_name)
        # Evolution status check
        state = res.get('instance', {}).get('state', 'disconnected').lower()
        
        # AUTO-CONFIG WEBHOOK: If connected, ensure the webhook is set to our live endpoint
        if state == 'open':
            try:
                # Use current_app.config['SERVER_NAME'] or hardcoded for now since it's production
                # The correct URL is needed. We can use the request.host_url
                webhook_url = f"{request.host_url.rstrip('/')}/api/webhooks/evolution"
                EvolutionService.configure_webhook(instance_name, webhook_url)
                current_app.logger.info(f"Auto-configured webhook for {instance_name} to {webhook_url}")
            except Exception as e:
                current_app.logger.error(f"Failed auto-webhook config: {e}")
        
        qr_code_base64 = None
        debug_info = None
        
        if state in ['connecting', 'close', 'disconnected']:
            # For v2, let's try POST connect first
            qr_res = EvolutionService.connect_instance(instance_name)
            
            # If 404 (Not Found), the server might be out of sync
            if isinstance(qr_res, dict) and qr_res.get('status') == 404:
                # AUTO-SYNC: delete and recreate on server
                EvolutionService.delete_instance(instance_name)
                import time
                time.sleep(1) # Give the server a breather
                qr_res = EvolutionService.create_instance(instance_name)
            
            # Helper to find 'base64' in any nested dictionary
            def find_base64(data):
                if isinstance(data, dict):
                    if 'base64' in data and data['base64']:
                        return data['base64']
                    for v in data.values():
                        res = find_base64(v)
                        if res: return res
                elif isinstance(data, list):
                    for item in data:
                        res = find_base64(item)
                        if res: return res
                return None

            qr_code_base64 = find_base64(qr_res)
            
            # If still nothing, try GET as final fallback
            if not qr_code_base64:
                qr_res_get = EvolutionService.get_qrcode(instance_name)
                qr_code_base64 = find_base64(qr_res_get)
                if not qr_code_base64:
                    debug_info = f"V2.3.7 - State: {state} | POST Res: {str(qr_res)[:60]} | GET Res: {str(qr_res_get)[:60]}"
            
            # Ensure it has the data URI prefix
            if qr_code_base64 and isinstance(qr_code_base64, str) and not qr_code_base64.startswith('data:'):
                qr_code_base64 = f"data:image/png;base64,{qr_code_base64}"
            
        instance.status = state
        db.session.commit()
        
        return jsonify({
            'status': state,
            'qr_code_base64': qr_code_base64,
            'debug': debug_info
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- VIEWS ---
@whatsapp_bp.route('/whatsapp')
@login_required
def inbox():
    try:
        from models import Pipeline, User
        # Optimize queries with specific IDs
        pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
        users = User.query.filter_by(company_id=current_user.company_id).all()
        return render_template('whatsapp_inbox.html', pipelines=pipelines, users=users)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        current_app.logger.error(f"WhatsApp Inbox Error: {e}\n{error_trace}")
        
        # If it's a 500, let's at least show the company ID for debugging
        return render_template('500.html', error=f"Erro ao carregar o chat. (Company: {current_user.company_id})"), 500

@whatsapp_bp.route('/whatsapp/groups')
@login_required
def groups():
    return render_template('whatsapp_groups.html')
@whatsapp_bp.route('/api/whatsapp/debug-schema')
@login_required
def debug_schema():
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    results = {}
    for table in ['whatsapp_instances', 'whatsapp_conversations', 'whatsapp_messages']:
        try:
            results[table] = [c['name'] for c in inspector.get_columns(table)]
        except Exception as e:
            results[table] = f"ERROR: {str(e)}"
    # Also list instances for name matching verification
    instances = []
    try:
        raw_instances = WhatsappInstance.query.all()
        instances = [{'id': i.id, 'name': i.instance_name, 'company_id': i.company_id} for i in raw_instances]
    except Exception as e:
        instances = f"ERROR: {str(e)}"

    return jsonify({
        'version': 'v2.4.0-FINAL-FIX',
        'tables': results,
        'instances': instances,
        'user_company_id': current_user.company_id
    })

@whatsapp_bp.route('/api/whatsapp/ping')
def ping_whatsapp():
    return jsonify({'status': 'alive', 'version': 'v2.4.1-DEBUG'})

@whatsapp_bp.route('/api/whatsapp/test-loopback')
@login_required
def test_loopback():
    """Simulates an incoming message to test internal logic (DB save, NORA forward)"""
    import requests
    # Find first instance for this company
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({"error": "No instance found for your company"}), 404
        
    # Standard Evolution v2 payload for message.upsert
    webhook_url = f"{request.host_url.rstrip('/')}/api/webhooks/evolution"
    payload = {
        "event": "messages.upsert",
        "instance": instance.instance_name,
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": f"TEST-{int(datetime.utcnow().timestamp())}"
            },
            "pushName": "Antigravity Test",
            "message": {
                "conversation": "Teste de Loopback - NorthWay CRM"
            },
            "messageTimestamp": int(datetime.utcnow().timestamp())
        }
    }
    
    try:
        # We hit our own endpoint (publicly available on Vercel)
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return jsonify({
            "test": "loopback",
            "target_url": webhook_url,
            "payload_sent": payload,
            "response_status": resp.status_code,
            "response_body": resp.json() if resp.status_code == 200 else resp.text
        })
    except Exception as e:
        return jsonify({"error": str(e), "webhook_url": webhook_url}), 500

@whatsapp_bp.route('/api/whatsapp/sync-webhook')
@login_required
def sync_webhook():
    """Forces Evolution API to use the correct Webhook URL for the active instance"""
    from services.evolution_service import EvolutionService
    # Find first instance for this company
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({"error": "No instance found"}), 404
        
    # The URL MUST be the public one
    webhook_url = f"https://{request.host}/api/webhooks/evolution"
    
    try:
        result = EvolutionService.configure_webhook(instance.instance_name, webhook_url)
        return jsonify({
            "status": "success",
            "instance": instance.instance_name,
            "new_url": webhook_url,
            "evolution_response": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@whatsapp_bp.route('/api/whatsapp/sync-messages', methods=['POST'])
@login_required
def sync_messages():
    """Busca chats e mensagens recentes da Evolution API e salva no banco."""
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({'error': 'Nenhuma instância WhatsApp configurada'}), 404

    company_id = current_user.company_id
    stats = {'chats_found': 0, 'chats_saved': 0, 'messages_saved': 0, 'errors': []}

    try:
        chats_data = EvolutionService.fetch_chats(instance.instance_name)
    except Exception as e:
        return jsonify({'error': f'Falha ao buscar chats da Evolution API: {str(e)}'}), 500

    # Evolution v2 pode retornar lista direta ou objeto com chave 'chats'
    chats = chats_data if isinstance(chats_data, list) else chats_data.get('chats', [])
    stats['chats_found'] = len(chats)

    # Pré-carrega leads e clientes da empresa indexados por telefone (normalizado)
    def normalize_phone(p):
        if not p: return ''
        return ''.join(c for c in str(p) if c.isdigit())[-11:]  # últimos 11 dígitos

    leads_by_phone = {normalize_phone(l.phone): l for l in Lead.query.filter_by(company_id=company_id).all() if l.phone}
    clients_by_phone = {normalize_phone(c.phone): c for c in Client.query.filter_by(company_id=company_id).all() if c.phone}

    for chat in chats[:50]:  # Limita a 50 chats para evitar timeout no Vercel
        try:
            # Usar remoteJid (JID real), não 'id' (ID interno da Evolution)
            remote_jid = chat.get('remoteJid')
            if not remote_jid:
                continue

            # Para contatos LID (@lid), o telefone real está em lastMessage.key.remoteJidAlt
            last_msg = chat.get('lastMessage') or {}
            last_key = last_msg.get('key') or {}
            alt_jid = last_key.get('remoteJidAlt')  # Ex: "554396977498@s.whatsapp.net"

            # JID para busca de telefone: preferir @s.whatsapp.net sobre @lid
            phone_jid = alt_jid if (alt_jid and '@s.whatsapp.net' in alt_jid) else remote_jid
            phone_digits = normalize_phone(phone_jid.split('@')[0])

            # Nome: chat.pushName para grupos, lastMessage.pushName para contatos individuais
            wa_name = chat.get('pushName') or last_msg.get('pushName') or ''

            crm_lead = leads_by_phone.get(phone_digits)
            crm_client = clients_by_phone.get(phone_digits)
            crm_name = (crm_lead.name if crm_lead else None) or (crm_client.name if crm_client else None)
            chat_name = crm_name or wa_name or phone_jid.split('@')[0]

            # Foto: campo correto é profilePicUrl
            pic_url = chat.get('profilePicUrl') or chat.get('profilePictureUrl') or chat.get('imgUrl')

            # Upsert conversation
            conv = WhatsappConversation.query.filter_by(
                instance_id=instance.id, remote_jid=remote_jid
            ).first()

            if not conv:
                conv = WhatsappConversation(
                    company_id=company_id,
                    instance_id=instance.id,
                    remote_jid=remote_jid,
                    name=chat_name,
                    profile_pic_url=pic_url,
                    lead_id=crm_lead.id if crm_lead else None,
                    client_id=crm_client.id if crm_client else None,
                )
                db.session.add(conv)
                db.session.flush()
                stats['chats_saved'] += 1
            else:
                # Atualiza nome e foto se melhorou
                if crm_name and conv.name != crm_name:
                    conv.name = crm_name
                elif not conv.name or conv.name == remote_jid.split('@')[0]:
                    conv.name = chat_name
                if pic_url and not conv.profile_pic_url:
                    conv.profile_pic_url = pic_url
                if crm_lead and not conv.lead_id:
                    conv.lead_id = crm_lead.id
                if crm_client and not conv.client_id:
                    conv.client_id = crm_client.id

            # Busca foto do perfil se ainda não tem (apenas grupos individuais, não @g.us)
            if not conv.profile_pic_url and '@g.us' not in remote_jid:
                try:
                    fetched_pic = EvolutionService.fetch_profile_pic(instance.instance_name, remote_jid)
                    if fetched_pic:
                        conv.profile_pic_url = fetched_pic
                except Exception:
                    pass

            # Busca mensagens recentes
            try:
                msgs_data = EvolutionService.fetch_messages(instance.instance_name, remote_jid, limit=30)
                messages = msgs_data if isinstance(msgs_data, list) else msgs_data.get('messages', [])

                for msg in messages:
                    try:
                        key = msg.get('key', {})
                        message_id = key.get('id')
                        if not message_id:
                            continue

                        # Evita duplicatas
                        if WhatsappMessage.query.filter_by(message_id=message_id).first():
                            continue

                        is_from_me = key.get('fromMe', False)
                        direction = 'out' if is_from_me else 'in'
                        push_name = msg.get('pushName') or chat_name

                        msg_object = msg.get('message', {})
                        content = ''
                        msg_type = 'text'
                        media_url = None

                        if 'conversation' in msg_object:
                            content = msg_object['conversation']
                        elif 'extendedTextMessage' in msg_object:
                            content = msg_object['extendedTextMessage'].get('text', '')
                        elif 'imageMessage' in msg_object:
                            msg_type = 'image'
                            content = msg_object['imageMessage'].get('caption', '[Imagem]')
                        elif 'audioMessage' in msg_object:
                            msg_type = 'audio'
                            content = '[Áudio]'
                        elif 'videoMessage' in msg_object:
                            msg_type = 'video'
                            content = '[Vídeo]'
                        elif 'documentMessage' in msg_object:
                            msg_type = 'document'
                            content = msg_object['documentMessage'].get('title', '[Documento]')

                        if not content:
                            content = '[Mensagem]'

                        timestamp = msg.get('messageTimestamp')
                        dt_timestamp = datetime.utcfromtimestamp(int(timestamp)) if timestamp else datetime.utcnow()

                        new_msg = WhatsappMessage(
                            company_id=company_id,
                            conversation_id=conv.id,
                            message_id=message_id,
                            direction=direction,
                            type=msg_type,
                            content=content,
                            media_url=media_url,
                            status='read',
                            timestamp=dt_timestamp,
                            sender_name=push_name if direction == 'in' else 'Você'
                        )
                        db.session.add(new_msg)
                        stats['messages_saved'] += 1

                        # Atualiza preview da conversa com a msg mais recente
                        if not conv.last_message_preview or dt_timestamp > (conv.last_message_at or datetime.min):
                            conv.last_message_preview = content[:255]
                            conv.last_message_at = dt_timestamp
                            conv.last_message_dir = direction

                    except Exception as msg_e:
                        stats['errors'].append(f'msg {message_id}: {str(msg_e)}')

            except Exception as fetch_e:
                stats['errors'].append(f'fetch msgs {remote_jid}: {str(fetch_e)}')

        except Exception as chat_e:
            stats['errors'].append(f'chat: {str(chat_e)}')

    try:
        db.session.commit()
    except Exception as commit_e:
        db.session.rollback()
        return jsonify({'error': f'Erro ao salvar no banco: {str(commit_e)}'}), 500

    return jsonify({
        'success': True,
        'stats': stats,
        'message': f'{stats["chats_saved"]} conversas e {stats["messages_saved"]} mensagens sincronizadas.'
    })


@whatsapp_bp.route('/api/whatsapp/debug-chats')
@login_required
def debug_chats():
    """Mostra os primeiros 3 chats crus da Evolution API para debug de nomes/campos."""
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({'error': 'Sem instância'}), 404
    try:
        chats_data = EvolutionService.fetch_chats(instance.instance_name)
        chats = chats_data if isinstance(chats_data, list) else chats_data.get('chats', [])
        sample = chats[:3]
        return jsonify({
            'total': len(chats),
            'sample': sample,
            'raw_type': type(chats_data).__name__,
            'raw_keys': list(chats_data.keys()) if isinstance(chats_data, dict) else 'list'
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@whatsapp_bp.route('/api/whatsapp/debug-messages')
@login_required
def debug_messages():
    """Mostra mensagens cruas da Evolution API para o primeiro chat individual encontrado."""
    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({'error': 'Sem instância'}), 404
    try:
        chats_data = EvolutionService.fetch_chats(instance.instance_name)
        chats = chats_data if isinstance(chats_data, list) else chats_data.get('chats', [])
        # Pega o primeiro chat individual
        target = next((c for c in chats if '@g.us' not in (c.get('remoteJid') or '')), chats[0] if chats else None)
        if not target:
            return jsonify({'error': 'Nenhum chat encontrado'})

        remote_jid = target.get('remoteJid')

        # Chama diretamente sem wrapper para ver a resposta crua
        import requests as req
        url = f"{EvolutionService.get_api_url()}/chat/findMessages/{instance.instance_name}"
        payload = {"where": {"remoteJid": remote_jid}, "limit": 3}
        try:
            r = req.post(url, headers=EvolutionService.get_headers(), json=payload, timeout=30)
            raw = r.json()
        except Exception as e:
            import traceback
            return jsonify({'jid_used': remote_jid, 'error': str(e), 'trace': traceback.format_exc()})

        return jsonify({
            'jid_used': remote_jid,
            'status': r.status_code,
            'raw_type': type(raw).__name__,
            'raw_keys': list(raw.keys()) if isinstance(raw, dict) else 'list',
            'total_items': len(raw) if isinstance(raw, list) else None,
            'sample': raw[:3] if isinstance(raw, list) else raw
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@whatsapp_bp.route('/api/whatsapp/sync-profile', methods=['POST'])
@login_required
def sync_profile():
    from urllib.parse import unquote
    data = request.json or {}
    chat_type = data.get('type', 'atendimento')
    contact_id = unquote(str(data.get('id', '')))

    if not contact_id:
        return jsonify({'success': False, 'message': 'ID não informado'}), 400

    instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
    if not instance:
        return jsonify({'success': False, 'message': 'Nenhuma instância configurada'}), 404

    # Resolve remote_jid
    remote_jid = contact_id
    if chat_type == 'lead':
        obj = Lead.query.get(contact_id)
        if obj:
            remote_jid = f"{obj.phone}@s.whatsapp.net" if obj.phone and '@' not in obj.phone else obj.phone
    elif chat_type == 'client':
        obj = Client.query.get(contact_id)
        if obj:
            remote_jid = f"{obj.phone}@s.whatsapp.net" if obj.phone and '@' not in obj.phone else obj.phone
    elif '@' not in remote_jid:
        remote_jid = f"{remote_jid}@s.whatsapp.net"

    try:
        pic_url = EvolutionService.fetch_profile_pic(instance.instance_name, remote_jid)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

    if not pic_url:
        return jsonify({'success': False, 'message': 'Foto não encontrada no WhatsApp'})

    # Persiste na conversa
    conv = WhatsappConversation.query.filter_by(instance_id=instance.id, remote_jid=remote_jid).first()
    if conv:
        conv.profile_pic_url = pic_url
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({'success': True, 'url': pic_url})


@whatsapp_bp.route('/api/whatsapp/inspect-webhook')
def inspect_webhook():
    try:
        from northway_crm.utils.webhook_logger import get_last_events
        events = get_last_events()
        return jsonify({
            'last_events': events if events else "No events received yet",
            'server_time': datetime.utcnow().isoformat()
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500

@whatsapp_bp.route('/api/whatsapp/conversations')
@login_required
def get_conversations():
    try:
        instance = WhatsappInstance.query.filter_by(company_id=current_user.company_id).first()
        if not instance:
            return jsonify({'conversations': [], 'debug': 'No instance found for this company'})
            
        try:
            # Query conversations, but handle potential missing columns gracefully
            # We use a safer query first to check if the table exists
            conversations = WhatsappConversation.query.filter_by(instance_id=instance.id).order_by(WhatsappConversation.updated_at.desc()).all()
        except Exception as query_e:
            current_app.logger.error(f"Inbox Query Failure: {query_e}")
            return jsonify({
                'conversations': [],
                 'debug_error': f"Query Error: {str(query_e)}",
                 'repair_url': f'/sys-admin/sync-db?secret=northway_sync_2026'
            }), 200 
            
        data = []
        for c in conversations:
            try:
                # Use getattr for everything to be safe
                remote_jid = getattr(c, 'remote_jid', 'unknown')
                c_id = str(getattr(c, 'id', ''))
                
                # Determine contact type and ID
                contact_type = 'atendimento'
                contact_id = remote_jid
                
                if getattr(c, 'lead_id', None):
                    contact_type = 'lead'
                    contact_id = str(c.lead_id)
                elif getattr(c, 'client_id', None):
                    contact_type = 'client'
                    contact_id = str(c.client_id)
                    
                # Safe date formatting
                last_at = getattr(c, 'updated_at', None)
                if last_at and hasattr(last_at, 'isoformat'):
                    last_at = last_at.isoformat()
                else:
                    last_at = None
                
                # Prioriza nome do CRM (lead/cliente) sobre o nome salvo na conversa
                display_name = getattr(c, 'name', '') or ''
                if contact_type == 'lead' and getattr(c, 'lead_id', None):
                    try:
                        lead_obj = Lead.query.get(c.lead_id)
                        if lead_obj and lead_obj.name:
                            display_name = lead_obj.name
                    except Exception:
                        pass
                elif contact_type == 'client' and getattr(c, 'client_id', None):
                    try:
                        client_obj = Client.query.get(c.client_id)
                        if client_obj and client_obj.name:
                            display_name = client_obj.name
                    except Exception:
                        pass
                if not display_name:
                    display_name = remote_jid.split('@')[0] if '@' in str(remote_jid) else 'Desconhecido'

                data.append({
                    'id': contact_id,
                    'type': contact_type,
                    'phone': remote_jid,
                    'name': display_name,
                    'profile_pic_url': getattr(c, 'profile_pic_url', None),
                    'last_message_content': getattr(c, 'last_message_preview', ''),
                    'last_message_at': last_at,
                    'last_message_dir': getattr(c, 'last_message_dir', 'in'),
                    'last_message_status': getattr(c, 'last_message_status', 'sent'),
                    'unread_count': getattr(c, 'unread_count', 0),
                    'is_group': "@g.us" in str(remote_jid)
                })
            except Exception as item_e:
                current_app.logger.warning(f"Error processing conversation item: {item_e}")
                continue
            
        return jsonify({'conversations': data})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Inbox Fatal Error: {e}\n{error_details}")
        # Return 200 with error info so the UI can show the ACTUAL cause
        return jsonify({
            'error': f"BACKEND_ERROR: {str(e)}", 
            'conversations': [], 
            'fatal': True,
            'stack': error_details,
            'repair_message': 'Por favor, execute o link de sincronização para garantir que o banco de dados está atualizado.',
            'repair_url': '/sys-admin/sync-db?secret=northway_sync_2026'
        }), 200

@whatsapp_bp.route('/api/whatsapp/<string:type>/<string:contact_id>/messages', methods=['GET'])
@whatsapp_bp.route('/api/whatsapp/lead/<int:id>/messages', methods=['GET'], endpoint='get_lead_messages_legacy')
@whatsapp_bp.route('/api/whatsapp/client/<int:id>/messages', methods=['GET'], endpoint='get_client_messages_legacy')
@login_required
def get_history(type='lead', contact_id=None, id=None):
    from urllib.parse import unquote
    contact_id = unquote(contact_id) if contact_id else id

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
    # Fallback: Evolution v2 may store conversation with @lid JID — look up by lead_id/client_id
    if not conv and type == 'lead':
        conv = WhatsappConversation.query.filter_by(instance_id=instance.id, lead_id=contact_id).first()
    elif not conv and type == 'client':
        conv = WhatsappConversation.query.filter_by(instance_id=instance.id, client_id=contact_id).first()
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
