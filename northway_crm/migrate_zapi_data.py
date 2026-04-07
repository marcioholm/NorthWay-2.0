import uuid
from app import app
from models import db, WhatsappInstance, WhatsappConversation, WhatsappMessage, Company
from sqlalchemy import text

def run_migration():
    with app.app_context():
        # Read old messages
        result = db.session.execute(text("SELECT * FROM whats_app_message;")).fetchall()
        print(f"Found {len(result)} legacy WhatsApp messages to migrate.")
        
        # Get column names
        cols = db.session.execute(text("PRAGMA table_info(whats_app_message);")).fetchall()
        col_names = [c[1] for c in cols]
        
        migrated_count = 0
        company_instances = {}
        conversations_dict = {}
        
        for row in result:
            msg = dict(zip(col_names, row))
            company_id = msg.get('company_id')
            if not company_id:
                continue
                
            # Find or create instance
            if company_id not in company_instances:
                instance = WhatsappInstance.query.filter_by(company_id=company_id, instance_name="Z-API Legacy").first()
                if not instance:
                    instance = WhatsappInstance(
                        company_id=company_id,
                        instance_name="Z-API Legacy",
                        status="disconnected"
                    )
                    db.session.add(instance)
                    db.session.commit()
                company_instances[company_id] = instance.id
                
            instance_id = company_instances[company_id]
            
            # Determine logic for remote_jid (phone)
            phone = msg.get('phone')
            if not phone:
                phone = f"unknown_{msg.get('id')}@s.whatsapp.net"
            elif "@" not in phone:
                phone = f"{phone}@s.whatsapp.net"
                
            # Find or create conversation
            lead_id = msg.get('lead_id')
            client_id = msg.get('client_id')
            
            conv_key = f"{instance_id}_{phone}"
            if conv_key not in conversations_dict:
                conv = WhatsappConversation.query.filter_by(instance_id=instance_id, remote_jid=phone).first()
                if not conv:
                    conv = WhatsappConversation(
                        company_id=company_id,
                        instance_id=instance_id,
                        remote_jid=phone,
                        name=msg.get('sender_name') or phone.split('@')[0],
                        profile_pic_url=msg.get('profile_pic_url'),
                        lead_id=lead_id,
                        client_id=client_id,
                        last_message_preview=msg.get('content')
                    )
                    db.session.add(conv)
                    db.session.commit()
                conversations_dict[conv_key] = conv.id
            else:
                # Update lead/client association if it wasn't there before
                # (Optional optimization: if we need to sync lead_id / client_id)
                pass
                
            conv_id = conversations_dict[conv_key]
            
            # Insert message
            new_msg = WhatsappMessage(
                company_id=company_id,
                conversation_id=conv_id,
                message_id=msg.get('external_id') or str(uuid.uuid4()),
                direction=msg.get('direction', 'out'),
                type=msg.get('type', 'text'),
                content=msg.get('content'),
                media_url=msg.get('attachment_url'),
                status=msg.get('status', 'sent'),
                timestamp=msg.get('created_at'),
                created_at=msg.get('created_at'),
                sender_name=msg.get('sender_name')
            )
            # prevent duplicate message ids
            try:
                db.session.add(new_msg)
                db.session.commit()
                migrated_count += 1
            except Exception as e:
                db.session.rollback()
                # If unique constraint fails, pass
                pass
                
        print(f"Successfully migrated {migrated_count} messages.")
        
if __name__ == '__main__':
    run_migration()
