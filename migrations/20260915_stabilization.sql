-- Apply to PostgreSQL BEFORE deploying the stabilization release.
-- Abort rather than silently delete existing duplicate clients.
BEGIN;
DO $$ BEGIN
    IF EXISTS (SELECT lead_id FROM client WHERE lead_id IS NOT NULL
               GROUP BY lead_id HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'Duplicate client.lead_id values: reconcile these clients before migration';
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_client_origin_lead ON client(lead_id);
CREATE TABLE IF NOT EXISTS webhook_delivery (
    id VARCHAR(36) PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company(id),
    webhook_id INTEGER NOT NULL REFERENCES integration_webhooks(id),
    event_name VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_webhook_delivery_due ON webhook_delivery(status, available_at);
CREATE INDEX IF NOT EXISTS ix_whatsapp_history_cursor ON whatsapp_messages(conversation_id, id);
COMMIT;
