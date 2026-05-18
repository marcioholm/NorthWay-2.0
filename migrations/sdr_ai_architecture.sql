-- Migration: SDR AI Architecture (Conversations, Messages, Memory, Logs)

-- 1. Alter crm_channel_integrations to use UUID (Drop and Recreate since it is empty)
DROP TABLE IF EXISTS public.crm_channel_integrations CASCADE;

CREATE TABLE public.crm_channel_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL,
    instance_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    api_url VARCHAR(255),
    api_key VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_crm_channel_integrations_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.company(id) ON DELETE CASCADE,
    CONSTRAINT uq_provider_instance UNIQUE (provider, instance_name)
);
CREATE INDEX idx_provider_instance ON public.crm_channel_integrations (provider, instance_name);

-- 2. Create crm_conversations
CREATE TABLE public.crm_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    lead_id INTEGER,
    channel VARCHAR(50) NOT NULL,
    provider VARCHAR(50),
    instance_name VARCHAR(100),
    remote_jid VARCHAR(255),
    phone VARCHAR(50),
    status VARCHAR(50) DEFAULT 'open',
    last_message_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_crm_conversations_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.company(id) ON DELETE CASCADE,
    CONSTRAINT fk_crm_conversations_lead_id FOREIGN KEY (lead_id) REFERENCES public.lead(id) ON DELETE SET NULL
);

-- 3. Create crm_conversation_messages
CREATE TABLE public.crm_conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES public.crm_conversations(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL,
    lead_id INTEGER,
    direction VARCHAR(50) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    provider VARCHAR(50),
    instance_name VARCHAR(100),
    remote_jid VARCHAR(255),
    phone VARCHAR(50),
    message_id VARCHAR(255),
    message_type VARCHAR(50) DEFAULT 'text',
    text_content TEXT,
    raw_payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_crm_conversation_msgs_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.company(id) ON DELETE CASCADE,
    CONSTRAINT fk_crm_conversation_msgs_lead_id FOREIGN KEY (lead_id) REFERENCES public.lead(id) ON DELETE SET NULL
);
CREATE INDEX idx_crm_conv_msgs_msg_id ON public.crm_conversation_messages (message_id);

-- 4. Create crm_conversation_memory
CREATE TABLE public.crm_conversation_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    lead_id INTEGER NOT NULL,
    conversation_id UUID REFERENCES public.crm_conversations(id) ON DELETE CASCADE,
    summary TEXT,
    last_intention VARCHAR(255),
    last_objection VARCHAR(255),
    interest_level VARCHAR(50),
    next_best_action VARCHAR(255),
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_crm_conv_memory_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.company(id) ON DELETE CASCADE,
    CONSTRAINT fk_crm_conv_memory_lead_id FOREIGN KEY (lead_id) REFERENCES public.lead(id) ON DELETE CASCADE
);

-- 5. Create crm_ai_logs
CREATE TABLE public.crm_ai_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL,
    lead_id INTEGER,
    conversation_id UUID REFERENCES public.crm_conversations(id) ON DELETE CASCADE,
    action VARCHAR(100),
    provider VARCHAR(50),
    model_name VARCHAR(100),
    prompt JSONB,
    input_data JSONB,
    output_data JSONB,
    classification VARCHAR(100),
    error_message TEXT,
    tokens_used INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_crm_ai_logs_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.company(id) ON DELETE CASCADE,
    CONSTRAINT fk_crm_ai_logs_lead_id FOREIGN KEY (lead_id) REFERENCES public.lead(id) ON DELETE SET NULL
);

-- 6. RLS Policies
ALTER TABLE public.crm_channel_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_conversation_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crm_ai_logs ENABLE ROW LEVEL SECURITY;

-- Integrations
DROP POLICY IF EXISTS "tenant_isolation" ON public.crm_channel_integrations;
CREATE POLICY "tenant_isolation" ON public.crm_channel_integrations
  FOR ALL TO authenticated
  USING (tenant_id = public.get_current_user_company_id())
  WITH CHECK (tenant_id = public.get_current_user_company_id());

-- Conversations
DROP POLICY IF EXISTS "tenant_isolation" ON public.crm_conversations;
CREATE POLICY "tenant_isolation" ON public.crm_conversations
  FOR ALL TO authenticated
  USING (tenant_id = public.get_current_user_company_id())
  WITH CHECK (tenant_id = public.get_current_user_company_id());

-- Messages
DROP POLICY IF EXISTS "tenant_isolation" ON public.crm_conversation_messages;
CREATE POLICY "tenant_isolation" ON public.crm_conversation_messages
  FOR ALL TO authenticated
  USING (tenant_id = public.get_current_user_company_id())
  WITH CHECK (tenant_id = public.get_current_user_company_id());

-- Memory
DROP POLICY IF EXISTS "tenant_isolation" ON public.crm_conversation_memory;
CREATE POLICY "tenant_isolation" ON public.crm_conversation_memory
  FOR ALL TO authenticated
  USING (tenant_id = public.get_current_user_company_id())
  WITH CHECK (tenant_id = public.get_current_user_company_id());

-- AI Logs
DROP POLICY IF EXISTS "tenant_isolation" ON public.crm_ai_logs;
CREATE POLICY "tenant_isolation" ON public.crm_ai_logs
  FOR ALL TO authenticated
  USING (tenant_id = public.get_current_user_company_id())
  WITH CHECK (tenant_id = public.get_current_user_company_id());
