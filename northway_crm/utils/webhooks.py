import os
import requests
import time
import logging
from models import db, CRMWebhookLog

logger = logging.getLogger(__name__)

def send_outbound_webhook(tenant_id, lead_id, action, webhook_url, payload, timeout=60, max_retries=3):
    """
    Sends an outbound webhook to n8n with retry logic, 60s timeout, X-Internal-API-Key header, and audit logging.
    """
    # Header with API key
    internal_key = os.environ.get('CRM_INTERNAL_API_KEY', '')
    headers = {
        'Content-Type': 'application/json',
        'X-Internal-API-Key': internal_key
    }
    
    # Also support authorization bearer token for standard APIs
    if internal_key:
        headers['Authorization'] = f'Bearer {internal_key}'
    
    status_code = None
    response_payload = None
    success = False
    error_message = None
    response = None
    
    logger.info(f"[OUTBOUND_WEBHOOK] Starting action={action} to url={webhook_url} for tenant={tenant_id}, lead={lead_id}")

    for attempt in range(max_retries):
        try:
            logger.info(f"[OUTBOUND_WEBHOOK] Attempt {attempt + 1}/{max_retries}...")
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            status_code = response.status_code
            
            # Try parsing json response
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = {"raw_text": response.text}
                
            if response.status_code in [200, 202]:
                success = True
                error_message = None
                logger.info(f"[OUTBOUND_WEBHOOK] Success on attempt {attempt + 1}!")
                break
            else:
                error_message = f"Status {response.status_code}: {response.text[:200]}"
                logger.warning(f"[OUTBOUND_WEBHOOK] Attempt {attempt + 1} failed: {error_message}")
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            status_code = None
            response_payload = None
            logger.warning(f"[OUTBOUND_WEBHOOK] Attempt {attempt + 1} raised exception: {error_message}")
            
        # Wait a small delay before retry
        if attempt < max_retries - 1:
            sleep_time = 2 ** attempt
            logger.info(f"[OUTBOUND_WEBHOOK] Sleeping {sleep_time}s before retry...")
            time.sleep(sleep_time) # Exponential backoff: 1s, 2s, 4s...
            
    # Save the log to the database
    try:
        log_entry = CRMWebhookLog(
            tenant_id=tenant_id,
            lead_id=lead_id,
            action=action,
            webhook_url=webhook_url,
            request_payload=payload,
            response_payload=response_payload,
            status_code=status_code,
            success=success,
            error_message=error_message
        )
        db.session.add(log_entry)
        db.session.commit()
        logger.info(f"[OUTBOUND_WEBHOOK] Saved log entry in crm_webhook_logs. ID={log_entry.id}")
    except Exception as db_err:
        logger.error(f"[OUTBOUND_WEBHOOK] Failed to save webhook log to DB: {db_err}", exc_info=True)
        
    return success, response_payload, error_message
