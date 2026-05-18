-- Enable RLS on AI tables
ALTER TABLE public.tenant_ai_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prospecting_integrations ENABLE ROW LEVEL SECURITY;

-- Helper function to get current company_id (matching fix_supabase_rls.sql pattern)
-- If it already exists, this is fine.
CREATE OR REPLACE FUNCTION public.get_current_user_company_id()
RETURNS integer AS $$
  SELECT company_id FROM public.user WHERE supabase_uid = auth.uid()::text LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Policies for tenant_ai_credentials
DROP POLICY IF EXISTS "Users can only see AI credentials in their company" ON public.tenant_ai_credentials;
CREATE POLICY "Users can only see AI credentials in their company" ON public.tenant_ai_credentials
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

DROP POLICY IF EXISTS "Users can manage AI credentials in their company" ON public.tenant_ai_credentials;
CREATE POLICY "Users can manage AI credentials in their company" ON public.tenant_ai_credentials
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Policies for prospecting_integrations
DROP POLICY IF EXISTS "Users can only see prospecting integrations in their company" ON public.prospecting_integrations;
CREATE POLICY "Users can only see prospecting integrations in their company" ON public.prospecting_integrations
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

DROP POLICY IF EXISTS "Users can manage prospecting integrations in their company" ON public.prospecting_integrations;
CREATE POLICY "Users can manage prospecting integrations in their company" ON public.prospecting_integrations
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());
