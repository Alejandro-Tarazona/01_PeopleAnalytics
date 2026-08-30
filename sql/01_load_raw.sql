-- =============================================================================
-- 01 · Load source extracts into the raw layer
-- =============================================================================
-- \copy runs client-side, so paths are relative to the directory psql was
-- launched from (the repository root) and no server-side file permissions are
-- needed. That is what makes this reproducible on any machine.
--
-- market_bands.xlsx is deliberately absent: the salary survey is cleansed in
-- Power Query and joined in the semantic model. See docs/case/data-design.md.
-- =============================================================================

CREATE TABLE raw.ref_locations (
    city                 text    NOT NULL,
    country              text    NOT NULL,
    legal_entity         text    NOT NULL,
    currency_code        char(3) NOT NULL,
    region               text    NOT NULL,
    is_hub               boolean NOT NULL,
    geo_tier             text    NOT NULL,
    cost_of_labor_index  numeric(4,2) NOT NULL
);

CREATE TABLE raw.ref_job_catalog (
    job_code     char(3) NOT NULL,
    job_family   text    NOT NULL,
    job_level    text    NOT NULL,
    track        text    NOT NULL,
    level_order  smallint NOT NULL
);

CREATE TABLE raw.fx_rates (
    date                        date    NOT NULL,
    currency_code               char(3) NOT NULL,
    rate_local_per_usd_actual   numeric(14,6) NOT NULL,
    rate_local_per_usd_constant numeric(14,6) NOT NULL
);

CREATE TABLE raw.hris_employees (
    employee_id      text NOT NULL,
    hire_date        date NOT NULL,
    gender           char(1),
    employment_type  text,
    exit_date        date
);

CREATE TABLE raw.hris_headcount_monthly (
    snapshot_date        date    NOT NULL,
    employee_id          text    NOT NULL,
    city                 text    NOT NULL,
    business_unit        text    NOT NULL,
    department           text    NOT NULL,
    job_code             char(3) NOT NULL,
    job_level            text    NOT NULL,
    manager_id           text,
    currency_code        char(3) NOT NULL,
    base_salary_local    numeric(16,2) NOT NULL,
    variable_target_pct  numeric(5,4)  NOT NULL,
    fte                  numeric(3,2)  NOT NULL
);

CREATE TABLE raw.hris_movements (
    event_date           date NOT NULL,
    employee_id          text NOT NULL,
    event_type           text NOT NULL,
    event_reason         text,
    salary_local_before  numeric(16,2),
    salary_local_after   numeric(16,2),
    currency_code        char(3) NOT NULL
);

\copy raw.ref_locations         FROM 'data/raw/ref_locations.csv'         WITH (FORMAT csv, HEADER true)
\copy raw.ref_job_catalog       FROM 'data/raw/ref_job_catalog.csv'       WITH (FORMAT csv, HEADER true)
\copy raw.fx_rates              FROM 'data/raw/fx_rates.csv'              WITH (FORMAT csv, HEADER true)
\copy raw.hris_employees        FROM 'data/raw/hris_employees.csv'        WITH (FORMAT csv, HEADER true)
\copy raw.hris_headcount_monthly FROM 'data/raw/hris_headcount_monthly.csv' WITH (FORMAT csv, HEADER true)
\copy raw.hris_movements        FROM 'data/raw/hris_movements.csv'        WITH (FORMAT csv, HEADER true)

-- Indexes on the join keys used by the transformation layer.
CREATE INDEX ix_headcount_employee ON raw.hris_headcount_monthly (employee_id);
CREATE INDEX ix_headcount_snapshot ON raw.hris_headcount_monthly (snapshot_date);
CREATE INDEX ix_headcount_manager  ON raw.hris_headcount_monthly (snapshot_date, manager_id);
CREATE INDEX ix_movements_employee ON raw.hris_movements (employee_id);
CREATE INDEX ix_fx_lookup          ON raw.fx_rates (currency_code, date);
