"""Shared fixtures.

The suite runs against a built database. Connection settings come from the
standard libpq environment variables; see the README.

Scope note: Python's only job in this repository is validation. It recomputes
what SQL produced and compares. It does not produce findings — those come from
the semantic model.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from validation.bands import load_market_bands
from validation.db import connect

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


@pytest.fixture(scope="session")
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture(scope="session")
def bands() -> pd.DataFrame:
    return load_market_bands()


@pytest.fixture(scope="session")
def raw_headcount() -> pd.DataFrame:
    # keep_default_na=False: the region code NAM is safe, but several other
    # columns carry values pandas would otherwise read as missing.
    return pd.read_csv(RAW / "hris_headcount_monthly.csv", keep_default_na=False,
                       na_values=[""])


@pytest.fixture(scope="session")
def raw_employees() -> pd.DataFrame:
    return pd.read_csv(RAW / "hris_employees.csv", keep_default_na=False, na_values=[""])


@pytest.fixture(scope="session")
def raw_movements() -> pd.DataFrame:
    return pd.read_csv(RAW / "hris_movements.csv", keep_default_na=False, na_values=[""])


@pytest.fixture(scope="session")
def raw_fx() -> pd.DataFrame:
    return pd.read_csv(RAW / "fx_rates.csv", keep_default_na=False, na_values=[""])


@pytest.fixture(scope="session")
def raw_locations() -> pd.DataFrame:
    return pd.read_csv(RAW / "ref_locations.csv", keep_default_na=False, na_values=[""])
