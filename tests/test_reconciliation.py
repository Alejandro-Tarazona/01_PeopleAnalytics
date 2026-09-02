"""Block 6 — reconciliation and scoring.

Two questions, asked in this order, because the second is worthless without the
first:

  1. Does the semantic model agree with an independent implementation of the same
     specification? If the DAX and validation/reference_rule.py disagree, at least
     one of them is wrong and no score means anything.

  2. Given that they agree, does the rule find what is actually there? Precision
     and recall are scored against docs/case/ground_truth.json — the answer key
     written before the data existed.

This is the reason the project uses synthetic data. On real data an analysis can
only be described; here it can be marked.

The tests read data/exports/segment_scan_pbi.csv, produced by the model. They skip
with instructions when that file is absent rather than failing, because a missing
export means the model has not been refreshed yet, not that anything is broken.
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path

import pytest

from validation.pbi_export import (COLUMNS, DECIMALS, EXPORT_PATH, FLAGS,
                                   _detect_decimal_separator, load_export, tolerance)
from validation.poisson import survival, survival_by_recurrence
from validation.reference_rule import (ALPHA, CELL, MIN_MATERIALITY,
                                       flagged_cells, segment_scan)

GROUND_TRUTH = Path(__file__).resolve().parents[1] / "docs" / "case" / "ground_truth.json"

NO_EXPORT = f"""\
{EXPORT_PATH.name} not found.

Refresh the semantic model, open the "Segment scan (export)" page, and export the
table visual to data/exports/{EXPORT_PATH.name}. The columns it must contain are
defined in PowerBI/queries/segment_scan.dax.
"""

needs_export = pytest.mark.skipif(not EXPORT_PATH.exists(), reason=NO_EXPORT)

RULES = {"pay_adjustment": "flag_pay_adjustment",
         "internal_equity": "flag_internal_equity",
         "organizational": "flag_organizational"}


@pytest.fixture(scope="session")
def truth() -> dict:
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def reference(conn, bands):
    """The rule, implemented a second time in pandas, at the export's grain."""
    scan = segment_scan(conn, bands)
    material = scan[scan["avg_headcount_ltm"] >= MIN_MATERIALITY]
    return material.sort_values(CELL).reset_index(drop=True)


@pytest.fixture(scope="session")
def exported():
    return load_export()


@pytest.fixture(scope="session")
def paired(exported, reference):
    """Export and reference, joined cell to cell. Everything below reads this."""
    return exported.merge(reference, on=CELL, how="outer",
                          suffixes=("_pbi", "_ref"), indicator=True)


def _segment_of(row, truth) -> dict | None:
    """The designed segment a cell falls inside, if any."""
    for segment in truth["segments"]:
        definition = segment["definition"]
        if (row["city"] == definition["city"]
                and row["job_code"] == definition["job_code"]
                and row["job_level"] in definition["job_levels"]):
            return segment
    return None


# --- 0 · Is the arithmetic itself right? --------------------------------------
# Everything below rests on one function. Removing scipy removed the outside
# authority it used to be checked against, so the check lives here now: the same
# quantity computed by two algorithms that share no arithmetic.

@pytest.mark.parametrize("observed, expected, answer", [
    # P(X >= 1) = 1 - e^-1, the textbook value.
    (1, 1.0, 0.6321205588285577),
    # P(X >= 0) is certainty whatever the rate.
    (0, 13.5, 1.0),
    # A rate of one, ten events. Small enough to verify by hand, far enough into
    # the tail to catch a term-count that is off by one.
    (10, 1.0, 1.1142547833872021e-07),
])
def test_the_poisson_tail_matches_known_values(observed, expected, answer):
    assert survival(observed, expected) == pytest.approx(answer, rel=1e-12)


@pytest.mark.parametrize("expected", [0.1, 1.0, 4.7, 13.5, 100.0, 400.0])
def test_two_independent_algorithms_agree(expected):
    """Logarithms and lgamma against a plain ratio recurrence.

    One sums EXP(-lambda + k*LN(lambda) - LN(k!)); the other multiplies each term
    by lambda/k and never takes a logarithm at all. They share no step. Agreeing
    to 1e-12 across the range the model uses is strong evidence both are right,
    which is the job scipy used to do.
    """
    for observed in range(0, 60):
        by_logs = survival(observed, expected)
        by_ratio = survival_by_recurrence(observed, expected)
        assert by_logs == pytest.approx(by_ratio, abs=1e-12), (
            f"the two implementations disagree at observed={observed}, "
            f"expected={expected}: {by_logs} vs {by_ratio}"
        )


def test_the_tail_behaves_like_a_probability():
    """Monotone, bounded, and undefined rather than extreme where it has to be."""
    values = [survival(k, 13.5) for k in range(0, 40)]
    assert all(1.0 >= a >= b >= 0.0 for a, b in zip(values, values[1:])), (
        "P(X >= k) must fall as k rises and stay inside [0, 1]")
    assert math.isnan(survival(3, 0.0)), (
        "a cell with no exposure has an undefined rate, not a significant one")
    assert math.isnan(survival(3, float("nan")))


# --- 0b · Can the export be read at all, wherever it was written? -------------
# Power BI Desktop formats numbers with the machine's locale and separates columns
# with the machine's list separator, and those two settings are independent. A
# Spanish install writes a comma delimiter AND a comma decimal point, quoting the
# numbers so the file still parses. The first version of this reader assumed the
# two could never be the same character, read "0,7352" as 7352, and failed with a
# discrepancy of 7351.26 that pointed at the DAX rather than at itself.

LOCALES = [
    pytest.param(",", ".", ",", id="en-US"),
    pytest.param(";", ",", ".", id="es-ES-semicolon"),
    pytest.param(",", ",", ".", id="es-ES-comma-delimiter"),
    pytest.param("\t", ",", ".", id="de-DE-tab"),
    pytest.param(";", ",", "", id="no-grouping"),
]


def _write_export(path, rows, delimiter, decimal, grouping):
    """Write the scan the way Power BI Desktop would on one particular machine."""
    def dress(value, places):
        if value is None or (isinstance(value, float) and value != value):
            return ""
        text = f"{round(float(value), places):,.{places}f}"
        return (text.replace(",", "\x00").replace(".", decimal)
                    .replace("\x00", grouping))

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(list(COLUMNS))
    for row in rows:
        writer.writerow([row["city"], row["job_code"], row["job_level"]]
                        + [dress(row[name], places)
                           for name, places in DECIMALS.items()])
    writer.writerow(["", "", ""] + ["" for _ in DECIMALS])   # the totals row
    path.write_text(buffer.getvalue(), encoding="utf-8-sig")


@pytest.mark.parametrize("delimiter, decimal, grouping", LOCALES)
def test_the_export_reads_the_same_on_any_locale(reference, tmp_path,
                                                 delimiter, decimal, grouping):
    """Round-trip the reference through a locale's formatting and back.

    Whatever the machine wrote it with, the numbers that come back have to be the
    numbers that went in — otherwise a reviewer with different regional settings
    sees the model fail a test the model passes.
    """
    path = tmp_path / "segment_scan_pbi.csv"
    _write_export(path, reference.to_dict("records"), delimiter, decimal, grouping)
    loaded = load_export(path)

    assert len(loaded) == len(reference), "the totals row was not dropped"
    for column, places in DECIMALS.items():
        gap = (loaded[column].values - reference[column].astype(float).values)
        worst = max(abs(g) for g in gap)
        assert worst <= 0.5 * 10 ** -places + 1e-9, (
            f"{column} survived the round trip as a different number "
            f"(worst {worst:g}) with delimiter {delimiter!r} and decimal {decimal!r}"
        )


@pytest.mark.parametrize("values, expected", [
    (["0,7352", "70,67", "9,5333"], ","),          # comma decimal, no grouping
    (["0.7352", "70.67", "9.5333"], "."),          # full stop decimal
    (["1.234,56", "0,85"], ","),                   # both present: rightmost wins
    (["1,234.56", "0.85"], "."),
    (["1.234.567", "12.261"], ","),                # repeated: that one is grouping
    (["1,234,567", "12,261"], "."),
    # Genuinely undecidable on its own — a thousands group and a three-decimal
    # number look identical — so it abstains and takes the default rather than
    # guessing. Nothing in this export is ever that bare.
    (["12.261"], "."),
    ([], "."),                                     # no evidence: the plain default
])
def test_the_decimal_separator_is_read_from_the_numbers(values, expected):
    assert _detect_decimal_separator(values) == expected


# --- 1 · Do the two implementations agree? ------------------------------------

@needs_export
def test_both_implementations_see_the_same_segments(paired):
    """The same cells clear the materiality floor on both sides.

    A cell present on one side only means the two are working on different
    populations, and every comparison after this one would be meaningless.
    """
    only_model = paired.loc[paired["_merge"] == "left_only", CELL]
    only_reference = paired.loc[paired["_merge"] == "right_only", CELL]
    assert only_model.empty and only_reference.empty, (
        "the two implementations disagree on which cells are material — "
        f"model only: {only_model.to_dict('records')}, "
        f"reference only: {only_reference.to_dict('records')}"
    )


@needs_export
@pytest.mark.parametrize("column", [
    "avg_headcount_ltm", "voluntary_exits_ltm", "expected_exits_ltm",
    "attrition_p_value", "ttc_compa_ratio", "avg_span_of_control",
    "incumbent_count", "incumbent_percentile",
    "recent_hire_count", "recent_hire_percentile",
])
def test_every_input_to_the_rule_reconciles(paired, column):
    """Each input the rule reads, DAX against pandas.

    Compared to the precision the export carries and no further: a figure
    formatted to two decimals cannot be checked to six, and demanding that would
    fail on rounding rather than on a real difference.
    """
    limit = tolerance(column)
    gap = (paired[f"{column}_pbi"] - paired[f"{column}_ref"]).abs()
    worst = gap.max()
    offenders = paired.loc[gap > limit, CELL + [f"{column}_pbi", f"{column}_ref"]]
    assert offenders.empty, (
        f"{column}: {len(offenders)} cell(s) disagree beyond {limit:g} "
        f"(worst {worst:g})\n{offenders.to_string(index=False)}"
    )


@needs_export
@pytest.mark.parametrize("flag", FLAGS)
def test_the_model_and_the_reference_flag_the_same_cells(paired, flag):
    """The verdict itself, not just the numbers underneath it.

    Inputs can agree to four decimals and the verdicts still differ, when a value
    sits on a threshold. That is worth knowing about explicitly.
    """
    disagreements = paired.loc[
        paired[f"{flag}_pbi"].astype(int) != paired[f"{flag}_ref"].astype(int),
        CELL + [f"{flag}_pbi", f"{flag}_ref"]]
    assert disagreements.empty, (
        f"{flag}: model and reference reach different verdicts\n"
        f"{disagreements.to_string(index=False)}"
    )


@needs_export
def test_the_poisson_test_is_actually_discriminating(exported):
    """Guard against a p-value that is silently constant.

    A measure returning blank, or one, for every cell would pass every
    reconciliation above — both implementations would agree perfectly on
    nothing. The test has to separate cells for the rule to mean anything.
    """
    p_values = exported["attrition_p_value"]
    assert p_values.notna().all(), "some cells have no p-value at all"
    assert (p_values < ALPHA).any(), "no cell is significant: the test never fires"
    assert (p_values >= ALPHA).any(), "every cell is significant: the test never holds"


# --- 2 · Given they agree, is the rule right? ---------------------------------

@needs_export
@pytest.mark.parametrize("segment_id", ["A", "B", "D"])
def test_every_segment_with_an_expected_rule_is_found(exported, truth, segment_id):
    """Recall, one designed segment at a time."""
    segment = next(s for s in truth["segments"] if s["id"] == segment_id)
    definition = segment["definition"]
    cells = exported[
        (exported["city"] == definition["city"])
        & (exported["job_code"] == definition["job_code"])
        & (exported["job_level"].isin(definition["job_levels"]))]

    assert not cells.empty, (
        f"segment {segment_id} ({segment['name']}) is not in the export at all — "
        "it did not clear the materiality floor"
    )
    expected_flag = RULES[segment["expected_rule"]]
    assert cells[expected_flag].max() == 1, (
        f"segment {segment_id} ({segment['name']}) was not flagged by "
        f"{segment['expected_rule']}: {segment['root_cause']}"
    )


@needs_export
def test_the_designed_false_positive_is_left_alone(exported, truth):
    """São Paulo. Base pay looks low; total target cash does not."""
    segment = next(s for s in truth["segments"] if s["id"] == "C")
    definition = segment["definition"]
    cells = exported[
        (exported["city"] == definition["city"])
        & (exported["job_code"] == definition["job_code"])
        & (exported["job_level"].isin(definition["job_levels"]))]
    fired = cells.loc[cells[FLAGS].sum(axis=1) > 0, CELL + FLAGS]
    assert fired.empty, (
        "segment C was flagged. Its base compa-ratio is 0.88 and its total target "
        "cash 0.99: reading base salary in isolation is the trap this segment "
        f"exists to set.\n{fired.to_string(index=False)}"
    )


@needs_export
def test_nothing_outside_a_designed_segment_is_flagged(exported, truth):
    """The control against the 3% of employees carrying random pay deviation."""
    strays = []
    for _, row in exported.iterrows():
        if row[FLAGS].sum() == 0:
            continue
        segment = _segment_of(row, truth)
        if segment is None or RULES[segment["expected_rule"]] not in [
                flag for flag in FLAGS if row[flag] == 1]:
            fired = [flag for flag in FLAGS if row[flag] == 1]
            strays.append(f"{row['city']}/{row['job_code']}/{row['job_level']} {fired}")
    assert not strays, "flagged where nothing should be: " + "; ".join(strays)


@needs_export
def test_precision_and_recall(exported, truth, capsys):
    """The headline score, reported whether or not it is perfect.

    Scored on expected_rule rather than on the business verdict. Segment D carries
    the verdict "dismiss" because no pay adjustment is warranted there, yet a rule
    should still fire on it — the organizational one. Dismissing a segment for pay
    and detecting it as an organizational problem are the same correct answer said
    two ways.
    """
    actionable = [s for s in truth["segments"] if s["expected_rule"]]

    found = set()
    true_positives = 0
    flagged_rows = 0
    for _, row in exported.iterrows():
        fired = [flag for flag in FLAGS if row[flag] == 1]
        if not fired:
            continue
        flagged_rows += len(fired)
        segment = _segment_of(row, truth)
        if segment and segment["expected_rule"]:
            expected_flag = RULES[segment["expected_rule"]]
            if expected_flag in fired:
                found.add(segment["id"])
                true_positives += 1

    recall = len(found) / len(actionable)
    precision = true_positives / flagged_rows if flagged_rows else 0.0

    with capsys.disabled():
        print(f"\n  detection · {flagged_rows} cell-rules fired · "
              f"precision {precision:.0%} · recall {recall:.0%}")

    assert recall == 1.0, (
        f"recall {recall:.0%}: missed "
        f"{sorted({s['id'] for s in actionable} - found)}")
    assert precision == 1.0, f"precision {precision:.0%}: some flags are false positives"


# --- 3 · The reference implementation stands on its own -----------------------
# These run without the export. If they fail, the reference is broken and the
# reconciliation above was comparing the model against nothing worth comparing to.

def test_the_reference_implementation_scores_perfectly(reference, truth):
    """Independent of the model entirely: pandas, the star schema, the answer key."""
    flagged = flagged_cells(reference)
    matched, strays = set(), []
    for _, row in flagged.iterrows():
        segment = _segment_of(row, truth)
        if segment and segment["expected_rule"] == row["rule"]:
            matched.add(segment["id"])
        else:
            strays.append(f"{row['city']}/{row['job_code']}/{row['job_level']} ({row['rule']})")

    expected = {s["id"] for s in truth["segments"] if s["expected_rule"]}
    assert not strays, "reference flagged cells it should not: " + "; ".join(strays)
    assert matched == expected, f"reference missed {sorted(expected - matched)}"


def test_the_materiality_floor_removes_most_of_the_noise(conn, bands):
    """Transparency about how much work the thirty-person floor is doing.

    It is a threshold with real consequences — a segment below it gets a
    conversation with a manager, not a compensation program — so its effect is
    reported rather than left implicit.
    """
    scan = segment_scan(conn, bands)
    material = (scan["avg_headcount_ltm"] >= MIN_MATERIALITY).sum()
    assert 0 < material < len(scan), (
        f"the materiality floor keeps {material} of {len(scan)} cells; "
        "a floor that excludes everything or nothing is not a floor"
    )
