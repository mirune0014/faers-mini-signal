CREATE TABLE IF NOT EXISTS reports (
  safetyreportid VARCHAR PRIMARY KEY,
  receivedate DATE,
  primarysource_qualifier INTEGER
);

CREATE TABLE IF NOT EXISTS drugs (
  safetyreportid VARCHAR,
  drug_name VARCHAR,
  drug_name_normalized VARCHAR,  -- ingredient-level name (lowercase)
  drug_norm_source VARCHAR,      -- openfda_harmonized | rxnorm_api | unmapped
  role INTEGER, -- 1: suspect, 2: concomitant, 3: interacting
  FOREIGN KEY (safetyreportid) REFERENCES reports(safetyreportid)
);

-- Migrate existing DBs: add columns if missing (idempotent)
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS drug_name_normalized VARCHAR;
ALTER TABLE drugs ADD COLUMN IF NOT EXISTS drug_norm_source VARCHAR;

CREATE TABLE IF NOT EXISTS reactions (
  safetyreportid VARCHAR,
  meddra_pt VARCHAR,
  FOREIGN KEY (safetyreportid) REFERENCES reports(safetyreportid)
);

