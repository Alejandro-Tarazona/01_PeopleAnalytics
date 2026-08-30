-- =============================================================================
-- 05 · Read-only role for Power BI
-- =============================================================================
-- Power BI connects as mpg_reader, never as the superuser. A reporting tool has
-- no business being able to drop a table, and least privilege is cheap here: two
-- statements. The password is passed in at run time so it never reaches the
-- repository:
--
--   psql -U postgres -d mpg_analytics -v reader_password='...' -f sql/04_grants.sql
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mpg_reader') THEN
        CREATE ROLE mpg_reader LOGIN;
    END IF;
END
$$;

ALTER ROLE mpg_reader WITH PASSWORD :'reader_password';

GRANT CONNECT ON DATABASE mpg_analytics TO mpg_reader;
GRANT USAGE   ON SCHEMA analytics       TO mpg_reader;
GRANT SELECT  ON ALL TABLES IN SCHEMA analytics TO mpg_reader;

-- Anything created in analytics from now on is readable by the role too.
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO mpg_reader;

-- The raw layer stays closed: the report consumes the modelled star schema,
-- not the landing zone.
REVOKE ALL ON SCHEMA raw FROM mpg_reader;
