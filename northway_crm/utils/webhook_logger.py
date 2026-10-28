import os
import json
from datetime import datetime

LOG_FILE = '/tmp/evolution_webhook_debug.json'

def log_webhook_event(data):
    """Log webhook event securely without dumping sensitive customer payload to /tmp."""
    pass

def get_last_events():
    """Read events from /tmp/ file"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None
