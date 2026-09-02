"""Write the block 6 additions into the semantic model's TMDL.

TMDL is whitespace-significant: tabs for structure, and a `///` block is the
description of the object immediately below it — never a free-floating comment.
Both rules are easy to break by hand and produce a file Power BI Desktop refuses
to open, so the edits are generated rather than typed.

Run with Power BI Desktop CLOSED. Desktop holds the model in memory and
overwrites the files on disk when it saves.
"""

from __future__ import annotations

import re
from pathlib import Path

DEFINITION = (Path(__file__).resolve().parents[1]
              / "PowerBI" / "MPG_PeopleAnalytics.SemanticModel" / "definition")
TAG = "7a1c9e40-3b52-4a18-9f21-"


def write(path: Path, text: str) -> None:
    """UTF-8 without BOM, CRLF line endings — what Power BI Desktop writes."""
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


# --- The ln(k!) helper table --------------------------------------------------
LN_FACTORIAL = f"""\
/// ln(k!) for k = 0 to 500. DAX has no Poisson function and no factorial, and 171!
/// already overflows a double, so [Attrition p-value] sums the Poisson tail in
/// logarithms and reads ln(k!) from here instead of recomputing it per term.
///
/// Disconnected from the star on purpose: this is a table of mathematical constants,
/// not business data, and no filter, slicer or security role should ever reach it.
/// Built once at refresh. The largest segment in the model records 28 exits, so 500
/// is headroom rather than a ceiling anyone needs to think about.
table LnFactorial
	isHidden
	lineageTag: {TAG}0c4d8e6b1a10

	column k
		dataType: int64
		isHidden
		formatString: 0
		lineageTag: {TAG}0c4d8e6b1a11
		summarizeBy: none
		isNameInferred
		sourceColumn: [k]

		annotation SummarizationSetBy = Automatic

	column ln_factorial
		dataType: double
		isHidden
		lineageTag: {TAG}0c4d8e6b1a12
		summarizeBy: none
		isNameInferred
		sourceColumn: [ln_factorial]

		annotation SummarizationSetBy = Automatic

	partition LnFactorial = calculated
		mode: import
		source =
				SELECTCOLUMNS (
				    ADDCOLUMNS (
				        GENERATESERIES ( 0, 500, 1 ),
				        "@LnFactorial",
				            VAR K = [Value]
				            RETURN
				                IF (
				                    K <= 1,
				                    0,
				                    SUMX ( SELECTCOLUMNS ( GENERATESERIES ( 2, K, 1 ), "j", [Value] ), LN ( [j] ) )
				                )
				    ),
				    "k", [Value],
				    "ln_factorial", [@LnFactorial]
				)

	annotation PBI_Id = LnFactorial
"""

# --- The detection measures ---------------------------------------------------
# Every threshold here is argued for in docs/case/detection-rule.md and repeated as
# a constant in validation/reference_rule.py, so the two implementations can be read
# side by side.
FOLDER = "07 Detection"

MEASURES: list[tuple[str, str, str, str]] = [
    (
        "Expected Exits LTM",
        "The voluntary exits this segment would have produced over the last twelve months\n"
        "if it had run at the company rate. It exists to be compared against the actual\n"
        "count, and for nothing else.",
        "[Company Attrition Baseline] * [Average Headcount LTM]",
        "0.0000",
    ),
    (
        "Attrition p-value",
        "One-sided Poisson probability of seeing this many voluntary exits, or more, if the\n"
        "segment ran at the company rate. Below 0.05 the gap is not comfortably explained by\n"
        "chance. This replaces the \"1.5x the baseline\" rule of thumb, which on a segment of\n"
        "thirty people fires on noise 22% of the time — the arithmetic is tabulated in\n"
        "docs/case/detection-rule.md.\n"
        "\n"
        "DAX has no Poisson function, so the exact tail is summed term by term:\n"
        "    P(X >= x) = 1 - SUM over k = 0..x-1 of EXP( -lambda + k*LN(lambda) - LN(k!) )\n"
        "Working in logarithms keeps every term inside floating-point range, and LN(k!) comes\n"
        "from the LnFactorial helper table. The same tail is computed a second time in\n"
        "validation/poisson.py, by two algorithms that share no arithmetic, and the three\n"
        "agree to 1e-12 — tests/test_reconciliation.py checks that rather than assuming it.",
        "VAR Lambda = [Expected Exits LTM]\n"
        "VAR Observed = [Voluntary Exits LTM]\n"
        "VAR LargestK = MAXX ( ALL ( LnFactorial ), LnFactorial[k] )\n"
        "VAR CumulativeBelow =\n"
        "    SUMX (\n"
        "        FILTER ( ALL ( LnFactorial ), LnFactorial[k] <= Observed - 1 ),\n"
        "        EXP ( -Lambda + LnFactorial[k] * LN ( Lambda ) - LnFactorial[ln_factorial] )\n"
        "    )\n"
        "RETURN\n"
        "    SWITCH (\n"
        "        TRUE (),\n"
        "        ISBLANK ( Lambda ) || Lambda <= 0, BLANK (),\n"
        "        ISBLANK ( Observed ) || Observed <= 0, 1,\n"
        "        Observed - 1 > LargestK, BLANK (),\n"
        "        MIN ( MAX ( 1 - CumulativeBelow, 0 ), 1 )\n"
        "    )",
        "0.000000",
    ),
    (
        "Incumbent Headcount",
        "Employees with three or more years of service who carry a peer percentile. Rule 2\n"
        "compares cohorts rather than the segment average, because salary compression is\n"
        "invisible in the average by construction: the incumbents who have fallen behind and\n"
        "the recent hires who passed them cancel out.\n"
        "Rows with no peer percentile are excluded, not counted as zero — the percentile is\n"
        "suppressed in SQL wherever the peer group is under five people.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR LastSnapshotDate = CALCULATE ( MAX ( Dim_Date[date] ), Dim_Date[date_key] = LastSnapshot )\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        COUNTROWS (\n"
        "            FILTER (\n"
        "                Facts_HeadCount,\n"
        "                NOT ISBLANK ( Facts_HeadCount[peer_percentile] )\n"
        "                    && DATEDIFF ( RELATED ( Dim_Employee[hire_date] ), LastSnapshotDate, DAY ) >= 3 * 365.25\n"
        "            )\n"
        "        ),\n"
        "        Dim_Date[date_key] = LastSnapshot\n"
        "    )",
        "0",
    ),
    (
        "Recent Hire Headcount",
        "Employees with less than three years of service who carry a peer percentile. The\n"
        "other half of the cohort split; both sides need twenty people before the comparison\n"
        "is worth making.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR LastSnapshotDate = CALCULATE ( MAX ( Dim_Date[date] ), Dim_Date[date_key] = LastSnapshot )\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        COUNTROWS (\n"
        "            FILTER (\n"
        "                Facts_HeadCount,\n"
        "                NOT ISBLANK ( Facts_HeadCount[peer_percentile] )\n"
        "                    && DATEDIFF ( RELATED ( Dim_Employee[hire_date] ), LastSnapshotDate, DAY ) < 3 * 365.25\n"
        "            )\n"
        "        ),\n"
        "        Dim_Date[date_key] = LastSnapshot\n"
        "    )",
        "0",
    ),
    (
        "Incumbent Peer Percentile",
        "Where the long-tenured cohort sits inside its own city, job and level peer group.\n"
        "Peer percentile rather than compa-ratio on purpose: this asks whether incumbents have\n"
        "fallen behind the people beside them, which is a question about internal fairness and\n"
        "has nothing to do with the market band.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR LastSnapshotDate = CALCULATE ( MAX ( Dim_Date[date] ), Dim_Date[date_key] = LastSnapshot )\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        AVERAGEX (\n"
        "            FILTER (\n"
        "                Facts_HeadCount,\n"
        "                DATEDIFF ( RELATED ( Dim_Employee[hire_date] ), LastSnapshotDate, DAY ) >= 3 * 365.25\n"
        "            ),\n"
        "            Facts_HeadCount[peer_percentile]\n"
        "        ),\n"
        "        Dim_Date[date_key] = LastSnapshot\n"
        "    )",
        "0.0000",
    ),
    (
        "Recent Hire Peer Percentile",
        "Where the recent-hire cohort sits inside the same peer group. A gap of fifteen points\n"
        "or more against the incumbents is what rule 2 is looking for.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR LastSnapshotDate = CALCULATE ( MAX ( Dim_Date[date] ), Dim_Date[date_key] = LastSnapshot )\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        AVERAGEX (\n"
        "            FILTER (\n"
        "                Facts_HeadCount,\n"
        "                DATEDIFF ( RELATED ( Dim_Employee[hire_date] ), LastSnapshotDate, DAY ) < 3 * 365.25\n"
        "            ),\n"
        "            Facts_HeadCount[peer_percentile]\n"
        "        ),\n"
        "        Dim_Date[date_key] = LastSnapshot\n"
        "    )",
        "0.0000",
    ),
    (
        "Flag Pay Adjustment",
        "Rule 1. Fires where the segment is materially sized, its attrition is distinguishable\n"
        "from the baseline, total target cash sits below 0.92, and span of control rules out an\n"
        "organizational explanation.\n"
        "Total cash, not base salary. This is the single most consequential line in the model:\n"
        "base pay alone flags São Paulo Sales at 0.88, a population whose 41% variable target\n"
        "puts its total cash at 0.99 and whose attrition sits below its own region's.\n"
        "The p-value is tested for blank explicitly — in DAX a blank compares as zero, so an\n"
        "unguarded \"< 0.05\" would fire on every segment that has no p-value at all.",
        "VAR Significant =\n"
        "    [Average Headcount LTM] >= 30\n"
        "        && NOT ISBLANK ( [Attrition p-value] )\n"
        "        && [Attrition p-value] < 0.05\n"
        "RETURN\n"
        "    INT (\n"
        "        Significant\n"
        "            && [Weighted Average TTC Compa-Ratio] < 0.92\n"
        "            && [Average Span of Control] <= [Company Span Baseline] * 1.5\n"
        "    )",
        "0",
    ),
    (
        "Flag Internal Equity",
        "Rule 2. Fires where both tenure cohorts are at least twenty people, the incumbents sit\n"
        "at or below the 35th peer percentile and the recent hires at or above the 65th.\n"
        "No significance test here: this compares positions inside a fixed population rather\n"
        "than a rate estimated from counts, so Poisson noise does not apply. Nor is attrition a\n"
        "condition — the point of rule 2 is to catch the problem before attrition reacts.",
        "INT (\n"
        "    [Incumbent Headcount] >= 20\n"
        "        && [Recent Hire Headcount] >= 20\n"
        "        && [Incumbent Peer Percentile] <= 0.35\n"
        "        && [Recent Hire Peer Percentile] >= 0.65\n"
        ")",
        "0",
    ),
    (
        "Flag Organizational",
        "Rule 3. Fires where attrition is real and significant, pay is demonstrably not the\n"
        "explanation — total target cash at or above 0.95 — and span of control exceeds 1.5x the\n"
        "company mean. The recommendation this produces is a supervisory layer, not money.\n"
        "Without this rule the analysis has only one lever, and every problem starts to look\n"
        "like a pay problem.",
        "VAR Significant =\n"
        "    [Average Headcount LTM] >= 30\n"
        "        && NOT ISBLANK ( [Attrition p-value] )\n"
        "        && [Attrition p-value] < 0.05\n"
        "RETURN\n"
        "    INT (\n"
        "        Significant\n"
        "            && [Weighted Average TTC Compa-Ratio] >= 0.95\n"
        "            && [Average Span of Control] > [Company Span Baseline] * 1.5\n"
        "    )",
        "0",
    ),
    (
        "Detection Rule Fired",
        "The rules that fired, as text, for the report. Blank where none did.\n"
        "A segment can trip more than one rule; listing all of them is more honest than picking\n"
        "a winner by an arbitrary priority order and hiding the fact that two diagnoses apply.",
        "VAR Fired =\n"
        "    FILTER (\n"
        "        {\n"
        "            ( \"Pay adjustment\", [Flag Pay Adjustment] ),\n"
        "            ( \"Internal equity\", [Flag Internal Equity] ),\n"
        "            ( \"Organizational\", [Flag Organizational] )\n"
        "        },\n"
        "        [Value2] = 1\n"
        "    )\n"
        "RETURN\n"
        "    CONCATENATEX ( Fired, [Value1], \" + \" )",
        None,
    ),
]


def render_measure(index: int, name: str, description: str, dax: str,
                   format_string: str | None) -> str:
    """One measure block: description, definition, format, folder, lineage tag."""
    # TMDL takes a bare identifier only for a single word; anything with a space
    # or punctuation has to be quoted.
    quoted = name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else f"'{name}'"
    lines = [f"\t/// {line}".rstrip() for line in description.split("\n")]

    body = dax.split("\n")
    if len(body) == 1:
        lines.append(f"\tmeasure {quoted} = {body[0]}")
    else:
        lines.append(f"\tmeasure {quoted} =")
        lines += [f"\t\t\t{line}".rstrip() for line in body]

    if format_string:
        lines.append(f"\t\tformatString: {format_string}")
    lines.append(f"\t\tdisplayFolder: {FOLDER}")
    lines.append(f"\t\tlineageTag: {TAG}{index:012d}")
    return "\n".join(lines) + "\n"


def main() -> None:
    # 1 · The helper table.
    write(DEFINITION / "tables" / "LnFactorial.tmdl", LN_FACTORIAL)

    # 2 · The measures, inserted before the placeholder column that ends _Measures.
    measures_path = DEFINITION / "tables" / "_Measures.tmdl"
    text = read(measures_path)
    anchor = "\tcolumn Value\n"
    assert anchor in text, "the _Measures placeholder column moved; check the file"
    if f"displayFolder: {FOLDER}" in text:
        raise SystemExit("detection measures are already present — nothing to do")

    blocks = [render_measure(30 + i, *m) for i, m in enumerate(MEASURES)]
    head, tail = text.split(anchor, 1)
    text = head + "\n".join(blocks) + "\n" + anchor + tail

    # Average headcount over twelve months is not a whole number, and the block 6
    # export has to carry it at full precision for the reconciliation to mean
    # anything. "#,##0" would round 70.67 to 71.
    text = text.replace(
        "\tmeasure 'Average Headcount LTM' =", "\tmeasure 'Average Headcount LTM' =", 1)
    marker = "displayFolder: 03 Movement\n\t\tlineageTag: " + TAG + "000000000014"
    text = text.replace("formatString: #,##0\n\t\t" + marker,
                        "formatString: 0.00\n\t\t" + marker, 1)
    write(measures_path, text)

    # 3 · Register the helper table with the model.
    model_path = DEFINITION / "model.tmdl"
    model = read(model_path)
    if "ref table LnFactorial" not in model:
        model = model.replace("ref table _Measures\n",
                              "ref table _Measures\nref table LnFactorial\n", 1)
        write(model_path, model)

    # 4 · The four relationships the movement fact was missing.
    relationships_path = DEFINITION / "relationships.tmdl"
    relationships = read(relationships_path)
    new = [("job_key", "Dim_Job", "job_key", "b1"),
           ("org_key", "Dim_Organization", "org_key", "b2"),
           ("location_key", "Dim_Location", "location_key", "b3"),
           ("company_key", "Dim_Company", "company_key", "b4")]
    additions = ""
    for column, table, target, suffix in new:
        if f"fromColumn: Facts_Movement.{column}" in relationships:
            continue
        additions += (f"\nrelationship {TAG}0c4d8e6b1a{suffix}\n"
                      f"\tfromColumn: Facts_Movement.{column}\n"
                      f"\ttoColumn: {table}.{target}\n")
    if additions:
        write(relationships_path, relationships.rstrip("\n") + "\n" + additions)

    # 5 · Declare the four new columns on the movement fact. The partition is
    # SELECT *, so the database already returns them; TMDL still has to know they
    # exist before a relationship can point at one.
    movement_path = DEFINITION / "tables" / "Facts_Movement.tmdl"
    movement = read(movement_path)
    if "column job_key" not in movement:
        columns = ""
        for i, column in enumerate(["job_key", "org_key", "location_key", "company_key"]):
            columns += (f"\tcolumn {column}\n"
                        f"\t\tdataType: int64\n"
                        f"\t\tisHidden\n"
                        f"\t\tformatString: 0\n"
                        f"\t\tlineageTag: {TAG}0c4d8e6b1c{i:02d}\n"
                        f"\t\tsummarizeBy: none\n"
                        f"\t\tsourceColumn: {column}\n\n"
                        f"\t\tannotation SummarizationSetBy = Automatic\n\n")
        anchor = "\tcolumn event_type\n"
        assert anchor in movement
        movement = movement.replace(anchor, columns + anchor, 1)
        write(movement_path, movement)

    print(f"wrote {len(MEASURES)} measures, LnFactorial, "
          f"{additions.count('relationship')} relationships, movement keys")


if __name__ == "__main__":
    main()
