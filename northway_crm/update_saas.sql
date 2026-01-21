-- RUN THIS IN SUPABASE SQL EDITOR

-- 1. Add CPF/CNPJ Column
ALTER TABLE company ADD COLUMN IF NOT EXISTS cpf_cnpj VARCHAR(20);
ALTER TABLE company ADD CONSTRAINT company_cpf_cnpj_key UNIQUE (cpf_cnpj);

-- 2. Add SaaS Subscription Columns
ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_id VARCHAR(50);
ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive';
ALTER TABLE company ADD COLUMN IF NOT EXISTS plan_type VARCHAR(20) DEFAULT 'free';

-- 3. Verify
SELECT * FROM company LIMIT 1;
