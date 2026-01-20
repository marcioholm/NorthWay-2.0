import sqlite3
import os
import uuid
import re
from datetime import datetime

DB_PATH = '/Users/Marci.Holm/Applications/NorthWay-2.0/northway_crm/crm.db'

def normalize_phone(phone):
    """Mirroring the logic we will implement in WhatsAppService"""
    if not phone: return None
    clean = re.sub(r'\D', '', str(phone))
    if not clean: return None
    if len(clean) in [10, 11]:
        clean = '55' + clean
    return clean

def migrate_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Starting migration...")
    
    # 1. Fetch all Leads and Clients
    cursor.execute("SELECT id, name, phone, company_id FROM lead")
    leads = cursor.fetchall()
    
    cursor.execute("SELECT id, name, phone, company_id FROM client")
    clients = cursor.fetchall()
    
    print(f"Found {len(leads)} leads and {len(clients)} clients.")
    
    # 2. Unify by Phone
    # Map: normalized_phone -> contact_uuid
    phone_map = {}
    
    # 2a. Process Clients FIRST (Priority)
    for c in clients:
        norm = normalize_phone(c['phone'])
        if not norm: continue
        
        if norm not in phone_map:
            # Create Contact
            c_uuid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO contact (uuid, company_id, phone, created_at) VALUES (?, ?, ?, ?)",
                (c_uuid, c['company_id'], norm, datetime.utcnow())
            )
            phone_map[norm] = c_uuid
            
        # Update Client
        cursor.execute("UPDATE client SET contact_uuid = ? WHERE id = ?", (phone_map[norm], c['id']))

    # 2b. Process Leads
    for l in leads:
        norm = normalize_phone(l['phone'])
        if not norm: continue
        
        if norm not in phone_map:
            # Create Contact
            c_uuid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO contact (uuid, company_id, phone, created_at) VALUES (?, ?, ?, ?)",
                (c_uuid, l['company_id'], norm, datetime.utcnow())
            )
            phone_map[norm] = c_uuid
            
        # Update Lead
        cursor.execute("UPDATE lead SET contact_uuid = ? WHERE id = ?", (phone_map[norm], l['id']))

    print("Leads and Clients linked.")

    # 3. Migrate WhatsApp Messages
    # This is tricky because existing messages have phone, lead_id, or client_id
    # We should iterate and update based on the Best Match
    
    cursor.execute("SELECT id, phone, lead_id, client_id, company_id FROM whats_app_message")
    msgs = cursor.fetchall()
    print(f"Migrating {len(msgs)} messages...")
    
    count = 0
    for m in msgs:
        c_uuid = None
        
        # Try finding by linked Client
        if m['client_id']:
            cursor.execute("SELECT contact_uuid FROM client WHERE id = ?", (m['client_id'],))
            res = cursor.fetchone()
            if res and res['contact_uuid']: c_uuid = res['contact_uuid']
            
        # Try finding by linked Lead
        if not c_uuid and m['lead_id']:
            cursor.execute("SELECT contact_uuid FROM lead WHERE id = ?", (m['lead_id'],))
            res = cursor.fetchone()
            if res and res['contact_uuid']: c_uuid = res['contact_uuid']
            
        # Try finding by Phone
        if not c_uuid and m['phone']:
            norm = normalize_phone(m['phone'])
            if norm and norm in phone_map:
                c_uuid = phone_map[norm]
            elif norm:
                # Create 'Unknown' Contact for this phone
                c_uuid = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO contact (uuid, company_id, phone, created_at) VALUES (?, ?, ?, ?)",
                    (c_uuid, m['company_id'], norm, datetime.utcnow())
                )
                phone_map[norm] = c_uuid
        
        if c_uuid:
            cursor.execute("UPDATE whats_app_message SET contact_uuid = ? WHERE id = ?", (c_uuid, m['id']))
            count += 1
            
    print(f"Updated {count} messages.")
    
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    if os.path.exists(DB_PATH):
        migrate_data()
    else:
        print("DB not found.")
