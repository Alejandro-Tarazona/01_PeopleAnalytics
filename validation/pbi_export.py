"""Read the segment scan exported from the semantic model.

Power BI Desktop has no XMLA endpoint without Premium capacity, so Python cannot
query the model directly. The bridge is a file: the model exports the scan, the
file is committed, and the reconciliation reads it. That makes this a golden-file
test — less automatic than querying the model live, and honest about it, which is
better than pretending the limitation is not there. docs/case/reconciliation.md
sets out what the arrangement does and does not prove.

The export is a CSV written by Power BI Desktop on a machine whose locale is not
guaranteed, and the two things that vary are independent of each other:

- the **column delimiter** — comma, semicolon or tab
- the **decimal separator** — full stop or comma

They are not linked, and assuming they are is how this module got it wrong the
first time. A Spanish install writes `city,job_code,...` with a comma delimiter and
then puts `"0,7352"` in the cells, quoted, with a comma decimal. Any rule of the
shape "if the delimiter is a comma then the decimal point is a full stop" reads
that as seven thousand three hundred and fifty two, and the reconciliation fails
with a number nobody can trace back to a regional setting.

So neither is guessed now. The delimiter is whichever one yields the expected
column names — knowable, because PowerBI/queries/segment_scan.dax says what they
are — and the decimal separator is inferred from the numbers themselves.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd

EXPORT_PATH = (Path(__file__).resolve().parents[1]
               / "data" / "exports" / "segment_scan_pbi.csv")

# Export column -> the name used everywhere else in the validation code. Keeping
# the mapping in one place means the DAX measures can be renamed without hunting
# through the tests.
COLUMNS = {
    "city": "city",
    "job_code": "job_code",
    "job_level": "job_level",
    "Headcount": "headcount",
    "Average Headcount LTM": "avg_headcount_ltm",
    "Voluntary Exits LTM": "voluntary_exits_ltm",
    "Expected Exits LTM": "expected_exits_ltm",
    "Attrition vs Baseline": "attrition_vs_baseline",
    "Attrition p-value": "attrition_p_value",
    "Weighted Average TTC Compa-Ratio": "ttc_compa_ratio",
    "Average Span of Control": "avg_span_of_control",
    "Incumbent Headcount": "incumbent_count",
    "Incumbent Peer Percentile": "incumbent_percentile",
    "Recent Hire Headcount": "recent_hire_count",
    "Recent Hire Peer Percentile": "recent_hire_percentile",
    "Flag Pay Adjustment": "flag_pay_adjustment",
    "Flag Internal Equity": "flag_internal_equity",
    "Flag Organisational": "flag_organisational",
}

TEXT_COLUMNS = ["city", "job_code", "job_level"]

# Decimal places each measure's format string carries into the export. The
# reconciliation compares to exactly this precision: the export cannot be more
# accurate than what it was formatted to, and demanding more would fail on
# rounding rather than on disagreement.
DECIMALS = {
    "headcount": 0,
    "avg_headcount_ltm": 2,
    "voluntary_exits_ltm": 0,
    "expected_exits_ltm": 4,
    "attrition_vs_baseline": 2,
    "attrition_p_value": 6,
    "ttc_compa_ratio": 2,
    "avg_span_of_control": 1,
    "incumbent_count": 0,
    "incumbent_percentile": 4,
    "recent_hire_count": 0,
    "recent_hire_percentile": 4,
    "flag_pay_adjustment": 0,
    "flag_internal_equity": 0,
    "flag_organisational": 0,
}

FLAGS = ["flag_pay_adjustment", "flag_internal_equity", "flag_organisational"]

DELIMITERS = [",", ";", "\t", "|"]

# One number: optional sign, digits, and any mix of grouping and decimal separators.
_NUMBER = re.compile(r"^[+-]?\d+(?:[.,]\d+)*$")

# Whatever the export may have wrapped a number in.
_ORNAMENTS = ["$", "%", "US", "\u20ac", "\u00a3", " ", "\u00a0", "\u202f"]


def _clean(value: object) -> str:
    """Strip a cell down to digits and separators. Empty string where there is no number."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    for ornament in _ORNAMENTS:
        text = text.replace(ornament, "")
    return "" if text in ("", "-", "\u2014") else text


def _read_with(path: Path, delimiter: str) -> pd.DataFrame | None:
    """Read the file with one delimiter, or None if it does not produce the contract."""
    try:
        frame = pd.read_csv(path, sep=delimiter, encoding="utf-8-sig", dtype=str,
                            keep_default_na=False, na_values=[""])
    except (pd.errors.ParserError, UnicodeDecodeError):
        return None
    return frame if all(column in frame.columns for column in COLUMNS) else None


def _detect_decimal_separator(values: Iterable[str]) -> str:
    """Infer the decimal separator from the numbers, not from the delimiter.

    Three kinds of evidence, in descending strength:

    1. A value holding **both** separators settles it outright: the rightmost one
       is the decimal point, because grouping never comes after it. `1.234,56`
       can only be a comma decimal.
    2. A value holding one separator followed by a run of digits that is **not**
       three long settles it too: `70.67` and `0,7352` are decimals, because a
       thousands group is always exactly three digits.
    3. A separator appearing **more than once** in one value is grouping, so the
       other one is the decimal.

    Anything else — `1,234` alone — is genuinely ambiguous and casts no vote. With
    sixteen numeric columns and eleven rows there is always ample evidence; the
    tie-break is a full stop, which is what an unformatted export produces.
    """
    votes = {".": 0, ",": 0}
    for text in values:
        if not _NUMBER.match(text):
            continue
        dots, commas = text.count("."), text.count(",")
        if dots and commas:
            votes["." if text.rfind(".") > text.rfind(",") else ","] += 1
        elif dots > 1:
            votes[","] += 1
        elif commas > 1:
            votes["."] += 1
        elif dots == 1 and len(text.rsplit(".", 1)[1]) != 3:
            votes["."] += 1
        elif commas == 1 and len(text.rsplit(",", 1)[1]) != 3:
            votes[","] += 1
    return "," if votes[","] > votes["."] else "."


def _to_number(text: str, decimal: str) -> float:
    """Parse one cleaned cell, given which character is the decimal point."""
    if not text:
        return float("nan")
    grouping = "," if decimal == "." else "."
    try:
        return float(text.replace(grouping, "").replace(decimal, "."))
    except ValueError:
        return float("nan")


def load_export(path: Path | None = None) -> pd.DataFrame:
    """Load the exported scan, normalised to the names and types used in tests."""
    path = EXPORT_PATH if path is None else path

    frame = next((f for f in (_read_with(path, d) for d in DELIMITERS) if f is not None), None)
    if frame is None:
        header = path.read_text(encoding="utf-8-sig").splitlines()[:1]
        raise ValueError(
            f"no delimiter in {DELIMITERS!r} parses {path.name} into the expected "
            f"columns.\nIts header line is: {header}\n"
            "The export must match PowerBI/queries/segment_scan.dax exactly."
        )
    frame = frame[list(COLUMNS)].rename(columns=COLUMNS)

    numeric = [column for column in frame.columns if column not in TEXT_COLUMNS]
    cleaned = {column: frame[column].map(_clean) for column in numeric}
    decimal = _detect_decimal_separator(
        text for column in numeric for text in cleaned[column])

    for column in frame.columns:
        if column in TEXT_COLUMNS:
            # fillna before str: an empty cell read as NaN would otherwise become
            # the literal string "nan", which is not blank and not a city either.
            frame[column] = frame[column].fillna("").astype(str).str.strip()
        else:
            frame[column] = cleaned[column].map(lambda t: _to_number(t, decimal))

    # A count of zero comes back from DAX as a blank cell, not as a nought.
    # Reading it as missing and then comparing it against the reference's 0 would
    # fail on a difference that is not there.
    for column in FLAGS + ["voluntary_exits_ltm", "incumbent_count", "recent_hire_count"]:
        frame[column] = frame[column].fillna(0)

    # A totals row leaves the key columns empty, or fills them with whatever the
    # install calls a total. Either way it is not a cell and is dropped rather than
    # compared against one that does not exist.
    #
    # The export page has its totals switched off, so this should never fire. It is
    # here because a table visual turns them back on the moment somebody rebuilds the
    # page from the field list, and the failure that produces - one unmatched row, in
    # a test about attrition - sends whoever hits it looking in the wrong place
    # entirely.
    labels = {"", "total", "totales", "total general", "grand total"}
    is_total = False
    for column in TEXT_COLUMNS:
        is_total = is_total | frame[column].str.strip().str.lower().isin(labels)
    if is_total.any():
        frame = frame[~is_total]

    return frame.sort_values(TEXT_COLUMNS).reset_index(drop=True)


def tolerance(column: str) -> float:
    """Half a unit in the export's last decimal place, plus room for float dust."""
    return 0.5 * 10 ** -DECIMALS[column] + 1e-9
