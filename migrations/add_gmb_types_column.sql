-- Add gmb_types column to lead table for Google Maps place categories
-- Exemplo de valores: ['restaurant', 'food', 'point_of_interest', 'establishment']

ALTER TABLE lead ADD COLUMN IF NOT EXISTS gmb_types JSONB DEFAULT NULL;

-- Indexar para consultas futuras por tipo de estabelecimento
CREATE INDEX IF NOT EXISTS idx_lead_gmb_types ON lead USING gin (gmb_types);
