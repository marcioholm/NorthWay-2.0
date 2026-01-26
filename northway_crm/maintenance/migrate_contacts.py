from flask import current_app
from sqlalchemy import text
from app import db 
import uuid
import re
from datetime import datetime

# Logic mirror from WhatsAppService
def normalize_phone(phone):
    if not phone: return None
    clean = re.sub(r'\D', '', str(phone))
    if not clean: return None
    if len(clean) in [10, 11]:
        clean = '55' + clean
    return clean

def migrate_data():
    print("Starting data migration via SQLAlchemy...")
    connection = db.engine.connect()
    trans = connection.begin()
    
    try:
        # 1. Fetch all Leads and Clients
        leads = connection.execute(text("SELECT id, name, phone, company_id FROM lead")).mappings().all()
        clients = connection.execute(text("SELECT id, name, phone, company_id FROM client")).mappings().all()
        
        print(f"Found {len(leads)} leads and {len(clients)} clients.")
        
        phone_map = {} # normalized_phone -> contact_uuid
        
        # 2a. Process Clients FIRST (Priority)
        for c in clients:
            norm = normalize_phone(c['phone'])
            if not norm: continue
            
            if norm not in phone_map:
                c_uuid = str(uuid.uuid4())
                # Create Contact
                connection.execute(
                    text("INSERT INTO contact (uuid, company_id, phone, created_at) VALUES (:uuid, :cid, :phone, :now)"),
                    {"uuid": c_uuid, "cid": c['company_id'], "phone": norm, "now": datetime.utcnow()}
                )
                phone_map[norm] = c_uuid
                
            # Update Client
            connection.execute(
                text("UPDATE client SET contact_uuid = :cuuid WHERE id = :id"),
                {"cuuid": phone_map[norm], "id": c['id']}
            )

        # 2b. Process Leads
        for l in leads:
            norm = normalize_phone(l['phone'])
            if not norm: continue
            
            if norm not in phone_map:
                c_uuid = str(uuid.uuid4())
                connection.execute(
                    text("INSERT INTO contact (uuid, company_id, phone, created_at) VALUES (:uuid, :cid, :phone, :now)"),
                    {"uuid": c_uuid, "cid": l['company_id'], "phone": norm, "now": datetime.utcnow()}
                )
                phone_map[norm] = c_uuid
            
            connection.execute(
                text("UPDATE lead SET contact_uuid = :cuuid WHERE id = :id"),
                {"cuuid": phone_map[norm], "id": l['id']}
            )
            
        print("Leads and Clients linked.")

        # 3. Migrate WhatsApp Messages
        msgs = connection.execute(text("SELECT id, phone, lead_id, client_id, company_id FROM whats_app_message")).mappings().all()
        print(f"Migrating {len(msgs)} messages...")
        
        count = 0
        for m in msgs:
            c_uuid = None
            
            # Helper to fetch single value
            def get_uuid_from_table(table, id_val):
                res = connection.execute(text(f"SELECT contact_uuid FROM {table} WHERE id = :id"), {"id": id_val}).scalar()
                return res

            # Try Linked Client
            if m['client_id']:
                c_uuid = get_uuid_from_table('client', m['client_id'])
                
            # Try Linked Lead
            if not c_uuid and m['lead_id']:
                c_uuid = get_uuid_from_table('lead', m['lead_id'])
                
            # Try Phone
            if not c_uuid and m['phone']:
                norm = normalize_phone(m['phone'])
                if norm and norm in phone_map:
                    c_uuid = phone_map[norm]
                elif norm:
                    # Create Unknown Contact
                    c_uuid = str(uuid.uuid4())
                    connection.execute(
                        text("INSERT INTO contact (uuid, company_id, phone, created_at) VALUES (:uuid, :cid, :phone, :now)"),
                        {"uuid": c_uuid, "cid": m['company_id'], "phone": norm, "now": datetime.utcnow()}
                    )
                    phone_map[norm] = c_uuid
            
            if c_uuid:
                connection.execute(
                    text("UPDATE whats_app_message SET contact_uuid = :cuuid WHERE id = :id"),
                    {"cuuid": c_uuid, "id": m['id']}
                )
                count += 1
                
        print(f"Updated {count} messages.")
        trans.commit()
        print("Migration complete.")
        
    except Exception as e:
        trans.rollback()
        print(f"Migration failed: {e}")
        raise e
    finally:
        connection.close()

if __name__ == '__main__':
    from app import app
    with app.app_context():
        migrate_data()
