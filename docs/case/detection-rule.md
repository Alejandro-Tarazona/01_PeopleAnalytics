# The Detection Rule

How a segment gets prioritised, why each threshold is what it is, and how the
logic is scored.

This is the **specification**, and it is implemented twice on purpose: as DAX
measures in the semantic model (`_Measures.tmdl`, display folder *07 Detection*)
and as a reference implementation in `validation/reference_rule.py`. The two are
required to agree cell for cell before either is scored against
[`ground_truth.json`](./ground_truth.json).

Findings come from the model. Python's role in this repository is validation
only: it mirrors this rule so the model's output can be measured rather than
asserted. How that works, and what it does not prove:
[`reconciliation.md`](./reconciliation.md).

---

## Why a rule at all

"Look at the dashboard and decide" is not a method. It cannot be reviewed, it
cannot be repeated by a colleague, and it cannot be wrong in a way anyone can
demonstrate. Writing the decision down as an explicit rule makes it all three.

The rule scans **every city × job × level cell in the organisation** — 746 of
them, of which 11 clear the materiality floor. It does not know the four designed segments exist. That is what makes the
score meaningful: the logic is not being tested on the answers it was built from.

---

## Three problems, three rules

Elevated attrition is not one condition with one treatment. Collapsing it into a
single "flag the segments with low pay" rule is precisely the mistake this case
is built to expose.

### Rule 1 · Pay adjustment

The segment is genuinely below market and losing people because of it.

| Condition | Threshold | Why |
|---|---|---|
| Materiality | ≥ 30 people | An intervention below thirty people is a case, not a policy |
| Significance | Poisson *p* < 0.05 | The attrition gap must be distinguishable from the baseline |
| Pay position | Total target cash compa-ratio < 0.92 | Total cash, not base salary — see below |
| Cause | Span of control ≤ 1.5× company mean | Otherwise the problem is organisational, not financial |

### Rule 2 · Internal equity

Incumbents have fallen behind the recent hires sitting next to them. Nothing is
wrong with the segment average; the problem only appears when the peer group is
split by tenure.

| Condition | Threshold |
|---|---|
| Incumbent cohort (3+ years) | ≥ 20 people, mean peer percentile ≤ 0.35 |
| Recent-hire cohort (< 3 years) | ≥ 20 people, mean peer percentile ≥ 0.65 |

No significance test here: this is a comparison of positions within a fixed
population, not a rate estimated from counts, so Poisson noise does not apply.

### Rule 3 · Organisational

Attrition is real and significant, but pay is not the explanation.

| Condition | Threshold |
|---|---|
| Significance | Poisson *p* < 0.05, materiality ≥ 30 |
| Pay position | Total target cash compa-ratio ≥ 0.95 — pay is fine |
| Cause | Span of control > 1.5× company mean |

The recommendation this rule produces is a supervisory layer, not money.

---

## Total cash, not base salary

The single most consequential choice in the rule. Base salary in isolation
flags São Paulo Sales at a compa-ratio of 0.88 — which looks like an obvious
problem and is not one. That population carries a 41 % variable target against a
25 % market norm, so total target cash lands at 0.99 and its attrition sits
*below* its own region's.

Any rule reading base pay alone produces a false positive there, and the cost of
that false positive is a salary increase for a population that was never
underpaid.

---

## Why significance replaced "1.5× the baseline"

The first draft of this rule used a headcount floor of 30 and an attrition
threshold of 1.5× the company baseline. Both were arbitrary, and the second one
does not survive contact with the arithmetic.

At a company baseline of 13.5 %, here is the probability of observing 1.5× the
baseline purely by chance:

| Segment size | Expected exits | Observed at 1.5× | *p* | Distinguishable? |
|---:|---:|---:|---:|---|
| 30 | 4.0 | 6 | 0.222 | no |
| 50 | 6.7 | 10 | 0.145 | no |
| 100 | 13.5 | 20 | 0.058 | no |
| 120 | 16.2 | 24 | 0.041 | **yes** |
| 150 | 20.2 | 30 | 0.025 | **yes** |

With thirty people, a 1.5× reading has a **22 % chance of being noise**.
Recommending a six-figure intervention on that basis is the error this project
exists to avoid, so the ratio threshold was replaced by a one-sided Poisson test
against the baseline rate.

Applied to the four designed segments:

| Segment | n | Expected | Observed | *p* | |
|---|---:|---:|---:|---:|---|
| A · Bogotá D&A | 150 | 20.2 | 52 | <0.0001 | significant |
| B · Dublin Eng | 90 | 12.1 | 11 | 0.667 | not significant |
| C · São Paulo Sales | 122 | 16.5 | 19 | 0.297 | not significant |
| D · Singapore Risk | 100 | 13.5 | 33 | <0.0001 | significant |

The test separates them without a judgement call.

---

## Three floors, three different jobs

The project uses three minimum-size thresholds and they are not interchangeable:

| Threshold | Question it answers | Where it applies |
|---|---|---|
| **5 people** | May this figure be displayed at all? | Confidentiality. Suppresses peer percentiles and, in the report, individual pay. A group of two is identifiable. |
| **30 people** | Is this worth a policy intervention? | Materiality. Below it, the answer is a conversation with a manager, not a compensation programme. |
| ***p* < 0.05** | Is this difference real? | Statistical. Guards against acting on noise. |

Being able to say which of the three applies, and why, is more useful than any
of them individually.

---

## Scoring

Precision and recall are computed at the cell grain the rules operate on.

- **Recall** — did each segment with an expected rule get flagged by that rule?
- **Precision** — of every cell flagged, how many fall inside a designed segment
  and fire the rule that segment expects?

Segment D carries the business verdict *dismiss* because no pay adjustment is
warranted, yet a rule should still fire on it — the organisational one.
Dismissing for pay and detecting as an org problem are the same correct answer
expressed two ways, so scoring runs off `expected_rule`, not the verdict.

**Measured: precision 100 %, recall 100 %.** Eleven of 746 cells clear the
materiality floor; four rules fire across them, and every one falls inside the
segment that expects it. Segment C is flagged by nothing, and nothing outside a
designed segment is flagged — the control against the 3 % of employees carrying
random pay deviation holds.

The near misses are more informative than the hits. Bogotá OPS IC3 and São Paulo
SAL IC3 both run at 1.69× the baseline on thirty-five people, and both fail the
significance test at *p* = 0.107. Under the "1.5× the baseline" threshold this
rule started with, both would have been flagged. Two false positives avoided by
one line of arithmetic.

Full results, and the reconciliation that makes them checkable rather than
asserted: [`reconciliation.md`](./reconciliation.md).

---

## What would change this rule

Honest limitations, in the order they would matter:

- **The thresholds are calibrated on one organisation.** A company with a
  different baseline attrition or a flatter pay structure would need them
  re-derived, not copied.
- **The Poisson test assumes exits are independent.** Team-level departures —
  one manager leaving and taking three people — violate that and would overstate
  significance. Worth checking exit clustering before acting.
- **Rule 2 has no significance test.** Cohort percentile comparisons on small
  populations are noisy in a different way, and a bootstrap would be the honest
  extension.
- **Span of control is a proxy.** It stands in for management quality, which is
  what actually drives the attrition it flags. It is the best available signal in
  HRIS data, not the cause itself.
