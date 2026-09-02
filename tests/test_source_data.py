"""Level 1 - source validation.

Answers one question: can the extracts be trusted before anything is built on
top of them? Every assertion here would catch a real production incident, not a
hypothetical one.
"""

from __future__ import annotations

import pandas as pd

VALID_EVENTS = {"Hire", "Merit Increase", "Promotion", "Voluntary Exit",
                "Involuntary Exit", "Span Rebalance"}
VALID_REGIONS = {"NAM", "LAC", "EMEA", "APAC"}


# --- Referential integrity ----------------------------------------------------

def test_every_snapshot_employee_exists_in_the_master(raw_headcount, raw_employees):
    orphans = set(raw_headcount["employee_id"]) - set(raw_employees["employee_id"])
    assert not orphans, f"{len(orphans)} employees appear in snapshots but not in the master"


def test_every_movement_employee_exists_in_the_master(raw_movements, raw_employees):
    orphans = set(raw_movements["employee_id"]) - set(raw_employees["employee_id"])
    assert not orphans, f"{len(orphans)} employees have movements but no master record"


def test_every_manager_is_an_employee(raw_headcount, raw_employees):
    managers = set(raw_headcount["manager_id"].dropna())
    orphans = managers - set(raw_employees["employee_id"])
    assert not orphans, f"{len(orphans)} manager ids do not resolve to an employee"


def test_every_city_exists_in_the_location_master(raw_headcount, raw_locations):
    orphans = set(raw_headcount["city"]) - set(raw_locations["city"])
    assert not orphans, f"cities missing from the location master: {sorted(orphans)}"


def test_every_currency_has_a_full_rate_series(raw_headcount, raw_fx):
    months = raw_fx["date"].nunique()
    per_currency = raw_fx.groupby("currency_code").size()
    assert (per_currency == months).all(), "a currency is missing exchange rates for some months"
    orphans = set(raw_headcount["currency_code"]) - set(raw_fx["currency_code"])
    assert not orphans, f"currencies with no exchange rate: {sorted(orphans)}"


# --- Grain and domains --------------------------------------------------------

def test_snapshot_grain_is_unique(raw_headcount):
    duplicates = raw_headcount.duplicated(["employee_id", "snapshot_date"]).sum()
    assert duplicates == 0, f"{duplicates} duplicated employee-month rows"


def test_event_types_are_within_the_closed_domain(raw_movements):
    unexpected = set(raw_movements["event_type"]) - VALID_EVENTS
    assert not unexpected, f"unexpected event types: {sorted(unexpected)}"


def test_region_codes_are_within_the_closed_domain(raw_locations):
    unexpected = set(raw_locations["region"]) - VALID_REGIONS
    assert not unexpected, f"unexpected region codes: {sorted(unexpected)}"


# --- Values -------------------------------------------------------------------

def test_no_missing_or_non_positive_salaries(raw_headcount):
    assert raw_headcount["base_salary_local"].notna().all(), "missing salaries in the snapshot"
    assert (raw_headcount["base_salary_local"] > 0).all(), "zero or negative salaries"


def test_fte_is_within_range(raw_headcount):
    assert raw_headcount["fte"].between(0.1, 1.0).all(), "FTE outside the 0.1-1.0 range"


def test_variable_target_is_a_proportion(raw_headcount):
    assert raw_headcount["variable_target_pct"].between(0, 1).all(), \
        "variable target is not expressed as a proportion"


# --- Temporal coherence -------------------------------------------------------

def test_nobody_appears_in_a_snapshot_before_being_hired(raw_headcount, raw_employees):
    merged = raw_headcount.merge(raw_employees[["employee_id", "hire_date"]], on="employee_id")
    early = merged[pd.to_datetime(merged["snapshot_date"]) < pd.to_datetime(merged["hire_date"])]
    assert early.empty, f"{len(early)} snapshot rows predate the employee's hire date"


def test_nobody_appears_in_a_snapshot_after_leaving(raw_headcount, raw_employees):
    leavers = raw_employees.dropna(subset=["exit_date"])
    merged = raw_headcount.merge(leavers[["employee_id", "exit_date"]], on="employee_id")
    late = merged[pd.to_datetime(merged["snapshot_date"]) > pd.to_datetime(merged["exit_date"])]
    assert late.empty, f"{len(late)} snapshot rows follow the employee's exit date"


# --- The vendor salary survey -------------------------------------------------

def test_band_grid_is_complete(bands):
    expected = bands["job_code"].nunique() * bands["job_level"].nunique() * bands["geo_tier"].nunique()
    assert len(bands) == expected, "the cleansed survey is not a complete job x level x tier grid"


def test_band_bounds_are_ordered(bands):
    assert (bands["band_min_usd"] < bands["band_mid_usd"]).all()
    assert (bands["band_mid_usd"] < bands["band_max_usd"]).all()


def test_cleansing_removed_duplicates_and_footer(bands):
    assert not bands.duplicated(["job_code", "job_level", "geo_tier"]).any(), \
        "the vendor's duplicate row survived cleansing"
    assert bands["job_code"].str.fullmatch(r"[A-Z]{3}").all(), \
        "the footer note survived cleansing"


def test_cleansing_normalized_levels_and_codes(bands):
    assert not bands["job_level"].str.contains(" ").any(), "levels still contain 'IC 3' spacing"
    assert (bands["job_code"] == bands["job_code"].str.strip()).all(), \
        "job codes still carry stray whitespace"


def test_currency_formatted_text_was_parsed(bands):
    for column in ("band_min_usd", "band_mid_usd", "band_max_usd"):
        assert bands[column].dtype.kind == "f", f"{column} is not numeric after cleansing"
        assert (bands[column] > 0).all()


def test_every_job_and_level_in_the_snapshot_has_a_band(raw_headcount, raw_locations, bands):
    merged = raw_headcount.merge(raw_locations[["city", "geo_tier"]], on="city")
    keys = merged[["job_code", "job_level", "geo_tier"]].drop_duplicates()
    matched = keys.merge(bands, on=["job_code", "job_level", "geo_tier"], how="left")
    missing = matched[matched["band_mid_usd"].isna()]
    assert missing.empty, f"{len(missing)} job/level/tier combinations have no market band"
