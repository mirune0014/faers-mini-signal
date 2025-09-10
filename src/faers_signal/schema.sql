CREATE TABLE IF NOT EXISTS reports (
  safetyreportid VARCHAR PRIMARY KEY,
  receivedate DATE,
  primarysource_qualifier INTEGER
);

CREATE TABLE IF NOT EXISTS drugs (
  safetyreportid VARCHAR,
  drug_name VARCHAR,
  role INTEGER, -- 1: suspect, 2: concomitant, 3: interacting
  FOREIGN KEY (safetyreportid) REFERENCES reports(safetyreportid)
);

CREATE TABLE IF NOT EXISTS reactions (
  safetyreportid VARCHAR,
  meddra_pt VARCHAR,
  FOREIGN KEY (safetyreportid) REFERENCES reports(safetyreportid)
);

