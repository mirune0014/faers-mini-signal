-- ABCD aggregation at the report level
--
-- Definitions (per drug/PT pair):
--   A: suspect drug present AND PT present in the same report
--   B: suspect drug present AND PT absent
--   C: suspect drug absent  AND PT present
--   D: neither (complement)
--
-- Notes:
-- - Default uses suspect-only (role = 1). CLI/UI can switch to role in (1,2,3)
--   by replacing the WHERE clause in the first CTE.

-- Suspect drug set (role=1)
-- Use normalized name when available, fallback to lower(drug_name)
CREATE TEMP TABLE suspect AS
SELECT DISTINCT safetyreportid,
       COALESCE(drug_name_normalized, lower(drug_name)) AS drug
FROM drugs
WHERE role = 1;

-- Reaction PT set
CREATE TEMP TABLE rxn AS
SELECT DISTINCT safetyreportid, lower(meddra_pt) AS pt
FROM reactions;

-- Co-occurrence counts for A
CREATE TEMP TABLE a_counts AS
SELECT s.drug, r.pt, COUNT(*) AS A
FROM suspect s
JOIN rxn r USING (safetyreportid)
GROUP BY s.drug, r.pt;

WITH
drug_tot AS (
  SELECT drug, COUNT(DISTINCT safetyreportid) AS Dtot
  FROM suspect
  GROUP BY 1
),
pt_tot AS (
  SELECT pt, COUNT(DISTINCT safetyreportid) AS Rtot
  FROM rxn
  GROUP BY 1
),
rep_tot AS (
  SELECT COUNT(DISTINCT safetyreportid) AS N FROM reports
)
SELECT
  a.drug,
  a.pt,
  a.A                                                    AS A,
  (d.Dtot - a.A)                                         AS B,
  (r.Rtot - a.A)                                         AS C,
  (rep_tot.N - d.Dtot - r.Rtot + a.A)                    AS D,
  d.Dtot                                                 AS drug_reports,
  r.Rtot                                                 AS pt_reports,
  rep_tot.N                                              AS total_reports
FROM a_counts a
JOIN drug_tot d USING (drug)
JOIN pt_tot r USING (pt)
CROSS JOIN rep_tot;

