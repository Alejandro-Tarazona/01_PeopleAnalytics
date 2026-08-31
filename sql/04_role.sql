-- =============================================================================
-- 04 · Reporting role
-- =============================================================================
-- Creates the login Power BI connects with. Run once; the password is passed in
-- at run time so it never reaches the repository:
--
--   psql -U postgres -d mpg_analytics -v reader_password='...' -f sql/04_role.sql
--
-- The privileges themselves live in 05_grants.sql, which build.sql re-applies on
-- every rebuild. They have to be separate: dropping the analytics schema drops
-- every grant with it, but the role and its password survive.
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
