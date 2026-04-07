from datetime import datetime

# Global list to store last webhook events in memory for live debugging
# This avoids circular imports between blueprints
LAST_EVENTS = []

def log_webhook_event(data):
    """Helper to store last events in memory for live debugging"""
    try:
        event_summary = {
            'time': datetime.utcnow().isoformat(),
            'event': data.get('event'),
            'instance': data.get('instance'),
            'status': 'received',
            'data_keys': list(data.keys())
        }
        LAST_EVENTS.append(event_summary)
        # Keep only last 20 events
        if len(LAST_EVENTS) > 20:
            LAST_EVENTS.pop(0)
    except Exception as e:
        print(f"Error logging webhook event: {e}")

def get_last_events():
    return LAST_EVENTS
