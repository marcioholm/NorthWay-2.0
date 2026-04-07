import os
import json
from datetime import datetime

LOG_FILE = '/tmp/evolution_webhook_debug.json'

def log_webhook_event(data):
    """Helper to store last events in a file for live debugging across serverless instances"""
    try:
        event_summary = {
            'time': datetime.utcnow().isoformat(),
            'event': data.get('event'),
            'instance': data.get('instance'),
            'status': 'received',
            'data_keys': list(data.keys())
        }
        
        events = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r') as f:
                    events = json.load(f)
            except:
                events = []
        
        events.append(event_summary)
        # Keep only last 20 events
        if len(events) > 20:
            events = events[-20:]
            
        with open(LOG_FILE, 'w') as f:
            json.dump(events, f)
            
    except Exception as e:
        print(f"Error logging webhook event: {e}")

def get_last_events():
    """Read events from /tmp/ file"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None
