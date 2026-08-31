-- =============================================================================
-- build.sql · Rebuilds the analytical database from data/raw
-- =============================================================================
-- Run from the repository root:
--
--   psql -U postgres -d mpg_analytics -v ON_ERROR_STOP=1 -f sql/build.sql
--
-- Idempotent: the schemas are dropped and recreated, so running it twice gives
-- the same database. Grants are re-applied at the end, because dropping the
-- schema drops them too. Creating the reporting role itself needs a password and
-- is done once, separately, in sql/04_role.sql.
-- =============================================================================

\timing on

\echo '→ schemas'
\i sql/00_schema.sql
\echo '→ loading source extracts'
\i sql/01_load_raw.sql
\echo '→ dimensions'
\i sql/02_dimensions.sql
\echo '→ facts'
\i sql/03_facts.sql
\echo '→ re-applying read-only privileges'
\i sql/05_grants.sql

\echo ''
\echo 'Row counts:'
SELECT 'd_date' AS object, count(*) FROM analytics.d_date
UNION ALL SELECT 'd_employee',  count(*) FROM analytics.d_employee
UNION ALL SELECT 'd_job',       count(*) FROM analytics.d_job
UNION ALL SELECT 'd_org',       count(*) FROM analytics.d_org
UNION ALL SELECT 'd_location',  count(*) FROM analytics.d_location
UNION ALL SELECT 'd_company',   count(*) FROM analytics.d_company
UNION ALL SELECT 'd_fx_rate',   count(*) FROM analytics.d_fx_rate
UNION ALL SELECT 'f_headcount', count(*) FROM analytics.f_headcount
UNION ALL SELECT 'f_movement',  count(*) FROM analytics.f_movement
ORDER BY 1;
