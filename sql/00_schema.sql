-- =============================================================================
-- 00 · Schemas
-- =============================================================================
-- Two layers, one responsibility each:
--   raw       landing zone. Source extracts loaded verbatim, no transformation.
--             If a value is wrong here, the source is wrong.
--   analytics consumption layer. Star schema and analytical views served to
--             Power BI. Everything here is derived and reproducible.
--
-- Dropping and recreating makes the build idempotent: running build.sql twice
-- produces the same database, which is what makes the pipeline testable.
-- =============================================================================

DROP SCHEMA IF EXISTS analytics CASCADE;
DROP SCHEMA IF EXISTS raw CASCADE;

CREATE SCHEMA raw;
CREATE SCHEMA analytics;

COMMENT ON SCHEMA raw IS
    'Landing zone. Source extracts loaded verbatim from data/raw, no transformation.';
COMMENT ON SCHEMA analytics IS
    'Consumption layer. Star schema and analytical views served to Power BI.';
