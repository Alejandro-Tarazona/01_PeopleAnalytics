# The Report

Four pages, in the order a decision gets made: what is the shape of the
organization and what is being proposed, is there a problem and what does it cost,
which segments and why those, what to do about each one.

This document states what each page is **for**. It does not describe how to build
it. Layout lives in the PBIP and Power BI Desktop is the tool that owns it —
a step-by-step written here would be stale the first time a visual moves, and a
stale build guide is worse than none because it invites someone to follow it.
What does not go stale is the question each page has to answer, and that is what
is recorded below. If a visual cannot be traced to one of these questions it does
not belong on the page.

---

## 1 · Overview

**Reads it:** anyone opening the report for the first time, and the same executive
coming back to check a number they half-remember.

**Answers:** what the organization looks like right now, how it got here, and what
the proposal on the table would cost. It is the only page with a time axis. The
other three are all point-in-time by construction, because a rule that fires on a
segment fires on the segment as it stands today.

The page carries the report's one interactive assumption: a slicer for the size of
a blanket salary increase, defaulting to the 6 % the executive committee has been
asked to approve. Two figures move with it — how much of the money lands on people
already at or above their band minimum, and how many people are still below
minimum once it has been spent. Together they are the arithmetic answer to *is
this a money problem*, and they are on the overview rather than the recommendation
page on purpose: this page frames the question, page 4 answers it.

**Must survive the page alone:** that a blanket increase large enough to fix the
worst-paid segment overpays everyone else, and that one the budget can carry
leaves that segment roughly where it was. A reader who takes only that away has
understood why the rest of the report exists.

**Deliberately absent:** any detection verdict. Nothing on this page says which
segments are a problem — that is what the scan is for, and asserting a conclusion
before showing the rule that produced it is the habit this report is built to
avoid.

**On filtering:** every base measure resolves the last month-end inside its own
filter context rather than against a fixed date. One month selected gives that
month's close, a year gives its December, and a month on a chart axis gives each
point its own close. The comparison against the previous period follows the same
logic: a single month compares against the month before, anything wider against
the year before, and the card labels itself from `Comparison Period` rather than
carrying a caption that would go stale the first time someone changed the slicer.

---

## 2 · Where the exposure is

**Reads it:** an executive who will give this five minutes and may never open
page 3.

**Answers:** how much attrition is costing over the next twelve months, and
whether that cost is concentrated or spread. The company figure is the headline;
the breakdown by city and job family exists to show that it is not spread evenly,
which is the entire premise of scanning at cell level rather than reporting a
company attrition rate.

**Must survive the page alone:** the exposure figure, and the count of segments
that warrant action. Someone who reads nothing else should still be able to
repeat those two numbers correctly.

**Deliberately absent:** any recommendation. Page 1 establishes that a problem
exists and sizes it. Naming the fix here would invite agreement before the
evidence for it has been shown.

---

## 3 · The scan

**Reads it:** an HR business partner or an analyst who has to be convinced, and
who may arrive already believing they know which team is the problem.

**Answers:** which of the 746 cells clear the materiality floor, and which of
those eleven carry a signal that is unlikely to be noise. This is the page that
makes the rule visible rather than asserted: the significance test is shown, not
summarized, so that a reader can see a cell running well above the baseline and
watch it fail to fire.

**Must survive the page alone:** that two cells at 1.7x the company baseline —
Bogotá Operations and São Paulo Sales, on thirty-five people each — do not fire,
because at that population the reading has a one-in-nine chance of being noise.
A reader who leaves believing "high attrition means act" has not been served by
this page.

**Deliberately absent:** the reconciliation. That the DAX agrees with an
independent implementation is a property of the asset, not a finding, and it
belongs in `reconciliation.md` and in the test suite. A report page defending its
own arithmetic reads as a report that expects to be doubted.

---

## 4 · What to do

**Reads it:** whoever signs off the budget, and the HRBP who has to deliver the
outcome.

**Answers:** for each segment that fired, what the intervention is, what it
costs, and how long it takes to pay for itself. Three rules mean three different
answers, and the page has to keep them distinct — a pay adjustment, an equity
correction and an organizational change are not interchangeable, and presenting
them as one list of "problem teams" loses the only distinction that matters.

**Must survive the page alone:** that São Paulo is **not** on the action list,
and why. Base compa-ratio there is 0.88 with 62 % below band minimum, and on base
salary alone it is the most under-paid population in the company. On total target
cash it is at 0.99 and its attrition is below its own region's. A report that
only shows what fired cannot demonstrate that it avoided the expensive mistake,
so the segment that was correctly left alone earns space here.

**Deliberately absent:** a sensitivity control on the replacement factor.
`Replacement Factor` is a fixed `SWITCH` in DAX. The disconnected-parameter
pattern that drives the blanket increase on page 1 would work here too, so this is
now a choice rather than a limitation, and the choice is to leave it out: the
factor is the assumption the entire economic case rests on, and a slider invites a
reader to move it without understanding what moved. It is declared on the page and
its sensitivity is reported in the presentation, where the range can be argued for
rather than dragged.

---

## The fifth page

**Segment scan (export)** stays in the file and stays hidden. It is the export
contract the reconciliation reads — `PowerBI/queries/segment_scan.dax` defines
its columns and `tests/test_reconciliation.py` fails if they change. It is not
part of the narrative and is not navigable, but deleting it breaks the test
suite. Its measures are formatted as plain decimals for the parser, which is also
why it must never be shown to a reader.

---

## What is not in the report at all

Gender pay gap. The dimension exists in the model as an attribute and the
exclusion is deliberate; see the README. A credible pay-equity analysis needs
controls this data set was not built to support, and running one anyway on
synthetic data would produce a finding that looks rigorous and is not.

---

## What the panels say

Each page carries an information button that opens an "About this page" panel. The
text is reproduced here because it makes claims about the data and those claims have
to be reviewable — a figure quoted in a panel is as capable of going stale as one in
a measure, and harder to notice.

### 1 · Overview

> **What this page is for.** MPG employs 4,500 people across nine cities. Voluntary
> attrition over the last twelve months is 13.5 % and base pay sits at 0.98 of market
> midpoint — a company that looks healthy in aggregate.
>
> The executive committee has been asked to approve a blanket 6 % salary adjustment
> across the LATAM hub. The simulator below prices it. At 6 %, $27.8M leaves the
> budget, 98 % of it lands on people already paid at or above their band minimum, and
> 37 people are still below minimum afterwards. Lifting everyone to minimum costs
> $533K.
>
> Nothing here says which teams are the problem. That is the next page's job —
> asserting a conclusion before showing the rule that produced it is the habit this
> report is built to avoid.
>
> **The figures.** Headcount is people on the books at the last month-end in view;
> monthly snapshots are never summed. Annualized Payroll USD is base pay only, in
> constant currency, so an exchange movement is never read as a pay decision.
> Voluntary Attrition % LTM counts voluntary exits over the trailing twelve months
> over average headcount across the same window, involuntary exits excluded. Weighted
> Average Compa-Ratio is base pay against market midpoint weighted by population,
> never an average of individual ratios, blank below five people. Company Attrition
> Baseline is the company rate with every filter removed, so the reference line holds
> still while you filter. "vs previous period" compares a single selected month
> against the month before and anything wider against the year before; each card says
> which. Payroll Increase % is a simulation control, not data, and opens on the 6 %
> actually proposed. Cost to Band Minimum is the targeted alternative — measured, not
> simulated.

### 2 · Where the exposure is

> **What this page is for.** Attrition costs MPG $83.3M over the next twelve months if
> nothing changes: 599 voluntary exits, each valued at the leaver's salary times the
> cost of replacing them.
>
> That cost is not spread evenly, and it does not sit where the exits sit. Bogotá lost
> 148 people — two and a half times more than any other city — and ranks fourth in
> exposure. Dublin lost 79, barely half, and ranks first. Exposure is exits multiplied
> by salary and by replacement cost, and LATAM salaries are lower. Counting heads and
> counting dollars point at different cities, and both readings are right for
> different questions.
>
> This page sizes the problem. It does not say which teams to act on. Four of 746
> cells trip a rule; the scan on the next page is where they are named.
>
> **The figures.** Attrition Exposure USD is voluntary exits over the last twelve
> months times average base salary times the replacement factor. The Replacement
> Factor is a declared assumption, not a measurement: 0.5× salary for Operations, 1.0×
> for corporate functions, 1.5× for Engineering, Data, Product and Sales, 2.0× for
> managers. Voluntary Exits LTM counts departures the employee chose; involuntary
> exits and internal transfers are excluded, because only the first is a retention
> problem. Segments With A Rule Fired counts cells tripping at least one of the three
> rules, and a cell tripping two counts once. Attrition vs Baseline is a cell's rate
> divided by the company rate, where 1.00 is the company average. The matrix shows
> city by job family only where thirty or more people sit in the cell; that floor
> covers 88 % of the population, and below it a ratio computed on eight people is
> noise wearing the clothes of a finding.

### 3 · The scan

> **What this page is for.** 746 cells were scanned. 11 hold thirty people or more —
> below that, an attrition rate is arithmetic on too few lives to act on. 4 of those
> eleven trip a rule.
>
> The point of this page is not the four. It is the seven that do not fire, and one
> pair in particular. Bogotá Operations IC3 and São Paulo Sales IC3 are identical: 35
> people, 8 voluntary exits against 4.7 expected, 1.69× the company baseline,
> *p* = 0.107. Neither fires. At that population an elevated reading has close to a
> one-in-nine chance of being noise, and this analysis will not spend a salary budget
> on a one-in-nine. Under the "1.5× the baseline" rule of thumb this rule replaced,
> both would have been recommended for a raise.
>
> Dublin fires on the lowest attrition on the page: 0.74× the baseline, *p* = 0.854.
> Rule 2 catches it through the tenure split alone — incumbents at the 25th peer
> percentile against recent hires at the 74th. It is the only segment found before
> attrition reacted, which is the only time an equity correction is cheap.
>
> **How to read the chart.** Horizontal is attrition against the company baseline,
> where 1.0 is the company rate. Vertical is the probability of seeing this many exits
> or more if the cell ran at that rate — log scale, and lower is stronger, so a cell
> near the bottom is one whose gap is hard to explain by chance. The dashed line is
> α = 0.05. Bubble size is average headcount, which is why the significance test
> matters: the same ratio on 100 people and on 35 are not the same finding.
>
> **The figures.** Attrition p-value is the one-sided Poisson probability of the
> observed exit count given the company rate; DAX has no Poisson function, so the
> exact tail is summed in logarithms against a table of ln(k!) and checked against two
> independent implementations in Python that agree to 1e-12. Expected Exits LTM is
> what the cell would have produced at the company rate, and exists to be compared
> against the actual count. TTC is total target cash against market, base plus
> variable — the single most consequential choice in the rule, because base pay alone
> puts São Paulo Sales at 0.88 and recommends a raise for a population that was never
> underpaid. Average Span of Control is reports per manager, and separates a pay
> problem from an organizational one. The materiality floor is thirty people: a rule
> that cannot act below thirty has no business reporting below thirty.

### 4 · What to do

> **What this page is for.** The proposal on the table was a blanket 6 % across the
> LATAM hub: $5.40M, of which 95 % would land on people already paid at or above their
> band minimum, leaving 23 people in LATAM still below it.
>
> This page proposes $1.15M instead, on two segments, against the $5.76M of attrition
> exposure those segments carry. It pays for itself in under five months on the
> segment that drives it.
>
> Three findings, three different levers. That is the whole argument. Singapore
> carries $2.18M of exposure and appears here with no cost at all — its compa-ratio is
> 1.01 and its span of control is 15.1 against a company mean of 6.7. Buying that
> problem a salary budget would be spending money on the wrong diagnosis.
>
> São Paulo is on this page because it is not on the list. On base salary it is the
> most under-paid population in the company. On total target cash it sits at market,
> and its attrition is inside the noise. An analysis that only showed what fired could
> not demonstrate that it avoided the expensive mistake.
>
> **The figures.** Recommended Spend USD is what it costs to lift every cell where the
> pay or the equity rule fired to the selected compa-ratio target, scoped by which
> rule fired rather than by which city. Cost to Target Compa-Ratio is not the cost of
> reaching band minimum: the band floor sits at 80 % of midpoint throughout this
> survey, so lifting Bogotá Data & Analytics to it costs $35K and leaves the segment
> at 0.85, while lifting it to 0.95 costs $811K. Payback Months at Target is blank
> where attrition already sits at or below the baseline — Dublin was caught before
> attrition reacted, and inventing a payback there would be inventing a benefit.
>
> **Three assumptions, stated.** The replacement factor runs from 0.5× salary for
> Operations to 2.0× for managers; those figures are widely cited, rarely audited, and
> every payback on this page moves with them. The 0.95 target is a choice, not a
> finding, set below the company mean of 0.98 because the recommendation is to close a
> gap rather than to overtake the market. And the payback is the optimistic case: it
> assumes the adjustment brings attrition all the way down to the company baseline,
> and pay is one of several reasons people leave.

### The export page

> **This is not a report page.** It is the export contract.
> `PowerBI/queries/segment_scan.dax` defines its grain, its columns and its
> materiality filter, and `tests/test_reconciliation.py` compares every cell of it
> against `validation/reference_rule.py`.
>
> Every measure on this page is formatted as a plain decimal — no percent signs, no
> currency symbols, no thousands separators. The export writes what is displayed, and
> a reconciliation that trips over `$46,622` is testing the export dialog rather than
> the model. Changing a format here breaks the test suite. It must stay a table rather
> than a matrix, because a matrix nests the three key columns into a hierarchy and
> exports blanks for repeated levels. Totals off: a totals row is not a cell.
