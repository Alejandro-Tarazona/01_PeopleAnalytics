"""Write the overview additions into the semantic model's TMDL.

Two groups of measures and one disconnected table:

  08 Trend       - the same figure one period back, where "one period" follows what
                   the user filtered rather than being fixed at write time.
  09 Simulation  - a blanket salary increase, driven by a parameter, and the two
                   figures that say what a blanket increase actually buys.
  Payroll Increase - the parameter itself. Disconnected, so it composes with every
                   other filter on the page instead of fighting them.

TMDL is whitespace-significant: tabs for structure, and a `///` block is the
description of the object immediately below it - never a free-floating comment.
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

MOVEMENT = "03 Movement"
ECONOMICS = "05 Economics"
DETECTION = "07 Detection"
TREND = "08 Trend"
SIMULATION = "09 Simulation"
REPORT = "10 Report"


# --- The refresh stamp --------------------------------------------------------
# NOW() inside a measure is evaluated when the visual is queried, so a measure that
# simply returns NOW() reports the time the reader opened the page and calls it the
# refresh time - a caption that is always wrong and never obviously so. Inside a
# calculated table it is evaluated once, when the model refreshes, and then frozen.
# That is the only thing in import mode that actually knows when the data landed.
REFRESH_INFO = f"""\
/// One row, one column: the moment the model last refreshed.
/// Calculated rather than a measure on purpose. NOW() in a measure re-evaluates on
/// every query and would report when the reader opened the page; in a calculated
/// table it is evaluated once at refresh and frozen, which is the question the
/// banner is actually asking.
///
/// The clock it reads is the one running the refresh: local time in Power BI
/// Desktop, UTC in the Service. Anyone publishing this needs to know that before
/// they put the caption in front of a reader in another timezone.
table 'Refresh Info'
\tisHidden
\tlineageTag: {TAG}0c4d8e6b1a30

\tcolumn refreshed_at
\t\tdataType: dateTime
\t\tisHidden
\t\tformatString: General Date
\t\tlineageTag: {TAG}0c4d8e6b1a31
\t\tsummarizeBy: none
\t\tisNameInferred
\t\tsourceColumn: [refreshed_at]

\t\tannotation SummarizationSetBy = Automatic

\tpartition 'Refresh Info' = calculated
\t\tmode: import
\t\tsource = ROW ( "refreshed_at", NOW () )

\tannotation PBI_Id = RefreshInfo
"""


def write(path: Path, text: str) -> None:
    """UTF-8 without BOM, CRLF line endings - what Power BI Desktop writes."""
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


# --- The parameter table ------------------------------------------------------
# Disconnected on purpose. A parameter joined to the star would filter the fact and
# silently change every figure on the page; disconnected, it can only be read by the
# measures that ask for it, and it composes with a city or month filter rather than
# competing with one.
#
# The series stops at 15%. A blanket adjustment beyond that is not a compensation
# decision anyone models in a slicer, and an open-ended range invites a reader to
# drag it somewhere the underlying assumptions stop holding.
#
# No isNameInferred on the column. GENERATESERIES emits a column called Value, and
# isNameInferred tells the engine to take the name from the source - which quietly
# overrides the declared 'Payroll Increase %' and renames the field to Value every
# time this file is written. The declared name has to stand on its own.
#
# extendedProperty ParameterMetadata is not decoration and was wrongly left out of
# the first version of this file. It is what marks the table as a what-if parameter,
# and without it Desktop withholds the "Single value" slicer style - the slider. The
# shape below is what Desktop itself writes; it was read off a throwaway parameter
# rather than guessed, because a malformed embedded JSON block in TMDL is one of the
# few things that stops the model opening at all.
PAYROLL_INCREASE = f"""\
/// The blanket salary increase being simulated, as a share of base pay.
/// Disconnected from the star: no relationship, so it filters nothing on its own and
/// is read only by the measures in the "09 Simulation" folder.
///
/// Zero to fifteen per cent in half-point steps. The default is six, which is the
/// proposal actually on the table - the executive committee is being asked to approve
/// a blanket 6% across the LATAM hub, and a reader who opens the page should see that
/// number first rather than having to know to type it in.
table 'Payroll Increase'
\tlineageTag: {TAG}0c4d8e6b1a20

\tcolumn 'Payroll Increase %'
\t\tdataType: double
\t\tformatString: 0.0%
\t\tlineageTag: {TAG}0c4d8e6b1a21
\t\tsummarizeBy: none
\t\tsourceColumn: [Value]

\t\textendedProperty ParameterMetadata =
\t\t\t\t{{
\t\t\t\t  "version": 0
\t\t\t\t}}

\t\tannotation SummarizationSetBy = Automatic

\tpartition 'Payroll Increase' = calculated
\t\tmode: import
\t\tsource = GENERATESERIES ( 0, 0.15, 0.005 )

\tannotation PBI_Id = PayrollIncrease
"""


# --- The targeted-adjustment parameter ----------------------------------------
# The mirror of Payroll Increase. That one prices the blanket rise the executive
# committee was asked to approve; this one prices the targeted rise the analysis
# recommends instead. Same mechanism, opposite policy, and putting them on the same
# footing is what lets the two be compared rather than asserted against each other.
#
# It exists because [Cost to Band Minimum] turned out to be the wrong denominator for
# a recommendation. Band minimum sits at 80% of midpoint throughout this survey, so a
# segment averaging 0.85 has only its lower tail beneath the floor: lifting Bogota
# Data & Analytics to its band minimum costs $34,545 and moves the segment's compa
# ratio almost not at all. Lifting it to 0.95 of market costs $811,000. The second
# number is the one a compensation committee is actually being asked to approve.
COMPA_TARGET = f"""\
/// The compa-ratio a targeted adjustment would lift a segment to.
/// Disconnected from the star, like 'Payroll Increase': it filters nothing and is read
/// only by the measures that ask for it.
///
/// 0.85 to 1.05 in hundredths, defaulting to 0.95 - below the company mean of 0.98,
/// because the recommendation is to close a gap rather than to overtake the market,
/// and a default of 1.00 would quietly propose something more expensive than anyone
/// asked for.
table 'Compa Target'
\tlineageTag: {TAG}0c4d8e6b1a40

\tcolumn 'Compa-Ratio Target'
\t\tdataType: double
\t\tformatString: 0.00
\t\tlineageTag: {TAG}0c4d8e6b1a41
\t\tsummarizeBy: none
\t\tsourceColumn: [Value]

\t\textendedProperty ParameterMetadata =
\t\t\t\t{{
\t\t\t\t  "version": 0
\t\t\t\t}}

\t\tannotation SummarizationSetBy = Automatic

\tpartition 'Compa Target' = calculated
\t\tmode: import
\t\tsource = GENERATESERIES ( 0.85, 1.05, 0.01 )

\tannotation PBI_Id = CompaTarget
"""


# --- The measures -------------------------------------------------------------
# (name, description, dax, formatString, displayFolder)
MEASURES: list[tuple[str, str, str, str, str]] = [

    # --- 08 Trend -------------------------------------------------------------
    (
        "Comparison Period",
        "What \"the previous period\" means for whatever the user has filtered, as text, so a\n"
        "card can label itself instead of carrying a caption that goes stale.\n"
        "A single month selected compares against the month before it; anything else - a year,\n"
        "a quarter, no date filter at all - compares against the year before. Both readings are\n"
        "right for their context and neither is right for the other, which is why this is a\n"
        "measure rather than a decision taken once at design time.",
        "IF ( HASONEVALUE ( Dim_Date[year_month] ), \"vs previous month\", \"vs previous year\" )",
        "",
        TREND,
    ),
    (
        "Headcount Previous Period",
        "Headcount one period back, on the same basis the current figure uses.\n"
        "Nothing here re-implements the snapshot logic: [Headcount] already resolves the last\n"
        "month-end inside whatever filter context it is given, so shifting the context with\n"
        "PREVIOUSMONTH or PREVIOUSYEAR is enough and the two figures cannot drift apart.",
        "IF (\n"
        "    HASONEVALUE ( Dim_Date[year_month] ),\n"
        "    CALCULATE ( [Headcount], PREVIOUSMONTH ( Dim_Date[date] ) ),\n"
        "    CALCULATE ( [Headcount], PREVIOUSYEAR ( Dim_Date[date] ) )\n"
        ")",
        "#,##0",
        TREND,
    ),
    (
        "Headcount Change vs Previous Period",
        "People added or lost since the comparison period. Blank where there is no comparison\n"
        "period to speak of - the first month of the horizon has nothing behind it, and showing\n"
        "the whole headcount as growth there would be a fabricated number.",
        "VAR Baseline = [Headcount Previous Period]\n"
        "RETURN\n"
        "    IF ( NOT ISBLANK ( Baseline ), [Headcount] - Baseline )",
        "+#,##0;-#,##0;0",
        TREND,
    ),
    (
        "Headcount Change % vs Previous Period",
        "The same movement as a rate, for the card that has no room for two numbers.",
        "DIVIDE ( [Headcount Change vs Previous Period], [Headcount Previous Period] )",
        "+0.0%;-0.0%;0.0%",
        TREND,
    ),
    (
        "Annualized Payroll USD Previous Period",
        "Annualized base payroll one period back, in constant currency like its present-day\n"
        "counterpart. Constant currency matters more here than anywhere else on the page: a\n"
        "period-over-period comparison at actual rates reports an exchange movement as a pay\n"
        "decision, which is the single most common way a payroll trend chart misleads.",
        "IF (\n"
        "    HASONEVALUE ( Dim_Date[year_month] ),\n"
        "    CALCULATE ( [Annualized Payroll USD], PREVIOUSMONTH ( Dim_Date[date] ) ),\n"
        "    CALCULATE ( [Annualized Payroll USD], PREVIOUSYEAR ( Dim_Date[date] ) )\n"
        ")",
        "$#,##0",
        TREND,
    ),
    (
        "Annualized Payroll USD Change vs Previous Period",
        "Payroll movement in dollars. Blank with no comparison period, for the same reason as\n"
        "the headcount equivalent.",
        "VAR Baseline = [Annualized Payroll USD Previous Period]\n"
        "RETURN\n"
        "    IF ( NOT ISBLANK ( Baseline ), [Annualized Payroll USD] - Baseline )",
        "+$#,##0;-$#,##0;$0",
        TREND,
    ),
    (
        "Annualized Payroll USD Change % vs Previous Period",
        "Payroll movement as a rate. Read beside the headcount rate rather than alone: payroll\n"
        "rising faster than headcount is a mix or merit story, and the two rates together say\n"
        "which one without needing a third measure.",
        "DIVIDE ( [Annualized Payroll USD Change vs Previous Period],\n"
        "         [Annualized Payroll USD Previous Period] )",
        "+0.0%;-0.0%;0.0%",
        TREND,
    ),

    # --- 09 Simulation --------------------------------------------------------
    (
        "Payroll Increase % Value",
        "The rate currently selected on the Payroll Increase slicer, defaulting to the 6% the\n"
        "executive committee has been asked to approve.\n"
        "It lives here rather than on the parameter table because every measure in this model\n"
        "lives in _Measures. Power BI writes this measure onto the parameter table when it\n"
        "builds a what-if parameter itself; that convention is not this repository's.",
        "SELECTEDVALUE ( 'Payroll Increase'[Payroll Increase %], 0.06 )",
        "0.0%",
        SIMULATION,
    ),
    (
        "Blanket Increase Cost USD",
        "Annualized cost of raising every base salary in the current filter context by the\n"
        "selected rate. The gross number the proposal is asking for.",
        "[Annualized Payroll USD] * [Payroll Increase % Value]",
        "$#,##0",
        SIMULATION,
    ),
    (
        "Payroll USD After Blanket Increase",
        "Annualized base payroll once the increase is applied. Shown next to the current figure\n"
        "so the increase is read as a share of the whole rather than as a headline in isolation.",
        "[Annualized Payroll USD] * ( 1 + [Payroll Increase % Value] )",
        "$#,##0",
        SIMULATION,
    ),
    (
        "Weighted Average Compa-Ratio After Blanket Increase",
        "Where the population would sit against the market midpoint after the increase.\n"
        "Weighted the same way as its present-day counterpart, and suppressed below five people\n"
        "for the same reason: at that size the ratio identifies an individual's pay.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR IncreaseRate = [Payroll Increase % Value]\n"
        "VAR Pay = CALCULATE ( SUM ( Facts_HeadCount[base_salary_usd_constant] ), Dim_Date[date_key] = LastSnapshot )\n"
        "VAR Market = CALCULATE ( SUMX ( Facts_HeadCount, RELATED ( Dim_Market_Band[band_mid_usd] ) ), Dim_Date[date_key] = LastSnapshot )\n"
        "RETURN\n"
        "    IF (\n"
        "        [Headcount] >= 5 || [_Has Compensation Access],\n"
        "        DIVIDE ( Pay * ( 1 + IncreaseRate ), Market )\n"
        "    )",
        "0.00",
        SIMULATION,
    ),
    (
        "Blanket Increase Spend Above Band Minimum USD",
        "The share of a blanket increase that lands on people who are already at or above their\n"
        "band minimum.\n"
        "This is the cost of not targeting. A blanket adjustment is defended on the argument\n"
        "that people are underpaid, and this measure says how much of the money goes to people\n"
        "the argument does not describe. It moves with the slicer and with every filter on the\n"
        "page, so the figure for the LATAM hub at 6% is one click away.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR IncreaseRate = [Payroll Increase % Value]\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        SUMX (\n"
        "            FILTER (\n"
        "                Facts_HeadCount,\n"
        "                Facts_HeadCount[base_salary_usd_constant] >= RELATED ( Dim_Market_Band[band_min_usd] )\n"
        "            ),\n"
        "            Facts_HeadCount[base_salary_usd_constant] * IncreaseRate\n"
        "        ),\n"
        "        Dim_Date[date_key] = LastSnapshot\n"
        "    )",
        "$#,##0",
        SIMULATION,
    ),
    (
        "Blanket Increase Spend Below Band Minimum USD",
        "The remainder: the part of a blanket increase that does reach someone paid below their\n"
        "band minimum. The two halves sum to the gross cost, which is the point - they are meant\n"
        "to be read as a split, not as two independent figures.",
        "[Blanket Increase Cost USD] - [Blanket Increase Spend Above Band Minimum USD]",
        "$#,##0",
        SIMULATION,
    ),
    (
        "Headcount Still Below Band Minimum After Increase",
        "People who remain paid below their band minimum once the blanket increase is applied.\n"
        "The other half of the argument. A blanket rate large enough to fix the worst-paid\n"
        "segment overpays everyone else; a rate the budget can carry leaves that segment where\n"
        "it was. Bogota Data & Analytics sits at a compa-ratio of 0.85 with 86% of the segment\n"
        "below minimum, and six per cent does not move it out.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR IncreaseRate = [Payroll Increase % Value]\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        COUNTROWS (\n"
        "            FILTER (\n"
        "                Facts_HeadCount,\n"
        "                Facts_HeadCount[base_salary_usd_constant] * ( 1 + IncreaseRate )\n"
        "                    < RELATED ( Dim_Market_Band[band_min_usd] )\n"
        "            )\n"
        "        ),\n"
        "        Dim_Date[date_key] = LastSnapshot\n"
        "    )",
        "#,##0",
        SIMULATION,
    ),
    (
        "% Below Band Minimum After Increase",
        "The same population as a share, so it can be read directly against\n"
        "[% Below Band Minimum] and the gap between them is the increase's actual effect.",
        "IF (\n"
        "    [Headcount] >= 5 || [_Has Compensation Access],\n"
        "    DIVIDE ( [Headcount Still Below Band Minimum After Increase], [Headcount] )\n"
        ")",
        "0.0%",
        SIMULATION,
    ),

    # --- 03 Movement ----------------------------------------------------------
    (
        "Voluntary Attrition % LTM Complete Window",
        "[Voluntary Attrition % LTM] but blank until the trailing twelve months are actually\n"
        "twelve months. For charting only - the detection rule and the reconciliation read the\n"
        "unguarded measure and must go on doing so.\n"
        "\n"
        "The rate divides exits over a trailing window by the average headcount across that\n"
        "same window, and [Average Headcount LTM] divides by a constant twelve. Early in the\n"
        "horizon the window holds fewer than twelve months of snapshots, so the denominator is\n"
        "short while the numerator accumulates, and the rate climbs on its own. Measured from\n"
        "the source, the series reads 5.6% at 2024-10 and 13.5% at 2026-08 while real monthly\n"
        "exits go from about 44 to about 50 - a mild rise drawn as a doubling. The window is\n"
        "first complete at 2025-08, which is where an honest line starts.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR LastSnapshotDate = CALCULATE ( MAX ( Dim_Date[date] ), Dim_Date[date_key] = LastSnapshot )\n"
        "VAR MonthsInWindow =\n"
        "    CALCULATE (\n"
        "        DISTINCTCOUNT ( Facts_HeadCount[snapshot_date_key] ),\n"
        "        DATESINPERIOD ( Dim_Date[date], LastSnapshotDate, -12, MONTH )\n"
        "    )\n"
        "RETURN\n"
        "    IF ( MonthsInWindow >= 12, [Voluntary Attrition % LTM] )",
        "0.0%",
        MOVEMENT,
    ),

    # --- 08 Trend, second batch: the other two KPI cards ----------------------
    (
        "Voluntary Attrition % LTM Previous Period",
        "The attrition rate one period back, on the same trailing-twelve-month basis.",
        "IF (\n"
        "    HASONEVALUE ( Dim_Date[year_month] ),\n"
        "    CALCULATE ( [Voluntary Attrition % LTM], PREVIOUSMONTH ( Dim_Date[date] ) ),\n"
        "    CALCULATE ( [Voluntary Attrition % LTM], PREVIOUSYEAR ( Dim_Date[date] ) )\n"
        ")",
        "0.0%",
        TREND,
    ),
    (
        "Voluntary Attrition % LTM Change vs Previous Period",
        "The movement in the attrition rate, as a difference rather than as a ratio.\n"
        "13.8% to 13.5% is minus three tenths of a percentage point. Expressed the way the\n"
        "headcount and payroll cards express theirs it would read as minus 2.2%, which is a\n"
        "true number and a misleading one: nobody reads a rate card that way, and the two\n"
        "framings differ by a factor of seven. Points, and the card says pp.",
        "VAR Baseline = [Voluntary Attrition % LTM Previous Period]\n"
        "RETURN\n"
        "    IF ( NOT ISBLANK ( Baseline ), [Voluntary Attrition % LTM] - Baseline )",
        "+0.0%;-0.0%;0.0%",
        TREND,
    ),
    (
        "Weighted Average Compa-Ratio Previous Period",
        "Pay position one period back, weighted the same way as the current figure.",
        "IF (\n"
        "    HASONEVALUE ( Dim_Date[year_month] ),\n"
        "    CALCULATE ( [Weighted Average Compa-Ratio], PREVIOUSMONTH ( Dim_Date[date] ) ),\n"
        "    CALCULATE ( [Weighted Average Compa-Ratio], PREVIOUSYEAR ( Dim_Date[date] ) )\n"
        ")",
        "0.00",
        TREND,
    ),
    (
        "Weighted Average Compa-Ratio Change vs Previous Period",
        "Movement in pay position, as a difference. A ratio of ratios means nothing to a\n"
        "reader, and the quantity people actually discuss is \"we moved two points\".",
        "VAR Baseline = [Weighted Average Compa-Ratio Previous Period]\n"
        "RETURN\n"
        "    IF ( NOT ISBLANK ( Baseline ), [Weighted Average Compa-Ratio] - Baseline )",
        "+0.00;-0.00;0.00",
        TREND,
    ),

    # --- 08 Trend, the card captions ------------------------------------------
    # One string per KPI, arrow included. A reference label bound to one of these needs
    # nothing else configured, which keeps the card working regardless of which
    # formatting affordances a given Desktop build exposes. ABS() is deliberate: the
    # arrow already carries the sign and "v -0.3%" reads as a double negative.
    #
    # Each rounds to its own displayed precision first and formats the rounded value,
    # so the arrow and the number can never disagree. A movement too small to show is
    # not a movement: an arrow over "0,00" claims a direction the card cannot support,
    # and "no change" is both shorter and true.
    (
        "Headcount Comparison Label",
        "The headcount movement as one line of text, arrow included, for the card's reference\n"
        "label. Blank where there is no comparison period, so the card shows nothing rather\n"
        "than an empty arrow.",
        "VAR Movement = [Headcount Change % vs Previous Period]\n"
        "VAR Shown = ROUND ( Movement, 3 )\n"
        "RETURN\n"
        "    SWITCH (\n"
        "        TRUE (),\n"
        "        ISBLANK ( Movement ), BLANK (),\n"
        "        Shown = 0, \"no change \" & [Comparison Period],\n"
        "        UNICHAR ( IF ( Shown > 0, 9650, 9660 ) ) & \" \"\n"
        "            & FORMAT ( ABS ( Shown ), \"0.0%\" ) & \" \" & [Comparison Period]\n"
        "    )",
        "",
        TREND,
    ),
    (
        "Annualized Payroll USD Comparison Label",
        "Payroll movement as one line of text for the card's reference label.",
        "VAR Movement = [Annualized Payroll USD Change % vs Previous Period]\n"
        "VAR Shown = ROUND ( Movement, 3 )\n"
        "RETURN\n"
        "    SWITCH (\n"
        "        TRUE (),\n"
        "        ISBLANK ( Movement ), BLANK (),\n"
        "        Shown = 0, \"no change \" & [Comparison Period],\n"
        "        UNICHAR ( IF ( Shown > 0, 9650, 9660 ) ) & \" \"\n"
        "            & FORMAT ( ABS ( Shown ), \"0.0%\" ) & \" \" & [Comparison Period]\n"
        "    )",
        "",
        TREND,
    ),
    (
        "Voluntary Attrition % LTM Comparison Label",
        "Attrition movement as one line of text, in percentage points and labeled as such.\n"
        "The only card of the four whose direction means something on its own, which is why it\n"
        "is also the only one that should ever take color - conditional formatting on\n"
        "[Voluntary Attrition % LTM Change vs Previous Period] greater than zero.",
        "VAR Movement = [Voluntary Attrition % LTM Change vs Previous Period]\n"
        "VAR Shown = ROUND ( Movement, 3 )\n"
        "RETURN\n"
        "    SWITCH (\n"
        "        TRUE (),\n"
        "        ISBLANK ( Movement ), BLANK (),\n"
        "        Shown = 0, \"no change \" & [Comparison Period],\n"
        "        UNICHAR ( IF ( Shown > 0, 9650, 9660 ) ) & \" \"\n"
        "            & FORMAT ( ABS ( Shown ) * 100, \"0.0\" ) & \" pp \" & [Comparison Period]\n"
        "    )",
        "",
        TREND,
    ),
    (
        "Weighted Average Compa-Ratio Comparison Label",
        "Pay-position movement as one line of text, in ratio points.\n"
        "This is the card the stability case was written for: pay position moves in hundredths\n"
        "over a month, so a raw comparison is almost always a non-zero number that rounds to\n"
        "0,00 and takes an arrow anyway.",
        "VAR Movement = [Weighted Average Compa-Ratio Change vs Previous Period]\n"
        "VAR Shown = ROUND ( Movement, 2 )\n"
        "RETURN\n"
        "    SWITCH (\n"
        "        TRUE (),\n"
        "        ISBLANK ( Movement ), BLANK (),\n"
        "        Shown = 0, \"no change \" & [Comparison Period],\n"
        "        UNICHAR ( IF ( Shown > 0, 9650, 9660 ) ) & \" \"\n"
        "            & FORMAT ( ABS ( Shown ), \"0.00\" ) & \" \" & [Comparison Period]\n"
        "    )",
        "",
        TREND,
    ),

    # --- 10 Report, and the two page 2 needs ----------------------------------
    (
        "Last Data Refresh",
        "When the model last refreshed, as the value of a card.\n"
        "Reads the stamp frozen into 'Refresh Info' at refresh time rather than calling NOW()\n"
        "here, which would report when the reader opened the page.\n"
        "Returns the timestamp and nothing else - no \"Last data refresh:\" prefix. The card\n"
        "already carries that as its title, and a measure that repeats its own label cannot be\n"
        "placed anywhere the label is not wanted.\n"
        "Formatted yyyy-MM-dd HH:mm: all numeric, so it reads the same on a machine in any\n"
        "locale. A caption with a month name would come out in Spanish on this model, whose\n"
        "culture is es-ES, inside a report written in English.",
        "VAR Stamp = MAX ( 'Refresh Info'[refreshed_at] )\n"
        "RETURN\n"
        "    IF ( NOT ISBLANK ( Stamp ), FORMAT ( Stamp, \"yyyy-MM-dd HH:mm\" ) )",
        "",
        REPORT,
    ),
    (
        "Cells Scanned",
        "How many city / job / level cells the rule actually looks at. The denominator that\n"
        "stops \"four segments\" being read as \"four out of a handful\".\n"
        "\n"
        "Counted over the trailing twelve months, not at the last month-end, because that is\n"
        "the window every figure in the rule is computed over. Counting the closing snapshot\n"
        "instead returns 722 - it drops every cell that existed during the year and was empty\n"
        "by August, which are exactly the cells an attrition analysis should not lose sight of.\n"
        "\n"
        "The union with the movement fact adds one cell: a cell whose last leaver went before\n"
        "any surviving snapshot, so it has exits and no exposure. One row in 746, and it is the\n"
        "difference between this card agreeing with validation/reference_rule.py and quietly\n"
        "disagreeing with it.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR LastSnapshotDate = CALCULATE ( MAX ( Dim_Date[date] ), Dim_Date[date_key] = LastSnapshot )\n"
        "VAR Window = DATESINPERIOD ( Dim_Date[date], LastSnapshotDate, -12, MONTH )\n"
        "VAR Staffed =\n"
        "    CALCULATETABLE (\n"
        "        SUMMARIZE (\n"
        "            Facts_HeadCount,\n"
        "            Dim_Location[city], Dim_Job[job_code], Dim_Job[job_level]\n"
        "        ),\n"
        "        Window\n"
        "    )\n"
        "VAR Departed =\n"
        "    CALCULATETABLE (\n"
        "        SUMMARIZE (\n"
        "            Facts_Movement,\n"
        "            Dim_Location[city], Dim_Job[job_code], Dim_Job[job_level]\n"
        "        ),\n"
        "        Window,\n"
        "        Facts_Movement[event_type] = \"Voluntary Exit\"\n"
        "    )\n"
        "RETURN\n"
        "    COUNTROWS ( DISTINCT ( UNION ( Staffed, Departed ) ) )",
        "#,##0",
        DETECTION,
    ),
    (
        "Segments With A Rule Fired",
        "How many cells trip at least one of the three rules. A cell tripping two counts once:\n"
        "the question this answers is how many places need a conversation, not how many\n"
        "diagnoses were issued.\n"
        "This is the most expensive measure in the model - it evaluates all three rules, and\n"
        "so the Poisson tail, once per cell. On a card it is fine; do not put it on an axis.",
        "VAR Cells_rules =\n"
        "    ADDCOLUMNS (\n"
        "        SUMMARIZE (\n"
        "            Facts_HeadCount,\n"
        "            Dim_Location[city], Dim_Job[job_code], Dim_Job[job_level]\n"
        "        ),\n"
        "        \"@Rules\",\n"
        "            [Flag Pay Adjustment] + [Flag Internal Equity] + [Flag Organizational]\n"
        "    )\n"
        "RETURN\n"
        "    COUNTROWS ( FILTER ( Cells_rules, [@Rules] > 0 ) )",
        "#,##0",
        DETECTION,
    ),

    # --- Written by hand in Desktop, adopted here ------------------------------
    # The expressions are exactly as authored; what they were missing is a description
    # and a folder. None is renamed: a rename in TMDL does not follow through into the
    # report, and the two that a visual binds to by name would silently stop resolving.
    (
        "Attrition vs Baseline Material",
        "[Attrition vs Baseline] blanked below the thirty-person materiality floor, for the\n"
        "city-by-job-family matrix.\n"
        "The floor belongs in the measure rather than in the visual's filter pane for two\n"
        "reasons. A visual-level filter on a measure is not evaluated per cell in a matrix, so\n"
        "it silently fails to exclude anything. And a blank cell takes no conditional\n"
        "background, which is the actual risk: a ratio of 2.29 computed on eight people,\n"
        "painted navy, reads as a finding.",
        "IF ( [Headcount] >= 30, [Attrition vs Baseline] )",
        "0.00",
        MOVEMENT,
    ),
    (
        "Conditional Format Voluntary Attrition",
        "The font color for the attrition card's comparison label, as a hex string, bound\n"
        "through Format by field value.\n"
        "Attrition is the only one of the four headline figures whose direction means something\n"
        "on its own - headcount or payroll rising is neither good nor bad without context - so\n"
        "it is the only card that ever takes color. Rising is #B04A42; everything else stays\n"
        "the neutral #667085.",
        "IF ( [Voluntary Attrition % LTM Change vs Previous Period] > 0, \"#B04A42\", \"#667085\" )",
        "",
        REPORT,
    ),
    (
        "Voluntary Exits LTM Caption",
        "The exits card's sub-label: the same count expressed as a rate, so the headline number\n"
        "carries its own denominator instead of needing a second card.",
        "FORMAT ( [Voluntary Attrition % LTM], \"0.0%\" ) & \" of average headcount\"",
        "",
        REPORT,
    ),
    (
        "Segments With A Rule Fired Caption",
        "The detection card's sub-label. Four segments means nothing without the population it\n"
        "was drawn from; four out of 746 is the sentence.",
        "\"of \" & FORMAT ( [Cells Scanned], \"#,##0\" ) & \" cells scanned\"",
        "",
        REPORT,
    ),
    (
        "User",
        "The signed-in user's display name, for the banner greeting.\n"
        "USERPRINCIPALNAME() returns the Windows account in Power BI Desktop and the sign-in\n"
        "address in the Service, so the two never look the same. The fallback returns the raw\n"
        "principal, which means a reviewer who clones this repository sees their own machine\n"
        "account in the banner - worth replacing with a fixed word before anyone else opens it.",
        "VAR Principal = USERPRINCIPALNAME ()\n"
        "RETURN\n"
        "    IF ( Principal = \"AURELIO\\aleja\", \"Alejandro Tarazona\", Principal )",
        "",
        REPORT,
    ),
    # --- What the scan page counts and colors --------------------------------
    (
        "Cells Above Materiality Floor",
        "How many cells clear the thirty-person floor and are therefore worth a verdict.\n"
        "Sits between [Cells Scanned] and [Segments With A Rule Fired] and is the number that\n"
        "makes the other two legible: 746 scanned, 11 large enough to judge, 4 that fire. The\n"
        "middle figure is the one a reader silently assumes and usually assumes wrong.\n"
        "Cheaper than the fired count - it stops at headcount and never evaluates a rule.",
        "VAR Cells_material =\n"
        "    ADDCOLUMNS (\n"
        "        SUMMARIZE (\n"
        "            Facts_HeadCount,\n"
        "            Dim_Location[city], Dim_Job[job_code], Dim_Job[job_level]\n"
        "        ),\n"
        "        \"@Exposure\", [Average Headcount LTM]\n"
        "    )\n"
        "RETURN\n"
        "    COUNTROWS ( FILTER ( Cells_material, [@Exposure] >= 30 ) )",
        "#,##0",
        DETECTION,
    ),
    (
        "Conditional Format Rule Fired",
        "Row background for the scan table, as a hex string, bound through Format by field\n"
        "value. Four rows out of eleven carry a verdict and the other seven exist to show what\n"
        "the rule declined to flag; tinting the four is what stops a reader scanning the table\n"
        "as an undifferentiated list.",
        "IF ( NOT ISBLANK ( [Detection Rule Fired] ), \"#F4F8FD\", \"#FFFFFF\" )",
        "",
        REPORT,
    ),
    (
        "Conditional Format Detection Rule",
        "Point color for the scan scatter, as a hex string, bound through Data colors ->\n"
        "Format by field value.\n"
        "The scatter's Legend well takes a column and [Detection Rule Fired] is a measure, so\n"
        "there is no way to color the points by which rule fired through the field wells at\n"
        "all. Conditional formatting is the only route, and it costs the automatic legend -\n"
        "the page needs four colored squares and four words placed by hand.\n"
        "Ordered deliberately: a cell can trip more than one rule, and where that happens the\n"
        "pay verdict is the one shown, because it is the one that costs money.",
        "SWITCH (\n"
        "    TRUE (),\n"
        "    [Flag Pay Adjustment] = 1, \"#001552\",\n"
        "    [Flag Internal Equity] = 1, \"#3E72C4\",\n"
        "    [Flag Organizational] = 1, \"#6B97D8\",\n"
        "    \"#C9DAF3\"\n"
        ")",
        "",
        REPORT,
    ),

    # --- The targeted adjustment the recommendation page prices ---------------
    (
        "Compa-Ratio Target Value",
        "The compa-ratio currently selected on the Compa Target slicer, defaulting to 0.95.\n"
        "Lives in _Measures rather than on the parameter table, like its counterpart in\n"
        "09 Simulation, because that is where every measure in this model lives.",
        "SELECTEDVALUE ( 'Compa Target'[Compa-Ratio Target], 0.95 )",
        "0.00",
        SIMULATION,
    ),
    (
        "Cost to Target Compa-Ratio",
        "Annualized cost of lifting everyone paid below the selected compa-ratio up to it.\n"
        "The number a targeted adjustment actually costs, and the counterpart to\n"
        "[Blanket Increase Cost USD] on the overview.\n"
        "\n"
        "[Cost to Band Minimum] answers a different and much weaker question. The band minimum\n"
        "sits at 80% of midpoint across this survey, so a segment averaging 0.85 has only its\n"
        "lower tail beneath the floor. Lifting Bogota Data & Analytics to its band minimum\n"
        "costs $34,545 and leaves the segment at 0.85; lifting it to 0.95 costs $811,000. Only\n"
        "the second corresponds to the action being recommended.\n"
        "Nobody is moved downwards - MAX(..., 0) means people already above the target keep\n"
        "what they earn, which is how an adjustment actually works and why this is not simply\n"
        "the gap between the segment average and the target.",
        "VAR LastSnapshot = CALCULATE ( MAX ( Dim_Date[date_key] ), Facts_HeadCount )\n"
        "VAR Target = [Compa-Ratio Target Value]\n"
        "RETURN\n"
        "    CALCULATE (\n"
        "        SUMX (\n"
        "            Facts_HeadCount,\n"
        "            MAX (\n"
        "                Target * RELATED ( Dim_Market_Band[band_mid_usd] )\n"
        "                    - Facts_HeadCount[base_salary_usd_constant],\n"
        "                0\n"
        "            )\n"
        "        ),\n"
        "        Dim_Date[date_key] = LastSnapshot\n"
        "    )",
        "$#,##0",
        ECONOMICS,
    ),
    (
        "Payback Months at Target",
        "Months for a targeted adjustment to pay for itself, assuming it brings the segment's\n"
        "attrition down to the company baseline.\n"
        "The same arithmetic as [Payback Months] but costed against [Cost to Target\n"
        "Compa-Ratio] rather than against the band minimum, so the payback belongs to the\n"
        "intervention the page is recommending.\n"
        "Blank where attrition is already at or below the baseline: there is no avoided\n"
        "exposure to recover and a payback figure there would be invented. Dublin is the case\n"
        "in point - rule 2 catches it before attrition reacts, which is the whole argument for\n"
        "acting early and is also why this measure has nothing to say about it.",
        "VAR ExcessRate = [Voluntary Attrition % LTM] - [Company Attrition Baseline]\n"
        "VAR AvoidedExposure =\n"
        "    DIVIDE ( ExcessRate, [Voluntary Attrition % LTM] ) * [Attrition Exposure USD]\n"
        "RETURN\n"
        "    IF (\n"
        "        ExcessRate > 0,\n"
        "        DIVIDE ( [Cost to Target Compa-Ratio], DIVIDE ( AvoidedExposure, 12 ) )\n"
        "    )",
        "0.0",
        ECONOMICS,
    ),

    # --- The recommendation totals --------------------------------------------
    # These two exist because the recommendation spans two segments that share no
    # dimension value - Bogota Data & Analytics and Dublin Engineering IC5 - and a
    # visual-level filter can only AND across fields, never OR across segments.
    #
    # Scoping them by which rule fired rather than by naming the cities is the better
    # answer anyway: the cards then describe whatever the rule finds, and cannot drift
    # away from the argument the page is making if the data moves.
    #
    # Organizational segments are deliberately outside both. Singapore trips a rule and
    # carries $2.18M of exposure, and none of it is answered with a salary budget. A
    # total that swept it in would be adding up three different currencies of action.
    (
        "Recommended Spend USD",
        "Annualized cost of the adjustments this analysis recommends: every cell where the pay\n"
        "or the equity rule fired, lifted to the selected compa-ratio target.\n"
        "Excludes organizational findings on purpose - their lever is a supervisory layer, not\n"
        "money, and folding them into a spend figure would misstate both.\n"
        "Evaluates all three rules once per cell, so it is one of the slower measures in the\n"
        "model. Fine on a card; do not put it on an axis.",
        "VAR Cells_funded =\n"
        "    FILTER (\n"
        "        ADDCOLUMNS (\n"
        "            SUMMARIZE (\n"
        "                Facts_HeadCount,\n"
        "                Dim_Location[city], Dim_Job[job_code], Dim_Job[job_level]\n"
        "            ),\n"
        "            \"@Funded\", [Flag Pay Adjustment] + [Flag Internal Equity]\n"
        "        ),\n"
        "        [@Funded] > 0\n"
        "    )\n"
        "RETURN\n"
        "    SUMX ( Cells_funded, CALCULATE ( [Cost to Target Compa-Ratio] ) )",
        "$#,##0",
        ECONOMICS,
    ),
    (
        "Exposure Addressed USD",
        "Attrition exposure carried by the cells the recommended spend would act on. Read as\n"
        "the denominator of [Recommended Spend USD]: what the money is bought against.\n"
        "Scoped identically, so the two cannot describe different populations.",
        "VAR Cells_funded =\n"
        "    FILTER (\n"
        "        ADDCOLUMNS (\n"
        "            SUMMARIZE (\n"
        "                Facts_HeadCount,\n"
        "                Dim_Location[city], Dim_Job[job_code], Dim_Job[job_level]\n"
        "            ),\n"
        "            \"@Funded\", [Flag Pay Adjustment] + [Flag Internal Equity]\n"
        "        ),\n"
        "        [@Funded] > 0\n"
        "    )\n"
        "RETURN\n"
        "    SUMX ( Cells_funded, CALCULATE ( [Attrition Exposure USD] ) )",
        "$#,##0",
        ECONOMICS,
    ),

    # --- The action-card lines, as text ---------------------------------------
    # Two problems, one answer.
    #
    # The multi-row card formats numbers with the model's culture, which is es-ES and
    # cannot be changed after the model exists - so it renders $810.990 and 4,8 on a
    # page whose other visuals render $810,990 and 4.8. FORMAT with an explicit locale
    # takes the decision away from the model culture entirely.
    #
    # And two of the lines are comparisons - "p25 -> p74", "15.1 vs 6.7" - which no
    # number format can produce because they are two measures in one string.
    #
    # These return text, so they cannot be aggregated or sorted. That is acceptable
    # here and nowhere else: they are captions on a fixed recommendation card, and the
    # analytical measures they read are all still there to be used normally.
    (
        "Compa-Ratio Today Label",
        "Pay position for an action card, as text with the locale pinned to en-US.",
        "FORMAT ( [Weighted Average Compa-Ratio], \"0.00\", \"en-US\" )",
        "",
        REPORT,
    ),
    (
        "Cost to Target Label",
        "The targeted adjustment's cost for an action card, as text with the locale pinned.",
        "FORMAT ( [Cost to Target Compa-Ratio], \"$#,##0\", \"en-US\" )",
        "",
        REPORT,
    ),
    (
        "Exposure Carried Label",
        "Attrition exposure for an action card, as text with the locale pinned.",
        "FORMAT ( [Attrition Exposure USD], \"$#,##0\", \"en-US\" )",
        "",
        REPORT,
    ),
    (
        "Payback Label",
        "Payback for an action card, or the reason there is none.\n"
        "[Payback Months at Target] is blank where attrition sits at or below the baseline,\n"
        "and a blank line on a card reads as a missing number rather than as the finding it\n"
        "is. Dublin was caught before attrition reacted; the card should say so.",
        "VAR Months = [Payback Months at Target]\n"
        "RETURN\n"
        "    IF (\n"
        "        ISBLANK ( Months ),\n"
        "        \"No attrition yet\",\n"
        "        FORMAT ( Months, \"0.0\", \"en-US\" ) & \" months\"\n"
        "    )",
        "",
        REPORT,
    ),
    (
        "Cohort Percentile Gap",
        "Where the long-tenured cohort sits against the recent hires, as one line: p25 -> p74.\n"
        "Rule 2 is the comparison between these two numbers, not either one alone, so the card\n"
        "shows them as a single reading. Blank unless both cohorts clear twenty people, which\n"
        "is the population the rule itself requires before the comparison means anything.",
        "VAR Incumbents = [Incumbent Peer Percentile]\n"
        "VAR Recent = [Recent Hire Peer Percentile]\n"
        "RETURN\n"
        "    IF (\n"
        "        [Incumbent Headcount] >= 20 && [Recent Hire Headcount] >= 20,\n"
        "        \"p\" & FORMAT ( Incumbents * 100, \"0\", \"en-US\" )\n"
        "            & \" \" & UNICHAR ( 8594 ) & \" p\"\n"
        "            & FORMAT ( Recent * 100, \"0\", \"en-US\" )\n"
        "    )",
        "",
        REPORT,
    ),
    (
        "Span vs Company Label",
        "Span of control against the company mean, as one line: 15.1 vs 6.7.\n"
        "Rule 3 fires on the ratio between the two, and a card showing 15.1 alone leaves the\n"
        "reader to remember what normal looks like.",
        "FORMAT ( [Average Span of Control], \"0.0\", \"en-US\" )\n"
        "    & \" vs \" & FORMAT ( [Company Span Baseline], \"0.0\", \"en-US\" )",
        "",
        REPORT,
    ),
    (
        "Cost of a pay rise",
        "What a pay rise would cost this segment, or the fact that money is not the lever.\n"
        "The name is the row label the multi-row card displays, which is why it reads as a\n"
        "phrase rather than as a measure name - renaming it would change what the reader sees\n"
        "on the card, so it stays.\n"
        "\n"
        "It keys off the organizational flag rather than off a blank. The first version tested\n"
        "ISBLANK([% Above Band Maximum]), which worked only because COUNTROWS over an empty\n"
        "filter returns blank and nobody in Singapore Risk & Compliance sits above their band\n"
        "maximum. One person crossing that line would have turned the words \"Not the lever\"\n"
        "into a percentage, on a card whose whole argument is that this segment is not a pay\n"
        "problem.",
        "IF ( [Flag Organizational] = 1, \"Not the lever\", [Cost to Target Label] )",
        "",
        REPORT,
    ),
]


def quote(name: str) -> str:
    """A TMDL object name needs quoting unless it is a bare identifier."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else f"'{name}'"


def present(text: str, name: str) -> bool:
    """Is this measure already declared in the file?"""
    return f"\tmeasure {quote(name)} =" in text


def replace_measure(text: str, name: str, block: str) -> str:
    """Swap an existing measure - its description, expression and format - for a new block.

    The match runs from the first line of the /// description to the measure's own
    lineageTag, which is the last line every generated block carries. Without this the
    script could only ever add measures, and correcting one already in the model meant
    deleting it by hand first.
    """
    pattern = re.compile(
        r"(?:\n\t///[^\n]*)*\n\tmeasure " + re.escape(quote(name))
        + r" =.*?\n\t\tlineageTag: [0-9a-f-]+\n", re.S)
    match = pattern.search(text)
    if match is None:
        raise SystemExit(f"{name} is in the file but its block could not be located")
    return text[:match.start()] + "\n" + block.rstrip("\n") + "\n" + text[match.end():]


def render_measure(index: int, name: str, description: str, dax: str,
                   format_string: str, folder: str) -> str:
    """One measure as TMDL: description block, expression, format, folder, lineage."""
    quoted = quote(name)
    lines = [f"\t/// {line}".rstrip() for line in description.split("\n")]

    body = dax.split("\n")
    if len(body) == 1:
        lines.append(f"\tmeasure {quoted} = {body[0]}")
    else:
        lines.append(f"\tmeasure {quoted} =")
        lines += [f"\t\t\t{line}".rstrip() for line in body]

    if format_string:
        lines.append(f"\t\tformatString: {format_string}")
    lines.append(f"\t\tdisplayFolder: {folder}")
    lines.append(f"\t\tlineageTag: {TAG}{index:012d}")
    return "\n".join(lines) + "\n"


def main() -> None:
    # 1 · The parameter table.
    write(DEFINITION / "tables" / "Payroll Increase.tmdl", PAYROLL_INCREASE)

    # 2 · The measures, inserted before the placeholder column that ends _Measures.
    measures_path = DEFINITION / "tables" / "_Measures.tmdl"
    text = read(measures_path)
    anchor = "\tcolumn Value\n"
    assert anchor in text, "the _Measures placeholder column moved; check the file"
    # Indices are positional, so a measure keeps its lineage tag no matter how many of
    # its neighbours were already there. Appending to MEASURES is safe; reordering it
    # is not.
    inserted, updated = [], []
    for offset, measure in enumerate(MEASURES):
        block = render_measure(40 + offset, *measure)
        name = measure[0]
        if present(text, name):
            rewritten = replace_measure(text, name, block)
            if rewritten != text:
                text, _ = rewritten, updated.append(name)
        else:
            head, tail = text.split(anchor, 1)
            text = head + block + "\n" + anchor + tail
            inserted.append(name)
    write(measures_path, text)

    # 3 · Register the parameter table with the model. It goes after _Measures so the
    # field list orders it with the other non-star tables rather than among the
    # dimensions, which it is not.
    write(DEFINITION / "tables" / "Refresh Info.tmdl", REFRESH_INFO)
    write(DEFINITION / "tables" / "Compa Target.tmdl", COMPA_TARGET)

    model_path = DEFINITION / "model.tmdl"
    model = read(model_path)
    for table in ("Payroll Increase", "Refresh Info", "Compa Target"):
        if f"ref table '{table}'" not in model:
            model = model.replace("ref table LnFactorial\n",
                                  f"ref table LnFactorial\nref table '{table}'\n", 1)
    write(model_path, model)

    print(f"{len(inserted)} inserted, {len(updated)} updated, "
          f"{len(MEASURES) - len(inserted) - len(updated)} unchanged")
    for name in inserted:
        print(f"  + {name}")
    for name in updated:
        print(f"  ~ {name}")


if __name__ == "__main__":
    main()
