"""Reference implementation of the segment prioritization rule.

The findings in this project come from the semantic model. This module does not
produce them: it re-implements the same specification a second time, in pandas,
so the model's output can be *checked* rather than believed.

That is the whole idea. `docs/case/detection-rule.md` is the specification. The
DAX measures are implementation one. This file is implementation two, written
against the specification rather than against the DAX, and the two are required
to agree cell for cell. Double-entry bookkeeping applied to an analytical rule:
a single implementation can only be inspected, two independent ones can be
reconciled.

It depends on pandas and the standard library, and nothing else. The Poisson tail
it needs lives in `poisson.py` rather than coming from scipy — see that module for
why, and for the second implementation that keeps the arithmetic honest.

What this module deliberately does NOT re-derive is the star schema itself —
currency conversion, span of control, peer percentiles. Those are validated in
tests/test_sql_layer.py, which recomputes them from the raw extracts. Repeating
that work here would test the same thing twice and leave the rule untested.
The boundary is: block 3 proves the inputs, block 6 proves the rule.

Thresholds and their justification: docs/case/detection-rule.md.
"""

from __future__ import annotations

import pandas as pd

from .bands import load_market_bands
from .db import query
from .poisson import survival

# --- Thresholds ---------------------------------------------------------------
# Every one of these is argued for in docs/case/detection-rule.md. They are
# constants here so that the DAX and this file can be compared line by line.
MIN_MATERIALITY = 30         # below this an intervention is a case, not a policy
ALPHA = 0.05                 # attrition must be distinguishable from the baseline
TTC_BELOW_MARKET = 0.92      # total target cash position that counts as below market
TTC_IN_BAND = 0.95           # at or above this, pay is not the explanation
SPAN_TOLERANCE = 1.5         # multiples of the company mean span
COMPRESSION_LOW = 0.35       # incumbent cohort at or below this peer percentile
COMPRESSION_HIGH = 0.65      # recent-hire cohort at or above this peer percentile
MIN_COHORT = 20              # minimum per cohort for the compression comparison
INCUMBENT_YEARS = 3          # tenure that separates an incumbent from a recent hire
LTM_MONTHS = 12

CELL = ["city", "job_code", "job_level"]

# The trailing-twelve-month window, defined once. Every query below reads it, so
# the exposure, the exits and the snapshot can never drift on to different bases —
# which is the most common way an attrition rate ends up quietly wrong.
_WINDOW_CTE = """
WITH window_months AS (
    SELECT snapshot_date_key
    FROM (SELECT DISTINCT snapshot_date_key FROM analytics.f_headcount
          ORDER BY snapshot_date_key DESC LIMIT %(months)s) w
)
"""

_SNAPSHOT_SQL = """
SELECT l.city, l.geo_tier, j.job_code, j.job_level,
       f.employee_key,
       f.base_salary_usd_constant,
       f.target_cash_usd_constant,
       f.variable_target_pct,
       f.span_of_manager,
       f.peer_percentile,
       (d.date - e.hire_date) / 365.25 AS tenure_years
FROM analytics.f_headcount f
JOIN analytics.d_date     d ON d.date_key = f.snapshot_date_key
JOIN analytics.d_employee e ON e.employee_key = f.employee_key
JOIN analytics.d_job      j ON j.job_key = f.job_key
JOIN analytics.d_location l ON l.location_key = f.location_key
WHERE f.snapshot_date_key = (SELECT max(snapshot_date_key) FROM analytics.f_headcount)
"""

_EXPOSURE_SQL = _WINDOW_CTE + """
SELECT l.city, j.job_code, j.job_level,
       count(*)::numeric / %(months)s AS avg_headcount_ltm
FROM analytics.f_headcount f
JOIN analytics.d_job      j ON j.job_key = f.job_key
JOIN analytics.d_location l ON l.location_key = f.location_key
WHERE f.snapshot_date_key IN (SELECT snapshot_date_key FROM window_months)
GROUP BY 1, 2, 3
"""

# The company baseline the DAX measure resolves to: total exits over total exposure,
# with every filter removed. Deriving it by summing the cell table instead would make
# it quietly dependent on which cells survived the joins - which is exactly how the
# first version of this file lost one exit and moved the baseline in the fourth
# decimal, far enough to shift a p-value.
_COMPANY_SQL = _WINDOW_CTE + """
SELECT (SELECT count(*) FROM analytics.f_movement m
        WHERE m.is_voluntary_exit
          AND m.event_date_key IN (SELECT snapshot_date_key FROM window_months))
       AS voluntary_exits_ltm,
       (SELECT count(*)::numeric / %(months)s FROM analytics.f_headcount f
        WHERE f.snapshot_date_key IN (SELECT snapshot_date_key FROM window_months))
       AS avg_headcount_ltm
"""

# Exits are attributed through the movement fact's own dimension keys - the position
# the person held when they left - not through their last surviving headcount row.
# The two agree for someone who never moved and differ for everybody else.
_EXITS_SQL = _WINDOW_CTE + """
SELECT l.city, j.job_code, j.job_level, count(*) AS voluntary_exits_ltm
FROM analytics.f_movement m
JOIN analytics.d_job      j ON j.job_key = m.job_key
JOIN analytics.d_location l ON l.location_key = m.location_key
WHERE m.is_voluntary_exit
  AND m.event_date_key IN (SELECT snapshot_date_key FROM window_months)
GROUP BY 1, 2, 3
"""


def segment_scan(conn, bands: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the city x job x level table the three rules are evaluated against.

    One row per cell in the organization. The rule does not know the four
    designed segments exist, which is what makes scoring it meaningful.
    """
    bands = load_market_bands() if bands is None else bands
    params = {"months": LTM_MONTHS}
    people = query(conn, _SNAPSHOT_SQL)
    exposure = query(conn, _EXPOSURE_SQL, params)
    exits = query(conn, _EXITS_SQL, params)
    company = query(conn, _COMPANY_SQL, params).iloc[0]

    people = people.merge(
        bands[["job_code", "job_level", "geo_tier",
               "band_min_usd", "band_mid_usd", "market_variable_pct"]],
        on=["job_code", "job_level", "geo_tier"], how="left", validate="many_to_one",
    )
    if people["band_mid_usd"].isna().any():
        missing = people.loc[people["band_mid_usd"].isna(), CELL].drop_duplicates()
        raise ValueError(f"no market band for {len(missing)} job/level/tier combinations")

    # Market total cash for the same population, so the ratio below is a weighted
    # average and not an average of per-person ratios. For a group of mixed
    # seniority those two numbers differ enough to change a recommendation.
    people["market_mid_usd"] = people["band_mid_usd"]
    people["market_ttc_usd"] = people["band_mid_usd"] * (1 + people["market_variable_pct"])
    people["below_band"] = people["base_salary_usd_constant"] < people["band_min_usd"]
    people["is_incumbent"] = people["tenure_years"] >= INCUMBENT_YEARS

    cells = people.groupby(CELL, as_index=False).agg(
        headcount=("employee_key", "size"),
        pay_usd=("base_salary_usd_constant", "sum"),
        target_cash_usd=("target_cash_usd_constant", "sum"),
        market_mid_usd=("market_mid_usd", "sum"),
        market_ttc_usd=("market_ttc_usd", "sum"),
        share_below_band=("below_band", "mean"),
        avg_span_of_control=("span_of_manager", "mean"),
    )
    cells["compa_ratio"] = cells["pay_usd"] / cells["market_mid_usd"]
    cells["ttc_compa_ratio"] = cells["target_cash_usd"] / cells["market_ttc_usd"]

    # Rule 2 works on cohorts, not on the cell average - that is the entire point
    # of it. A peer percentile is blank where the peer group is under five people,
    # and those rows are excluded rather than treated as zero.
    rated = people.dropna(subset=["peer_percentile"])
    cohorts = rated.groupby(CELL + ["is_incumbent"], as_index=False).agg(
        n=("employee_key", "size"), mean_percentile=("peer_percentile", "mean"),
    )
    incumbents = (cohorts[cohorts["is_incumbent"]].drop(columns="is_incumbent")
                  .rename(columns={"n": "incumbent_count",
                                   "mean_percentile": "incumbent_percentile"}))
    recent = (cohorts[~cohorts["is_incumbent"]].drop(columns="is_incumbent")
              .rename(columns={"n": "recent_hire_count",
                               "mean_percentile": "recent_hire_percentile"}))

    # Outer on both, deliberately. A cell can hold exits and no exposure - one person
    # here left the snapshot roll a year before their exit was recorded - and an inner
    # or left join would drop them without a word. They are kept, they fail the
    # materiality floor, and the assertion below makes sure none went missing.
    cells = (cells
             .merge(exposure, on=CELL, how="outer")
             .merge(exits, on=CELL, how="outer")
             .merge(incumbents, on=CELL, how="left")
             .merge(recent, on=CELL, how="left"))
    for column in ("voluntary_exits_ltm", "incumbent_count", "recent_hire_count"):
        cells[column] = cells[column].fillna(0).astype(int)
    cells["avg_headcount_ltm"] = cells["avg_headcount_ltm"].fillna(0.0)

    if cells["voluntary_exits_ltm"].sum() != company["voluntary_exits_ltm"]:
        raise ValueError(
            f"the cell table accounts for {cells['voluntary_exits_ltm'].sum()} exits "
            f"but the company had {company['voluntary_exits_ltm']}"
        )

    # The company baseline, on exactly the same exposure basis as the cells. A rate
    # built on closing headcount and compared against one built on average headcount
    # is the classic way to manufacture a signal that is not there.
    baseline_rate = company["voluntary_exits_ltm"] / company["avg_headcount_ltm"]
    company_span = people["span_of_manager"].mean()

    cells["attrition_ltm"] = cells["voluntary_exits_ltm"] / cells["avg_headcount_ltm"]
    cells["attrition_vs_baseline"] = cells["attrition_ltm"] / baseline_rate
    cells["expected_exits_ltm"] = baseline_rate * cells["avg_headcount_ltm"]
    # One-sided Poisson survival: how likely is this many exits, or more, if the
    # cell ran at the company rate? Replaces an arbitrary "1.5x the baseline",
    # which at these population sizes sits comfortably inside the noise - the
    # arithmetic is tabulated in docs/case/detection-rule.md.
    # Where a cell has no exposure the rate is undefined, not extreme - survival()
    # returns NaN there rather than a p-value of zero, which would make the emptiest
    # cell in the company read as the most significant thing in it. The DAX returns
    # BLANK() for the same case; both have to agree on saying nothing.
    cells["attrition_p_value"] = [
        survival(int(exits), float(expected))
        for exits, expected in zip(cells["voluntary_exits_ltm"], cells["expected_exits_ltm"])
    ]

    cells["flag_pay_adjustment"] = _rule_pay_adjustment(cells, company_span)
    cells["flag_internal_equity"] = _rule_internal_equity(cells)
    cells["flag_organizational"] = _rule_organizational(cells, company_span)

    cells.attrs["baseline_rate"] = baseline_rate
    cells.attrs["company_mean_span"] = company_span
    return cells.sort_values(CELL).reset_index(drop=True)


def _material(cells: pd.DataFrame) -> pd.Series:
    """Large enough for the answer to be a policy rather than a conversation."""
    return cells["avg_headcount_ltm"] >= MIN_MATERIALITY


def _significant(cells: pd.DataFrame) -> pd.Series:
    """Materially sized, and losing people faster than chance explains."""
    return _material(cells) & (cells["attrition_p_value"] < ALPHA)


def _rule_pay_adjustment(cells: pd.DataFrame, company_span: float) -> pd.Series:
    """Below market on total cash, with attrition to match and no org explanation."""
    return (_significant(cells)
            & (cells["ttc_compa_ratio"] < TTC_BELOW_MARKET)
            & (cells["avg_span_of_control"] <= company_span * SPAN_TOLERANCE))


def _rule_internal_equity(cells: pd.DataFrame) -> pd.Series:
    """Incumbents have fallen behind the recent hires sitting next to them.

    No significance test: this compares positions inside a fixed population
    rather than a rate estimated from counts, so Poisson noise does not apply.
    """
    return ((cells["incumbent_count"] >= MIN_COHORT)
            & (cells["recent_hire_count"] >= MIN_COHORT)
            & (cells["incumbent_percentile"] <= COMPRESSION_LOW)
            & (cells["recent_hire_percentile"] >= COMPRESSION_HIGH))


def _rule_organizational(cells: pd.DataFrame, company_span: float) -> pd.Series:
    """Attrition is real, pay is not the cause, span of control is."""
    return (_significant(cells)
            & (cells["ttc_compa_ratio"] >= TTC_IN_BAND)
            & (cells["avg_span_of_control"] > company_span * SPAN_TOLERANCE))


def flagged_cells(scan: pd.DataFrame) -> pd.DataFrame:
    """Long-form view: one row per cell per rule that fired."""
    rules = {"pay_adjustment": "flag_pay_adjustment",
             "internal_equity": "flag_internal_equity",
             "organizational": "flag_organizational"}
    parts = [scan[scan[column]].assign(rule=name) for name, column in rules.items()]
    return (pd.concat(parts, ignore_index=True)
            .sort_values(["rule"] + CELL).reset_index(drop=True))
