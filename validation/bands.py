"""Cleansing of the market salary survey.

The vendor file arrives the way salary surveys actually arrive: preamble rows
above the header, amounts stored as currency-formatted text, stray whitespace in
job codes, inconsistent level spelling, duplicate rows and a footer note.

This module is one of two independent implementations of that cleansing. The
other lives in Power Query inside the semantic model, and the two are expected to
agree exactly — the reconciliation in block 6 is what proves it. Two
implementations of the same rule that must match is double-entry bookkeeping
applied to data.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

PATH_MARKET_BANDS = Path(__file__).resolve().parent.parent / "data" / "raw" / "market_bands.xlsx"

COLUMNS = {
    "Job Code": "job_code",
    "Job Family": "job_family",
    "Job Level": "job_level",
    "Track": "track",
    "Geo Tier": "geo_tier",
    "Band Min": "band_min_usd",
    "Band Mid": "band_mid_usd",
    "Band Max": "band_max_usd",
    "Variable Target %": "market_variable_pct",
    "Survey Year": "survey_year",
}

#Parse an amount that may arrive as a number or as '$120,000'.
def _to_amount(value) -> float:
    """Parse an amount that may arrive as a number or as currency-formatted text."""
    if isinstance(value, str):
        return float(re.sub(r"[^0-9.]", "", value))
    
    return float(value)

# Locate the real header row beneath the vendor's preamble.
def _header_row() -> int:
    """Locate the real header row beneath the vendor's preamble."""
    preview = pd.read_excel(PATH_MARKET_BANDS, header=None, nrows=15)
    matches = preview.index[preview[0].astype(str).str.strip() == "Job Code"]

    if len(matches) == 0:
        raise ValueError(f"No header row found in {PATH_MARKET_BANDS}: expected a cell reading 'Job Code'")
    return int(matches[0])

# Return the salary survey as a clean, deduplicated, typed table.
def load_market_bands() -> pd.DataFrame:
    """Return the salary survey as a clean, deduplicated, typed table."""
    raw = pd.read_excel(PATH_MARKET_BANDS, header=_header_row())                       # Read the Excel file, using the located header row to define column names

    df = raw.rename(columns=COLUMNS)                                                                    # Rename the columns of the DataFrame according to the COLUMNS mapping
    df = df[list(COLUMNS.values())]                                                                     # Keep only the columns specified in the COLUMNS mapping, discarding any extra columns that may be present in the raw data

    
    df = df.dropna(subset=["job_code"])                                                                 # Drop any rows where the "job_code" column is NaN (missing), as these rows are considered trailing blank rows that carry no job code
    df["job_code"] = df["job_code"].astype(str).str.strip()                                             # Convert the "job_code" column to string type and strip any leading or trailing whitespace from the values in that column

    # The vendor's footer note sits in the job code column. Keeping only rows
    # whose code matches the catalog's shape removes it without hard-coding
    # the note's text, which the vendor is free to change between editions.
    
    df = df[df["job_code"].str.fullmatch(r"[A-Z]{3}")]                                                  # Keep only rows where the "job_code" column matches the regular expression pattern "[A-Z]{3}", which means the job code consists of exactly three uppercase letters. This filters out any rows that do not conform to this expected format, including the vendor's footer note that may be present in the job code column.

    # Clean and type the remaining columns, converting amounts to floats and ensuring consistent formatting for job levels and other categorical fields.

    df["job_family"] = df["job_family"].astype(str).str.strip()                                         # Convert the "job_family" column to string type and strip any leading or trailing whitespace from the values in that column                                    
    df["track"] = df["track"].astype(str).str.strip()                                                   # Convert the "track" column to string type and strip any leading or trailing whitespace from the values in that column
    df["geo_tier"] = df["geo_tier"].astype(str).str.strip()                                             # Convert the "geo_tier" column to string type and strip any leading or trailing whitespace from the values in that column

    # "IC 3" and "IC3" are the same level written two ways.
    df["job_level"] = df["job_level"].astype(str).str.replace(" ", "", regex=False).str.strip()         # Convert the "job_level" column to string type, remove any spaces from the values in that column, and strip any leading or trailing whitespace. This ensures that variations like "IC 3" and "IC3" are treated as the same level by standardizing the formatting of job levels.

    for column in ("band_min_usd", "band_mid_usd", "band_max_usd"):
        df[column] = df[column].map(_to_amount)                                                          # Convert the values in the specified columns ("band_min_usd", "band_mid_usd", "band_max_usd") to float amounts using the to_amount function, which handles both numeric and currency-formatted string representations of amounts.

    df["market_variable_pct"] = df["market_variable_pct"].astype(float)                                 # Convert the "market_variable_pct" column to float type, ensuring that the values in this column are treated as numeric percentages for further analysis.
    df["survey_year"] = df["survey_year"].astype(int)                                                   # Convert the "survey_year" column to integer type, ensuring that the values in this column are treated as whole numbers representing the year of the survey.

    df = df.drop_duplicates(subset=["job_code", "job_level", "geo_tier"], keep="first")                 # Drop any duplicate rows in the DataFrame based on the combination of "job_code", "job_level", and "geo_tier" columns, keeping only the first occurrence of each unique combination. This ensures that the resulting DataFrame contains only distinct entries for each job code, level, and geographic tier.

    return df.sort_values(["job_code", "job_level", "geo_tier"]).reset_index(drop=True)                 # Sort the DataFrame by "job_code", "job_level", and "geo_tier" columns in ascending order, and reset the index of the DataFrame to create a new sequential index while dropping the old index. This provides a clean and organized DataFrame that is ready for further analysis or processing.
