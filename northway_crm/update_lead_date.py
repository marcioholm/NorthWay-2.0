from app import create_app, db
from models import Lead, LEAD_STATUS_LOST
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    # Find a target lead
    lead = Lead.query.filter(Lead.name.like('Gabriel%')).first()
    if not lead:
        lead = Lead.query.first()
    
    if lead:
        print(f"Updating lead: {lead.name}")
        lead.status = 'lost' # Match models.py LEAD_STATUS_LOST
        fake_date = datetime.now() - timedelta(days=91)
        lead.created_at = fake_date
        # Also update interactions if any to be old? 
        # Logical check in app.py used created_at for MVP.
        
        db.session.commit()
        print(f"Lead updated. Status: {lead.status}, Created At: {lead.created_at}")
    else:
        print("No lead found to update.")
