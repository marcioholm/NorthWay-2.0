-- Migration: Add crm_channel_integrations and missing Lead phone fields

-- 1. Add missing fields to Lead table
ALTER TABLE public.lead ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(50);
ALTER TABLE public.lead ADD COLUMN IF NOT EXISTS mobile_phone VARCHAR(50);

-- 2. Create crm_channel_integrations table
CREATE TABLE IF NOT EXISTS public.crm_channel_integrations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL,
    instance_name VARCHAR(100) NOT NULL,
    api_url VARCHAR(255),
    api_key VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_crm_channel_integrations_tenant_id FOREIGN KEY (tenant_id) REFERENCES public.company(id) ON DELETE CASCADE,
    CONSTRAINT uq_provider_instance UNIQUE (provider, instance_name)
);

-- 3. Create Index on provider and instance_name
CREATE INDEX IF NOT EXISTS idx_provider_instance ON public.crm_channel_integrations (provider, instance_name);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.crm_channel_integrations ENABLE ROW LEVEL SECURITY;

-- 5. Create Policies
DROP POLICY IF EXISTS "Users can only see channel integrations in their company" ON public.crm_channel_integrations;
CREATE POLICY "Users can only see channel integrations in their company" ON public.crm_channel_integrations
  FOR SELECT TO authenticated
  USING (tenant_id = public.get_current_user_company_id());

DROP POLICY IF EXISTS "Users can manage channel integrations in their company" ON public.crm_channel_integrations;
CREATE POLICY "Users can manage channel integrations in their company" ON public.crm_channel_integrations
  FOR ALL TO authenticated
  USING (tenant_id = public.get_current_user_company_id())
  WITH CHECK (tenant_id = public.get_current_user_company_id());
