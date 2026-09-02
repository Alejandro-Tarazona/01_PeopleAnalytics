-- =============================================================================
-- 05 · Read-only privileges on the consumption layer
-- =============================================================================
-- Re-applied by build.sql on every rebuild, because DROP SCHEMA ... CASCADE
-- removes every grant along with the objects. Forgetting this step is how a
-- report that worked yesterday returns "permission denied for schema analytics"
-- today.
--
-- Guarded so the build still succeeds on a machine where the role was never
-- created: a missing reporting role should not break the data pipeline.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mpg_reader') THEN
        RAISE NOTICE 'Role mpg_reader does not exist - skipping grants. Run sql/04_role.sql first.';
        RETURN;
    END IF;

    -- Power BI reads the modeled star schema, never the landing zone.
    EXECUTE 'GRANT USAGE  ON SCHEMA analytics TO mpg_reader';
    EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO mpg_reader';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO mpg_reader';
    EXECUTE 'REVOKE ALL ON SCHEMA raw FROM mpg_reader';

    RAISE NOTICE 'Read-only privileges granted to mpg_reader on schema analytics.';
END
$$;
