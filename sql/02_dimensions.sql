-- =============================================================================
-- 02 · Dimensions
-- =============================================================================
-- Surrogate integer keys throughout. Natural keys are kept as attributes so the
-- model stays debuggable, but relationships in Power BI run on the surrogates:
-- they are narrow, stable, and immune to a source system renaming a department.
-- =============================================================================

-- --- Date ---------------------------------------------------------------------
-- Contiguous daily calendar spanning every date present in the facts. Power BI
-- needs an unbroken date table for time intelligence to behave.
CREATE TABLE analytics.d_date AS
WITH bounds AS (
    SELECT date_trunc('year', min(d))::date AS from_date,
           (date_trunc('year', max(d)) + interval '1 year - 1 day')::date AS to_date
    FROM (
        SELECT min(snapshot_date) AS d FROM raw.hris_headcount_monthly
        UNION ALL SELECT max(snapshot_date) FROM raw.hris_headcount_monthly
        UNION ALL SELECT min(event_date)    FROM raw.hris_movements
        UNION ALL SELECT max(event_date)    FROM raw.hris_movements
    ) s
)
SELECT
    to_char(d, 'YYYYMMDD')::int                                    AS date_key,
    d::date                                                        AS date,
    extract(year  FROM d)::smallint                                AS year,
    extract(month FROM d)::smallint                                AS month_number,
    to_char(d, 'Mon')                                              AS month_short,
    to_char(d, 'Month')                                            AS month_name,
    to_char(d, 'YYYY-MM')                                          AS year_month,
    ('Q' || extract(quarter FROM d))::text                         AS quarter,
    (d = (date_trunc('month', d) + interval '1 month - 1 day')::date) AS is_month_end
FROM bounds, generate_series(bounds.from_date, bounds.to_date, interval '1 day') AS g(d);

ALTER TABLE analytics.d_date ADD PRIMARY KEY (date_key);

-- --- Employee -----------------------------------------------------------------
CREATE TABLE analytics.d_employee AS
SELECT
    row_number() OVER (ORDER BY employee_id)::int AS employee_key,
    employee_id,
    hire_date,
    gender,
    employment_type,
    exit_date,
    (exit_date IS NULL) AS is_active
FROM raw.hris_employees;

ALTER TABLE analytics.d_employee ADD PRIMARY KEY (employee_key);
CREATE UNIQUE INDEX ux_d_employee_id ON analytics.d_employee (employee_id);

-- --- Job ----------------------------------------------------------------------
CREATE TABLE analytics.d_job AS
SELECT
    row_number() OVER (ORDER BY job_code, level_order, job_level)::int AS job_key,
    job_code,
    job_family,
    job_level,
    track,
    level_order
FROM raw.ref_job_catalog;

ALTER TABLE analytics.d_job ADD PRIMARY KEY (job_key);
CREATE UNIQUE INDEX ux_d_job_natural ON analytics.d_job (job_code, job_level);

-- --- Organisation -------------------------------------------------------------
CREATE TABLE analytics.d_org AS
SELECT
    row_number() OVER (ORDER BY business_unit, department)::int AS org_key,
    business_unit,
    department
FROM (SELECT DISTINCT business_unit, department FROM raw.hris_headcount_monthly) s;

ALTER TABLE analytics.d_org ADD PRIMARY KEY (org_key);
CREATE UNIQUE INDEX ux_d_org_natural ON analytics.d_org (business_unit, department);

-- --- Location -----------------------------------------------------------------
CREATE TABLE analytics.d_location AS
SELECT
    row_number() OVER (ORDER BY region, country, city)::int AS location_key,
    city,
    country,
    region,
    currency_code,
    is_hub,
    geo_tier,
    cost_of_labor_index
FROM raw.ref_locations;

ALTER TABLE analytics.d_location ADD PRIMARY KEY (location_key);
CREATE UNIQUE INDEX ux_d_location_city ON analytics.d_location (city);

-- --- Legal entity -------------------------------------------------------------
-- Separate from location because row-level security scopes by legal entity, and
-- a country can in principle host more than one.
CREATE TABLE analytics.d_company AS
SELECT
    row_number() OVER (ORDER BY region, legal_entity)::int AS company_key,
    legal_entity,
    country,
    region
FROM (SELECT DISTINCT legal_entity, country, region FROM raw.ref_locations) s;

ALTER TABLE analytics.d_company ADD PRIMARY KEY (company_key);
CREATE UNIQUE INDEX ux_d_company_entity ON analytics.d_company (legal_entity);

-- --- FX rates -----------------------------------------------------------------
-- Exposed to the model so the report can show the currency effect explicitly,
-- even though row-level conversion happens here in SQL.
CREATE TABLE analytics.d_fx_rate AS
SELECT
    to_char(date, 'YYYYMMDD')::int AS date_key,
    date,
    currency_code,
    rate_local_per_usd_actual,
    rate_local_per_usd_constant
FROM raw.fx_rates;

ALTER TABLE analytics.d_fx_rate ADD PRIMARY KEY (date_key, currency_code);

-- --- Security -----------------------------------------------------------------
-- The bridge that row-level security reads. One row per user per scope, so a
-- person covering two regions is two rows rather than a special case.
--
-- scope_type   Global            no filter at all
--              Region            filters Dim_Location
--              LegalEntity       filters Dim_Company
--              BusinessUnit      filters Dim_Organization
--              CompensationAccess  exempt from the minimum group size rule
--
-- Hidden in the model: it is plumbing, not something to slice a report by.
CREATE TABLE analytics.d_security AS
SELECT
    row_number() OVER (ORDER BY user_email, scope_type, scope_value)::int AS security_key,
    lower(user_email) AS user_email,
    scope_type,
    scope_value,
    role_description
FROM raw.ref_security;

ALTER TABLE analytics.d_security ADD PRIMARY KEY (security_key);
CREATE INDEX ix_d_security_user ON analytics.d_security (user_email);
