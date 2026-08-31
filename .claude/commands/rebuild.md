---
description: Rebuild the analytics database and run the full validation suite
allowed-tools: Bash, Read, Grep, Glob
---

Rebuild the star schema and verify it, from the repository root.

1. `psql -U postgres -d mpg_analytics -v ON_ERROR_STOP=1 -f sql/build.sql`
2. `pytest -q`

Then report, briefly:

- The row counts `build.sql` prints, and whether `f_headcount` is 107,124 and
  `f_movement` is 12,261. A different number means the SQL layer changed and the
  reason has to be found before anything else is trusted.
- How many tests passed, failed and skipped. Skips are expected while
  `data/exports/segment_scan_pbi.csv` is absent — that file comes from Power BI and
  cannot be produced from here.
- For any failure: the assertion, the values involved, and what you think caused it.

If the build fails on a permissions error against the `analytics` schema, the
`mpg_reader` role does not exist yet. Create it once with
`psql -U postgres -d mpg_analytics -v reader_password='<password>' -f sql/04_role.sql`
and then rebuild — `build.sql` re-applies the grants on every run afterwards.

Do not fix anything yet. Report first, then wait.
