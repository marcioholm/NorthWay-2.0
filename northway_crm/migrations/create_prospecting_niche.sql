CREATE TABLE IF NOT EXISTS prospecting_niche (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company(id),
    name VARCHAR(100) NOT NULL,
    search_query VARCHAR(200) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) DEFAULT 'PR',
    min_rating FLOAT DEFAULT 3.5,
    min_reviews INTEGER DEFAULT 5,
    active_weekdays JSONB DEFAULT '[]',
    default_campaign_id INTEGER REFERENCES prospecting_campaigns(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prospecting_niche_company
    ON prospecting_niche (company_id, is_active);
