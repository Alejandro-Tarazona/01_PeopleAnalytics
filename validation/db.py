"""Database access for the validation suite.

Connection parameters come from the standard libpq environment variables
(PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD). Nothing is hard-coded and no
credential reaches the repository.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pandas as pd
import psycopg

# Defaults applied only when the variable is not already set, so anyone can
# override any of them from their own environment. PGUSER is included on purpose:
# without it libpq falls back to the operating-system user name, which is not a
# PostgreSQL role and produces a confusing "no password supplied" error.
DEFAULTS = {
    "PGHOST": "localhost",
    "PGPORT": "5432",
    "PGDATABASE": "mpg_analytics",
    "PGUSER": "postgres",
}

# Connect to PostgreSQL
def connect() -> psycopg.Connection:
    """Open a connection using libpq environment variables."""
    # Open a connection to PostgreSQL using libpq environment variables.
    for key, value in DEFAULTS.items():
        os.environ.setdefault(key, value)
    return psycopg.connect()


# Run a query and return the result as a DataFrame.
# PostgreSQL NUMERIC arrives as decimal.Decimal, which does not mix with float in arithmetic.
# Converting once here keeps every caller free of casts.
def query(conn: psycopg.Connection, sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Run a query and return the result as a DataFrame, with NUMERIC cast to float."""
    # Execute the SQL query and fetch the results into a DataFrame.
    with conn.cursor() as cur:
        cur.execute(sql, params)                                        # Execute the SQL query with optional parameters
        columns = [c.name for c in cur.description]                     # Get the column names from the cursor description
        frame = pd.DataFrame(cur.fetchall(), columns=columns)           # Fetch all rows and create a DataFrame with the specified columns

    # Transform any columns that are of type object and contain Decimal values to float for easier arithmetic operations.
    for column in frame.columns:
        if frame[column].dtype == object:
            first = frame[column].dropna()
            if not first.empty and isinstance(first.iloc[0], Decimal):
                frame[column] = frame[column].astype(float)
    return frame
