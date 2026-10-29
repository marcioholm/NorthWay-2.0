-- ============================================================================
-- NorthWay CRM - Otimização de Performance: Índices para Chaves e Filtros
-- Arquivo: migrations/20261028_perf_indexes.sql
-- NOTA: NÃO APLICAR AUTOMATICAMENTE. Rodar via psql/Supabase Dashboard com CONCURRENTLY.
-- ============================================================================

-- 1. CONSULTA DE ÍNDICES JÁ EXISTENTES (Conferir antes de aplicar)
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
    'task', 
    'interaction', 
    'notification', 
    'whatsapp_conversations', 
    'whatsapp_conversation', 
    'lead', 
    'transaction'
  )
ORDER BY tablename, indexname;

-- ============================================================================
-- 2. CRIAÇÃO DE ÍNDICES DE PERFORMANCE (CONCURRENTLY, SEM LOCK DE LEITURA/ESCRITA)
-- ============================================================================

-- Tabela: task
-- Filtros frequentes: tarefas da empresa por usuário e status (/home, /tasks)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_company_assigned_status 
    ON task (company_id, assigned_to_id, status);

-- Chaves estrangeiras e carregamento de relacionamentos (/pipeline, /clients/<id>, /leads/<id>)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_lead_id 
    ON task (lead_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_client_id 
    ON task (client_id);

-- Ordenação e checagem de vencimento (/home, /tasks)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_due_date 
    ON task (due_date);

-- Tabela: interaction
-- Carregamento do histórico e cálculo de dias de inatividade
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interaction_lead_id 
    ON interaction (lead_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interaction_client_id 
    ON interaction (client_id);

-- Tabela: notification
-- Contagem e listagem de notificações não lidas por usuário
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_user_read 
    ON notification (user_id, read);

-- Tabela: whatsapp_conversations
-- Busca de conversas por lead e cliente
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_whatsapp_conversations_lead_id 
    ON whatsapp_conversations (lead_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_whatsapp_conversations_client_id 
    ON whatsapp_conversations (client_id);

-- Tabela: lead
-- Filtro do Kanban do funil de vendas por empresa e etapa (/pipeline)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_company_pipeline_stage 
    ON lead (company_id, pipeline_stage_id);

-- Ordenação recente e paginação de leads por empresa (/leads, /pipeline)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_company_created_at 
    ON lead (company_id, created_at DESC);

-- Tabela: transaction
-- Filtro financeiro por vencimento e competência mensal por empresa (/financial)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transaction_company_due_date 
    ON transaction (company_id, due_date);
