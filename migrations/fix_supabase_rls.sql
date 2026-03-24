-- Migration: Fix Supabase RLS Security Errors
-- This script enables RLS on all public tables and adds policies to restrict access based on company_id.

-- 1. Enable RLS on all tables
ALTER TABLE public.role ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.integration ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whats_app_message ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quick_message ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.process_template ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.financial_category ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nfse_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_stage ENABLE ROW LEVEL SECURITY;

-- 2. Create a helper function to get the current user's company_id
-- This assumes that the 'user' table has a 'supabase_uid' column that matches auth.uid()
CREATE OR REPLACE FUNCTION public.get_current_user_company_id()
RETURNS integer AS $$
  SELECT company_id FROM public.user WHERE supabase_uid = auth.uid()::text LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- 3. Apply Multi-Tenant Policies

-- Table: role
CREATE POLICY "Users can only see roles in their company" ON public.role
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage roles in their company" ON public.role
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Table: pipeline
CREATE POLICY "Users can only see pipelines in their company" ON public.pipeline
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage pipelines in their company" ON public.pipeline
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Table: integration
CREATE POLICY "Users can only see integrations in their company" ON public.integration
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage integrations in their company" ON public.integration
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Table: whats_app_message
CREATE POLICY "Users can only see WhatsApp messages in their company" ON public.whats_app_message
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage WhatsApp messages in their company" ON public.whats_app_message
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Table: quick_message
CREATE POLICY "Users can only see quick messages in their company" ON public.quick_message
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage quick messages in their company" ON public.quick_message
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Table: process_template
CREATE POLICY "Users can only see process templates in their company" ON public.process_template
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage process templates in their company" ON public.process_template
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Table: financial_category
CREATE POLICY "Users can only see financial categories in their company" ON public.financial_category
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage financial categories in their company" ON public.financial_category
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- Table: nfse_log
CREATE POLICY "Users can only see NFS-e logs in their company" ON public.nfse_log
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

-- Table: user (Special handling)
CREATE POLICY "Users can see themselves and colleagues" ON public.user
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id() OR supabase_uid = auth.uid()::text);

CREATE POLICY "Users can update their own profile" ON public.user
  FOR UPDATE TO authenticated
  USING (supabase_uid = auth.uid()::text)
  WITH CHECK (supabase_uid = auth.uid()::text);

-- Table: pipeline_stage
CREATE POLICY "Users can only see pipeline stages in their company" ON public.pipeline_stage
  FOR SELECT TO authenticated
  USING (company_id = public.get_current_user_company_id());

CREATE POLICY "Users can manage pipeline stages in their company" ON public.pipeline_stage
  FOR ALL TO authenticated
  USING (company_id = public.get_current_user_company_id())
  WITH CHECK (company_id = public.get_current_user_company_id());

-- 4. Grant access to service_role to bypass RLS (usually default, but being explicit)
-- Note: The service_role key already bypasses RLS by default in Supabase.
-- These policies primarily protect the database from leaks of the anon or authenticated keys.
