ALTER TABLE prospecting_niche
  ADD COLUMN IF NOT EXISTS cities JSONB DEFAULT '[]';

UPDATE prospecting_niche
SET cities = jsonb_build_array(city)
WHERE cities = '[]' AND city IS NOT NULL;

ALTER TABLE prospecting_niche ALTER COLUMN city DROP NOT NULL;
