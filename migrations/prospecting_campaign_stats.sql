-- Add tracking columns to prospecting_campaigns table
ALTER TABLE prospecting_campaigns ADD COLUMN IF NOT EXISTS total_leads INTEGER DEFAULT 0;
ALTER TABLE prospecting_campaigns ADD COLUMN IF NOT EXISTS total_queued INTEGER DEFAULT 0;
ALTER TABLE prospecting_campaigns ADD COLUMN IF NOT EXISTS total_sent INTEGER DEFAULT 0;
ALTER TABLE prospecting_campaigns ADD COLUMN IF NOT EXISTS total_delivered INTEGER DEFAULT 0;
ALTER TABLE prospecting_campaigns ADD COLUMN IF NOT EXISTS total_failed INTEGER DEFAULT 0;
ALTER TABLE prospecting_campaigns ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP;
ALTER TABLE prospecting_campaigns ADD COLUMN IF NOT EXISTS n8n_workflow_id VARCHAR(100);