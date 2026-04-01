import secrets
import hashlib
import json
import uuid
import requests
import threading
from datetime import datetime
from flask import current_app, request, g
from models import db, IntegrationApiKey, IntegrationWebhook, IntegrationLog, get_now_br

class IntegrationsService:
    @staticmethod
    def generate_api_key(company_id, name, scopes=None):
        """
        Generates a new API base64 key, hashes it, and stores it.
        Returns the raw key (plain) only once.
        """
        raw_key = f"nw_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:10]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        new_key = IntegrationApiKey(
            company_id=company_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes or [],
            status='active'
        )
        db.session.add(new_key)
        db.session.commit()
        
        return raw_key

    @staticmethod
    def verify_api_key(raw_key):
        """
        Verifies a raw API key against the database.
        Returns the IntegrationApiKey object if valid, else None.
        """
        if not raw_key:
            return None
            
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = IntegrationApiKey.query.filter_by(key_hash=key_hash, status='active').first()
        
        if api_key:
            # Update last used
            api_key.last_used_at = get_now_br()
            db.session.commit()
            return api_key
            
        return None

    @staticmethod
    def log_activity(company_id, type, endpoint, method, status_code=None, 
                     req_payload=None, res_payload=None, error=None, 
                     execution_time=None, request_id=None):
        """Logs an integration request/response for auditing."""
        try:
            # Mask sensitive data in payloads if needed
            def mask_payload(p):
                if not p: return p
                if isinstance(p, str):
                    try: p = json.loads(p)
                    except: return p
                
                sensitive_keys = ['api_key', 'password', 'secret', 'token']
                if isinstance(p, dict):
                    for k in sensitive_keys:
                        if k in p: p[k] = '********'
                return p

            log = IntegrationLog(
                company_id=company_id,
                type=type,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                request_payload=mask_payload(req_payload),
                response_payload=mask_payload(res_payload),
                error_message=str(error) if error else None,
                request_id=request_id or str(uuid.uuid4()),
                execution_time_ms=execution_time
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Failed to log integration activity: {e}")
            db.session.rollback()

    @staticmethod
    def dispatch_webhooks(company_id, event_name, payload):
        """
        Finds all active webhooks for a company and event,
        and dispatches them in the background.
        """
        # Run in a separate thread to avoid blocking the main request
        thread = threading.Thread(
            target=IntegrationsService._dispatch_webhooks_sync,
            args=(company_id, event_name, payload)
        )
        thread.start()

    @staticmethod
    def _dispatch_webhooks_sync(company_id, event_name, payload):
        """Synchronous part of webhook dispatch (run in thread)."""
        # Need app context for DB access in thread
        # Note: This requires the caller to pass the app or we use a global app reference
        # For simplicity in Flask, we can use current_app._get_current_object() if called correctly
        # But since we are in a thread, we'll need to create a new app context.
        from northway_crm.app import create_app
        app = create_app()
        
        with app.app_context():
            webhooks = IntegrationWebhook.query.filter_by(
                company_id=company_id, 
                status='active'
            ).all()

            for webhook in webhooks:
                # Check if event is subscribed
                subscribed_events = webhook.events or []
                if event_name not in subscribed_events and '*' not in subscribed_events:
                    continue

                IntegrationsService._send_single_webhook(webhook, event_name, payload)

    @staticmethod
    def _send_single_webhook(webhook, event_name, payload):
        import hmac
        import hashlib
        import time

        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Prepare Payload
        body = {
            "event": event_name,
            "timestamp": datetime.utcnow().isoformat(),
            "company_id": webhook.company_id,
            "request_id": request_id,
            "data": payload
        }
        body_json = json.dumps(body)

        # Generate Signature
        signature = hmac.new(
            webhook.secret.encode(),
            body_json.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-NorthWay-Event": event_name,
            "X-NorthWay-Signature": signature,
            "X-NorthWay-Request-Id": request_id,
            "User-Agent": "NorthWay-Webhook-Dispatcher/1.0"
        }

        success = False
        status_code = None
        error_msg = None
        response_text = None

        try:
            res = requests.post(webhook.url, data=body_json, headers=headers, timeout=10)
            status_code = res.status_code
            response_text = res.text[:2000] # Cap response size
            if 200 <= status_code < 300:
                success = True
        except Exception as e:
            error_msg = str(e)

        execution_time = int((time.time() - start_time) * 1000)

        # Log Webhook Attempt
        IntegrationsService.log_activity(
            company_id=webhook.company_id,
            type='outbound_webhook',
            endpoint=webhook.url,
            method='POST',
            status_code=status_code,
            req_payload=body,
            res_payload=response_text,
            error=error_msg,
            execution_time=execution_time,
            request_id=request_id
        )
