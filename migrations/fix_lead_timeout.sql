-- 1. Add missing columns to lead table (Fixes 500 Internal Server Error)
ALTER TABLE public.lead ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(50);
ALTER TABLE public.lead ADD COLUMN IF NOT EXISTS mobile_phone VARCHAR(50);

-- 2. Add performance indexes (Fixes Timeout and query locks)
-- Lead table searches
CREATE INDEX IF NOT EXISTS idx_lead_phone ON public.lead(phone);
CREATE INDEX IF NOT EXISTS idx_lead_whatsapp ON public.lead(whatsapp);
CREATE INDEX IF NOT EXISTS idx_lead_mobile_phone ON public.lead(mobile_phone);

-- Conversations table lookups
CREATE INDEX IF NOT EXISTS idx_crm_conversations_tenant_lead ON public.crm_conversations(tenant_id, lead_id);

-- Conversation messages (history load optimization)
CREATE INDEX IF NOT EXISTS idx_crm_conv_msgs_history ON public.crm_conversation_messages(conversation_id, created_at DESC);

-- Integrations (Tenant Resolution)
-- This might already exist from the previous script, adding IF NOT EXISTS
CREATE INDEX IF NOT EXISTS idx_provider_instance ON public.crm_channel_integrations(provider, instance_name);

-- Idempotency (Processed Messages) if the table exists in production
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'processed_messages') THEN
        CREATE INDEX IF NOT EXISTS idx_processed_messages_tenant_msg ON public.processed_messages(tenant_id, message_id);
    END IF;
END $$;
