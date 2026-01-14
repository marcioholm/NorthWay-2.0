from app import create_app
from models import db, WhatsAppMessage, Lead, Client, User

app = create_app()

with app.app_context():
    print("--- START DEBUG ---")
    try:
        # Simulate current_user.company_id = 1
        company_id = 1
        
        print(f"Querying for Company {company_id}")
        all_msgs = WhatsAppMessage.query.filter_by(company_id=company_id)\
            .order_by(WhatsAppMessage.created_at.desc())\
            .limit(10).all()
            
        print(f"Found {len(all_msgs)} messages")
        
        conversations_map = {}
        for msg in all_msgs:
            print(f"Msg: {msg.id} - Lead: {msg.lead_id} / Client: {msg.client_id}")
            
            key = None
            if msg.lead_id: key = f"lead_{msg.lead_id}"
            elif msg.client_id: key = f"client_{msg.client_id}"
            
            if not key: 
                print("Skipping (no target)")
                continue
                
            if key in conversations_map: continue
            
            # Fetch names
            name = "Unknown"
            if msg.lead_id:
                l = Lead.query.get(msg.lead_id)
                if l: name = l.name
            elif msg.client_id:
                c = Client.query.get(msg.client_id)
                if c: name = c.name
                
            conversations_map[key] = {'name': name}
            
        print("Conversations:", conversations_map)
        print("--- SUCCESS ---")
        
    except Exception as e:
        print(f"--- ERROR: {e} ---")
        import traceback
        traceback.print_exc()
