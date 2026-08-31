-- =============================================================================
-- 03 · Facts
-- =============================================================================
-- Two facts at different grains:
--   f_headcount  one row per employee per month-end. Answers "how did we look
--                in March?"
--   f_movement   one row per event. Answers "what changed between February and
--                March?"
-- Both are needed: attrition cannot be derived from snapshots alone, and pay
-- position cannot be derived from events alone.
--
-- Currency conversion happens here, not in DAX. A row-level conversion is
-- deterministic — it does not depend on filter context — so pushing it into the
-- model would only make every measure heavier. Ratios that DO depend on context
-- (compa-ratio, weighted averages) are deliberately left to DAX.
-- =============================================================================

-- --- Span of control ----------------------------------------------------------
-- Derived from manager_id rather than carried in the source, which is the point:
-- the extract has no such column. Counted per snapshot because an org changes
-- month to month.
CREATE TEMPORARY TABLE tmp_span AS
SELECT snapshot_date,
       manager_id,
       count(*)::smallint AS direct_reports
FROM raw.hris_headcount_monthly
WHERE manager_id IS NOT NULL
GROUP BY snapshot_date, manager_id;

CREATE INDEX ix_tmp_span ON tmp_span (snapshot_date, manager_id);

-- --- Headcount ----------------------------------------------------------------
CREATE TABLE analytics.f_headcount AS
SELECT
    to_char(h.snapshot_date, 'YYYYMMDD')::int              AS snapshot_date_key,
    e.employee_key,
    j.job_key,
    o.org_key,
    l.location_key,
    c.company_key,
    m.employee_key                                         AS manager_employee_key,
    coalesce(s.direct_reports, 0)::smallint                AS span_of_manager,
    h.currency_code,
    h.base_salary_local,
    round(h.base_salary_local / fx.rate_local_per_usd_constant, 2) AS base_salary_usd_constant,
    round(h.base_salary_local / fx.rate_local_per_usd_actual,   2) AS base_salary_usd_actual,
    h.variable_target_pct,
    -- Composite key for the market band relationship. Bands join on three
    -- columns (job code, level, geo tier) and Power BI supports single-column
    -- relationships only, so both sides carry the same concatenated key. Power
    -- Query builds the identical string on the salary survey.
    trim(j.job_code) || '|' || j.job_level || '|' || l.geo_tier AS band_key,
    round(h.base_salary_local * (1 + h.variable_target_pct)
          / fx.rate_local_per_usd_constant, 2)             AS target_cash_usd_constant,
    -- Internal pay position: where this person sits inside their own
    -- city x job x level cohort, independent of any market band. Computed here
    -- because a window function costs one pass in SQL, while the DAX equivalent
    -- is a RANKX over a filtered table evaluated once per row.
    -- Suppressed below five peers: a percentile inside a group of two says
    -- nothing, and the same minimum-group rule governs the report.
    CASE WHEN count(*) OVER peer_group >= 5
         THEN round((percent_rank() OVER peer_group_ordered)::numeric, 4) END AS peer_percentile,
    CASE WHEN count(*) OVER peer_group >= 5
         THEN round(((h.base_salary_local / fx.rate_local_per_usd_constant)
              / avg(h.base_salary_local / fx.rate_local_per_usd_constant) OVER peer_group
              - 1)::numeric, 4) END                          AS vs_peer_average,
    h.fte
FROM raw.hris_headcount_monthly h
JOIN analytics.d_employee  e  ON e.employee_id = h.employee_id
JOIN analytics.d_job       j  ON j.job_code = h.job_code AND j.job_level = h.job_level
JOIN analytics.d_org       o  ON o.business_unit = h.business_unit AND o.department = h.department
JOIN analytics.d_location  l  ON l.city = h.city
JOIN raw.ref_locations     rl ON rl.city = h.city
JOIN analytics.d_company   c  ON c.legal_entity = rl.legal_entity
JOIN raw.fx_rates          fx ON fx.currency_code = h.currency_code AND fx.date = h.snapshot_date
LEFT JOIN analytics.d_employee m ON m.employee_id = h.manager_id
LEFT JOIN tmp_span s ON s.snapshot_date = h.snapshot_date AND s.manager_id = h.manager_id
-- Two window definitions on the same partition: percent_rank needs an ORDER BY,
-- while count and avg must see the whole peer group. Sharing one window with an
-- ORDER BY would silently turn them into running totals.
WINDOW peer_group AS (PARTITION BY h.snapshot_date, h.city, h.job_code, h.job_level),
       peer_group_ordered AS (PARTITION BY h.snapshot_date, h.city, h.job_code, h.job_level
                              ORDER BY h.base_salary_local / fx.rate_local_per_usd_constant);

ALTER TABLE analytics.f_headcount ADD PRIMARY KEY (snapshot_date_key, employee_key);
CREATE INDEX ix_f_headcount_job      ON analytics.f_headcount (job_key);
CREATE INDEX ix_f_headcount_location ON analytics.f_headcount (location_key);
CREATE INDEX ix_f_headcount_org      ON analytics.f_headcount (org_key);

-- --- Movements ----------------------------------------------------------------
-- An event fact has to carry its own dimension keys. Joining it to the employee
-- alone looks sufficient until someone slices attrition by city: the movement has
-- no location, so every cell returns the company total. The keys below fix the
-- event to the position the person actually held when it happened, which is also
-- the only correct attribution for a promotion or a transfer.
CREATE TABLE analytics.f_movement AS
SELECT
    to_char(mv.event_date, 'YYYYMMDD')::int AS event_date_key,
    e.employee_key,
    pos.job_key,
    pos.org_key,
    pos.location_key,
    pos.company_key,
    mv.event_type,
    mv.event_reason,
    mv.currency_code,
    mv.salary_local_before,
    mv.salary_local_after,
    round(mv.salary_local_before / fx.rate_local_per_usd_constant, 2) AS salary_usd_before,
    round(mv.salary_local_after  / fx.rate_local_per_usd_constant, 2) AS salary_usd_after,
    CASE
        WHEN mv.salary_local_before IS NULL OR mv.salary_local_after IS NULL THEN NULL
        ELSE round(mv.salary_local_after / mv.salary_local_before - 1, 4)
    END AS salary_change_pct,
    (mv.event_type = 'Voluntary Exit')   AS is_voluntary_exit,
    (mv.event_type = 'Involuntary Exit') AS is_involuntary_exit,
    (mv.event_type = 'Hire')             AS is_hire
FROM raw.hris_movements mv
JOIN analytics.d_employee e ON e.employee_id = mv.employee_id
JOIN raw.fx_rates fx ON fx.currency_code = mv.currency_code AND fx.date = mv.event_date
-- The position held at the time of the event: the nearest snapshot at or before it.
-- An exit in March belongs to the March org, not to wherever the person happened to
-- sit in their final row. LATERAL keeps this to one indexed lookup per event; the
-- COALESCE catches a hire whose event predates their first snapshot.
LEFT JOIN LATERAL (
    SELECT coalesce(before_event.job_key,      first_row.job_key)      AS job_key,
           coalesce(before_event.org_key,      first_row.org_key)      AS org_key,
           coalesce(before_event.location_key, first_row.location_key) AS location_key,
           coalesce(before_event.company_key,  first_row.company_key)  AS company_key
    FROM (SELECT f.job_key, f.org_key, f.location_key, f.company_key
          FROM analytics.f_headcount f
          WHERE f.employee_key = e.employee_key
            AND f.snapshot_date_key <= to_char(mv.event_date, 'YYYYMMDD')::int
          ORDER BY f.snapshot_date_key DESC LIMIT 1) before_event
    FULL JOIN (SELECT f.job_key, f.org_key, f.location_key, f.company_key
               FROM analytics.f_headcount f
               WHERE f.employee_key = e.employee_key
               ORDER BY f.snapshot_date_key ASC LIMIT 1) first_row ON true
) pos ON true
-- 77 events belong to 76 people who left on the first month-end of the horizon and
-- so never appear in any snapshot. They have no position to attribute to. LEFT JOIN
-- above and this filter make that a decision rather than a side effect of a join:
-- an inner join would have removed the same rows without anyone noticing.
-- They cost the analysis nothing — every one of them predates the trailing-twelve-
-- month window by more than a year — and tests/test_sql_layer.py pins both the
-- count and the reason so the day it changes, it fails.
WHERE pos.job_key IS NOT NULL;

ALTER TABLE analytics.f_movement
    ALTER COLUMN job_key      SET NOT NULL,
    ALTER COLUMN org_key      SET NOT NULL,
    ALTER COLUMN location_key SET NOT NULL,
    ALTER COLUMN company_key  SET NOT NULL;

CREATE INDEX ix_f_movement_employee ON analytics.f_movement (employee_key);
CREATE INDEX ix_f_movement_date     ON analytics.f_movement (event_date_key);
CREATE INDEX ix_f_movement_type     ON analytics.f_movement (event_type);
CREATE INDEX ix_f_movement_job      ON analytics.f_movement (job_key);
CREATE INDEX ix_f_movement_location ON analytics.f_movement (location_key);
