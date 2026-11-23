-- Episodes: flags with the same likely root cause and issuer segment on consecutive days
-- (a gap of at most 1 day) form one case. Deterministic, so reruns give the same case keys.
-- case_key = root_cause | issuer_segment | episode_start. Stable because flags arrive in date order.
CREATE OR REPLACE VIEW classic_stable_zjnu75_catalog.network_migration.gold_case_flags
COMMENT 'Flagged anomalies grouped into cases (episodes of the same likely root cause and issuer segment, gap <= 1 day). One row per flag, with its case_key and is_representative (highest score in the case).'
AS
WITH d AS (
  SELECT DISTINCT likely_root_cause, issuer_segment, business_date
  FROM classic_stable_zjnu75_catalog.network_migration.gold_anomalies
  WHERE likely_root_cause IS NOT NULL
),
e AS (
  SELECT *,
    CASE WHEN datediff(business_date, lag(business_date) OVER (PARTITION BY likely_root_cause, issuer_segment ORDER BY business_date)) <= 2
         THEN 0 ELSE 1 END AS new_episode
  FROM d
),
g AS (
  SELECT *, sum(new_episode) OVER (PARTITION BY likely_root_cause, issuer_segment ORDER BY business_date) AS episode_no
  FROM e
),
s AS (
  SELECT likely_root_cause, issuer_segment, business_date,
         min(business_date) OVER (PARTITION BY likely_root_cause, issuer_segment, episode_no) AS episode_start,
         max(business_date) OVER (PARTITION BY likely_root_cause, issuer_segment, episode_no) AS episode_end
  FROM g
)
SELECT
  concat_ws('|', a.likely_root_cause, a.issuer_segment, CAST(s.episode_start AS STRING)) AS case_key,
  s.episode_start, s.episode_end,
  a.*,
  row_number() OVER (PARTITION BY a.likely_root_cause, a.issuer_segment, s.episode_start ORDER BY a.score DESC, a.anomaly_key) = 1 AS is_representative
FROM classic_stable_zjnu75_catalog.network_migration.gold_anomalies a
JOIN s USING (likely_root_cause, issuer_segment, business_date);
