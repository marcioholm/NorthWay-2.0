-- ============================================================================
-- NorthWay CRM - CREPI v2
-- Arquivo: migrations/20261029_crepi_v2.sql
-- Adiciona: nível calculado (com regra de impacto catastrófico), plano de tratamento
-- (responsável, prazo, gatilho, status, revisão) e risco residual.
-- Idempotente. O database_sync.py aplica as mesmas colunas; este arquivo serve para
-- aplicar manualmente no Supabase (SQL Editor) antes do deploy, se preferir.
-- ============================================================================

ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS nivel VARCHAR(20) DEFAULT 'nao_avaliado';
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS contingencia_obrigatoria BOOLEAN DEFAULT FALSE;
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS responsavel VARCHAR(150);
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS prazo DATE;
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS gatilho TEXT;
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'aberta';
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS revisao_em DATE;
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS probabilidade_residual INTEGER;
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS impacto_residual INTEGER;
ALTER TABLE crepi_premissas ADD COLUMN IF NOT EXISTS score_residual INTEGER;

-- Backfill do nível das premissas existentes (mesma regra de services/crepi_service.py)
UPDATE crepi_premissas SET
    contingencia_obrigatoria = (impacto >= 9 AND probabilidade BETWEEN 1 AND 2),
    nivel = CASE
        WHEN COALESCE(probabilidade, 0) = 0 OR COALESCE(impacto, 0) = 0 THEN 'nao_avaliado'
        WHEN impacto >= 9 AND probabilidade >= 3 THEN 'critico'
        WHEN impacto >= 9 THEN 'medio'
        WHEN probabilidade * impacto > 40 THEN 'critico'
        WHEN probabilidade * impacto > 15 THEN 'medio'
        ELSE 'baixo'
    END;

-- Conferência: premissas que mudaram de nível com a regra nova (impacto >= 9)
SELECT id, nome, probabilidade, impacto, score, nivel, contingencia_obrigatoria
FROM crepi_premissas
WHERE impacto >= 9
ORDER BY score DESC;
