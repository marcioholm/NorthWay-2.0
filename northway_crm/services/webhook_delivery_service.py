"""Durable webhook delivery with bounded retries and a reclaimable lease."""
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from models import db, WebhookDelivery, IntegrationWebhook
from services.integrations_service import IntegrationsService


def process_deliveries(limit=5):
    processed = 0
    for _ in range(max(1, min(limit, 20))):
        now = datetime.utcnow()
        job = WebhookDelivery.query.filter(
            WebhookDelivery.status.in_(['pending', 'processing']),
            WebhookDelivery.available_at <= now
        ).order_by(WebhookDelivery.available_at).with_for_update(skip_locked=True).first()
        if not job:
            break
        if job.attempts >= 5:
            job.status = 'failed'
            db.session.commit()
            continue
        job.status = 'processing'
        job.attempts += 1
        job.available_at = now + timedelta(minutes=5)
        job_id = job.id
        db.session.commit()
        webhook = IntegrationWebhook.query.filter_by(id=job.webhook_id, company_id=job.company_id, status='active').first()
        if not webhook:
            job.status = 'cancelled'
            db.session.commit()
            continue
        try:
            success = IntegrationsService._send_single_webhook(webhook, job.event_name, job.payload,
                request_id=job.id, event_timestamp=job.created_at.isoformat())
        except Exception:
            db.session.rollback()
            success = False
        job = db.session.get(WebhookDelivery, job_id)
        job.status = 'delivered' if success else 'failed' if job.attempts >= 5 else 'pending'
        job.available_at = datetime.utcnow() + timedelta(seconds=min(3600, 30 * 2 ** job.attempts))
        db.session.commit()
        processed += 1
    return {'processed': processed}
