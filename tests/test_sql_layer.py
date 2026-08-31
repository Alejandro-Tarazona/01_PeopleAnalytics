"""Level 2 - transformation validation.

Every derived value in the star schema is recomputed here independently, in
pandas, straight from the source files, and compared against what SQL produced.
Two implementations that must agree is the cheapest insurance there is against
the most expensive failure in BI: reporting a number that does not match the
source.
"""

from __future__ import annotations

import pandas as pd

from validation.db import query


def test_accented_text_survives_the_load(conn, raw_locations):
    r"""The city names in the database are the ones in the file, byte for byte.

    \copy hands the file to the server in the session's client_encoding, which psql
    derives from the console code page on Windows. A build run from a WIN1252
    console reads UTF-8 accents as latin-1 and re-encodes them, so 'Bogota' with an
    acute accent is stored as two characters instead of one. Row counts stay right
    and nothing raises; the damage only appears when the scoring in
    tests/test_reconciliation.py compares a city against ground_truth.json with ==
    and gets False for a segment that is plainly there. 01_load_raw.sql declares
    ENCODING 'UTF8' to stop it, and this is what keeps the declaration honest.
    """
    stored = set(query(conn, "SELECT city FROM analytics.d_location")["city"])
    source = set(raw_locations["city"])
    assert stored == source, (
        "the location dimension does not carry the source spellings: "
        f"only in the database {sorted(stored - source)}, "
        f"only in the file {sorted(source - stored)}"
    )


def test_no_rows_lost_loading_the_headcount_fact(conn, raw_headcount):
    rows = query(conn, "SELECT count(*) AS n FROM analytics.f_headcount")["n"].iloc[0]
    assert rows == len(raw_headcount), "the fact join dropped or duplicated snapshot rows"


def test_the_movement_fact_loses_only_the_events_it_declares(conn, raw_movements):
    """Every source movement is either loaded or explained. There is no third case.

    The movement fact carries its own job, org, location and company keys, fixed to
    the position the person held when the event happened — without them, attrition
    cannot be sliced by anything and every segment returns the company total.

    That attribution needs the employee to appear in at least one month-end
    snapshot, and 76 people do not: they left on the first month-end of the horizon.
    Their 77 events cannot be attributed to any organisation. Dropping them is a
    decision, taken in 03_facts.sql behind an explicit filter, and this test is what
    stops it from quietly becoming something else.
    """
    loaded = query(conn, "SELECT count(*) AS n FROM analytics.f_movement")["n"].iloc[0]
    unattributable = query(conn, """
        SELECT count(*) AS n
        FROM raw.hris_movements mv
        JOIN analytics.d_employee e ON e.employee_id = mv.employee_id
        WHERE NOT EXISTS (SELECT 1 FROM analytics.f_headcount f
                          WHERE f.employee_key = e.employee_key)
    """)["n"].iloc[0]

    assert loaded + unattributable == len(raw_movements), (
        f"{len(raw_movements) - loaded - unattributable} movement rows went missing "
        "for a reason nobody wrote down"
    )
    assert unattributable == 77, (
        f"{unattributable} events cannot be attributed to a position, not 77. "
        "The exclusion is deliberate but its size is not supposed to move."
    )


def test_movement_events_are_attributed_to_the_position_held_at_the_time(conn):
    """The keys point at the snapshot on or before the event, not at a random one.

    An exit in March belongs to the March organisation. Reading the keys off the
    employee's final surviving row gives the same answer for someone who never
    moved and the wrong one for everybody else.
    """
    misattributed = query(conn, """
        SELECT count(*) AS n
        FROM analytics.f_movement m
        JOIN LATERAL (
            SELECT f.job_key, f.location_key, f.org_key, f.company_key
            FROM analytics.f_headcount f
            WHERE f.employee_key = m.employee_key
              AND f.snapshot_date_key <= m.event_date_key
            ORDER BY f.snapshot_date_key DESC LIMIT 1
        ) expected ON true
        WHERE (m.job_key, m.location_key, m.org_key, m.company_key)
           IS DISTINCT FROM
              (expected.job_key, expected.location_key, expected.org_key, expected.company_key)
    """)["n"].iloc[0]
    assert misattributed == 0, f"{misattributed} events carry the wrong position"


def test_no_orphan_surrogate_keys(conn):
    orphans = query(conn, """
        SELECT
          count(*) FILTER (WHERE d.date_key     IS NULL) AS missing_date,
          count(*) FILTER (WHERE e.employee_key IS NULL) AS missing_employee,
          count(*) FILTER (WHERE j.job_key      IS NULL) AS missing_job,
          count(*) FILTER (WHERE o.org_key      IS NULL) AS missing_org,
          count(*) FILTER (WHERE l.location_key IS NULL) AS missing_location,
          count(*) FILTER (WHERE c.company_key  IS NULL) AS missing_company
        FROM analytics.f_headcount f
        LEFT JOIN analytics.d_date     d ON d.date_key     = f.snapshot_date_key
        LEFT JOIN analytics.d_employee e ON e.employee_key = f.employee_key
        LEFT JOIN analytics.d_job      j ON j.job_key      = f.job_key
        LEFT JOIN analytics.d_org      o ON o.org_key      = f.org_key
        LEFT JOIN analytics.d_location l ON l.location_key = f.location_key
        LEFT JOIN analytics.d_company  c ON c.company_key  = f.company_key
    """).iloc[0]
    assert orphans.sum() == 0, f"unresolved dimension keys: {orphans[orphans > 0].to_dict()}"


def test_date_dimension_is_contiguous_and_covers_the_facts(conn):
    row = query(conn, """
        SELECT count(*) AS days, min(date) AS from_date, max(date) AS to_date FROM analytics.d_date
    """).iloc[0]
    span = (row["to_date"] - row["from_date"]).days + 1
    assert row["days"] == span, "the date dimension has gaps"

    uncovered = query(conn, """
        SELECT count(*) AS n FROM analytics.f_headcount f
        LEFT JOIN analytics.d_date d ON d.date_key = f.snapshot_date_key
        WHERE d.date_key IS NULL
    """)["n"].iloc[0]
    assert uncovered == 0, "fact dates fall outside the calendar"


def test_currency_conversion_matches_an_independent_calculation(conn, raw_headcount, raw_fx):
    """SQL divides local pay by the constant rate. Recompute it in pandas and compare."""
    constant = raw_fx.groupby("currency_code")["rate_local_per_usd_constant"].first()
    expected = raw_headcount.assign(
        usd=raw_headcount["base_salary_local"] / raw_headcount["currency_code"].map(constant)
    )["usd"].sum()

    actual = query(conn, """
        SELECT sum(base_salary_usd_constant) AS total FROM analytics.f_headcount
    """)["total"].iloc[0]

    assert abs(actual - expected) < 1.0, (
        f"constant-currency payroll differs: SQL {actual:,.2f} vs pandas {expected:,.2f}"
    )


def test_currency_effect_is_material_where_the_local_currency_weakened(conn):
    """The whole reason for holding two rates.

    Summed across all currencies and all months the effect largely cancels, which
    is exactly why a headline figure hides it. Cut to the region whose currencies
    depreciated, at the latest close, and it has to be both negative and material -
    otherwise constant currency would be an unnecessary complication.
    """
    row = query(conn, """
        SELECT sum(f.base_salary_usd_constant) AS constant,
               sum(f.base_salary_usd_actual)   AS actual
        FROM analytics.f_headcount f
        JOIN analytics.d_location l ON l.location_key = f.location_key
        WHERE l.region = 'LAC'
          AND f.snapshot_date_key = (SELECT max(snapshot_date_key) FROM analytics.f_headcount)
    """).iloc[0]
    effect = (row["actual"] - row["constant"]) / row["constant"]
    assert effect < -0.05, (
        f"LATAM payroll shows only a {effect:.1%} currency effect; "
        "constant currency would not be earning its place"
    )


def test_span_of_control_matches_an_independent_calculation(conn, raw_headcount):
    """SQL derives span from the manager self-reference. Recompute it in pandas."""
    expected = (raw_headcount.dropna(subset=["manager_id"])
                .groupby(["snapshot_date", "manager_id"]).size()
                .rename("direct_reports").reset_index())
    expected_total = expected["direct_reports"].sum()

    actual_total = query(conn, """
        SELECT sum(direct_reports) AS total FROM (
            SELECT count(*) AS direct_reports
            FROM analytics.f_headcount
            WHERE manager_employee_key IS NOT NULL
            GROUP BY snapshot_date_key, manager_employee_key) s
    """)["total"].iloc[0]

    assert actual_total == expected_total, (
        f"span of control differs: SQL {actual_total} vs pandas {expected_total}"
    )


def test_peer_percentile_is_bounded(conn):
    out_of_range = query(conn, """
        SELECT count(*) AS n FROM analytics.f_headcount
        WHERE peer_percentile IS NOT NULL AND (peer_percentile < 0 OR peer_percentile > 1)
    """)["n"].iloc[0]
    assert out_of_range == 0, "peer percentile outside the 0-1 range"


def test_peer_percentile_is_suppressed_below_five_peers(conn):
    """The minimum group size rule has to hold everywhere, not just on the report."""
    leaks = query(conn, """
        WITH peers AS (
            SELECT f.snapshot_date_key, l.city, j.job_code, j.job_level,
                   count(*) AS group_size,
                   count(f.peer_percentile) AS disclosed
            FROM analytics.f_headcount f
            JOIN analytics.d_job      j ON j.job_key = f.job_key
            JOIN analytics.d_location l ON l.location_key = f.location_key
            GROUP BY 1, 2, 3, 4)
        SELECT count(*) AS n FROM peers WHERE group_size < 5 AND disclosed > 0
    """)["n"].iloc[0]
    assert leaks == 0, f"{leaks} peer groups below five people disclose a percentile"


def test_target_cash_is_base_plus_variable(conn):
    mismatches = query(conn, """
        SELECT count(*) AS n FROM analytics.f_headcount
        WHERE abs(target_cash_usd_constant
                  - base_salary_usd_constant * (1 + variable_target_pct)) > 0.02
    """)["n"].iloc[0]
    assert mismatches == 0, f"{mismatches} rows where target cash does not equal base + variable"
