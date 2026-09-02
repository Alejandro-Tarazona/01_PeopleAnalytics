# Source Data Design

How the source files in `data/raw/` were designed, and why they look the way they do.

---

## Provenance

The seven files in `data/raw/` are **synthetic**. They were generated to a
specification set out in this document; the generation itself was scripted with AI
assistance and is not part of this repository, because it is not where the analytical
value of this project lies.

This is a deliberate choice, not a shortcut. Real compensation and attrition data is
confidential and cannot be published. Synthetic data solves that — and it buys
something real data cannot give: **a known ground truth**. Because the anomalies in
this dataset were specified in advance, the analysis can be scored. Detection logic
that finds the two real problems and correctly dismisses the two decoys is
*measurably* correct, not just plausible.

What this repository demonstrates is everything downstream of the source files: the
ingestion and cleansing layer, the SQL transformations, the data validation suite, the
dimensional model, row-level security, and the analysis that ends in a costed
recommendation.

---

## The organization

**Meridian Payments Group (MPG)** — a global payments company, ~4,500 employees across
nine cities and four regions, operating a hub model.

| Region | Cities | Role |
|---|---|---|
| NAM | San Francisco, New York, Miami | Headquarters, product, commercial |
| LAC | Bogotá, São Paulo, Mexico City | Corporate services and technology hub |
| EMEA | Dublin, London | Technology and regulatory hub |
| APAC | Singapore | Commercial and risk hub |

Six business units (Technology, Product, Commercial, Risk & Compliance, Operations,
Corporate Services), ten job families, and a ten-step career ladder (IC1–IC6, M1–M4).

---

## Design principles

**1. Local currency is the source of truth.** Salaries are held in local currency with
an explicit currency code. USD amounts are always derived through the FX table, never
stored. Two rates are supplied per month and currency: actual (reconciles to Finance)
and constant (neutralises FX movement). COP and BRL depreciate deliberately over the
horizon — without that, a payroll variance bridge would have nothing to show.

**2. Nothing is pre-computed.** The extracts carry base salary, currency and manager
ID. Span of control and USD conversion are not columns — they are derived in the SQL
layer. Compa-ratio is not derived there either: it depends on the market band, which
enters through Power Query, so it is a DAX measure.

**3. The salary survey is dated to the analysis period.** Bands reflect the market at
the time of analysis, not at the start of the horizon. Comparing today's salaries
against a two-year-old band would flatter the whole company by roughly seven points of
compa-ratio.

**4. One source file is deliberately dirty.** `market_bands.xlsx` arrives the way a
salary survey actually arrives: four preamble rows before the header, 70 amounts
stored as currency-formatted text, 30 job codes with stray whitespace, 25 levels
written as "IC 3", two exact duplicate rows and a footer note. Cleansing it is part
of the exercise; proving it was cleansed correctly is part of the test suite.

**5. Attrition has causes, not correlations.** People leave when their *total* target
cash falls below market, or when their manager has too many direct reports. Never
because base salary alone is low. That distinction is what makes the decoys work.

---

## The four segments

Four anomalies are built into the data. **Only two should be acted on.**

All figures below are reproduced by `sql/build.sql` and the band cleansing — they are
verifiable from the repository, not asserted.

| Seg | Segment | HC | Base compa | TTC compa | Below band | Span | Attrition | vs. baseline | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **A** | Data & Analytics IC3–IC4 · Bogotá | 150 | 0.85 | 0.85 | 15 % | 7.9 | 32.7 % | 2.42× | **Detect — high priority** |
| **B** | Engineering IC5 · Dublin | 90 | 0.99 | 0.99 | 0 % | 7.6 | 10.0 % | 0.74× | **Detect — medium priority** |
| **C** | Sales IC3–M1 · São Paulo | 122 | 0.88 | 0.99 | 7 % | 5.0 | 15.8 % | 1.17× | **Dismiss** |
| **D** | Risk & Compliance IC2 · Singapore | 100 | 1.01 | 1.01 | 0 % | 15.1 | 28.0 % | 2.07× | **Dismiss** |

Company baseline: 13.5 % voluntary attrition, mean compa-ratio 0.98, mean span 6.7.
Voluntary attrition by region: LAC 16.4 % · APAC 14.8 % · EMEA 12.9 % · NAM 9.5 %.
Mean compa-ratio by region: APAC 1.01 · NAM 1.00 · EMEA 0.99 · LAC 0.94.

### A — the strong signal

Sustained pay drift. Mean compa-ratio of 0.85 and attrition at **2.4× the baseline**.
Only 15 % of the segment sits below band minimum: the band floor is 80 % of midpoint,
so drift of this size moves the whole distribution without pushing most of it under
the floor. This is the segment a correct analysis
must find and prioritize, and the one where a targeted adjustment pays for itself.

### B — invisible in the average

Salary compression. The segment average compa-ratio is 0.99, which looks healthy.
Cutting by tenure cohort tells a different story: incumbents with three or more years
sit at **0.912** while recent hires enter at **1.062** — a compression gap of 15
compa-ratio points. Attrition has not yet reacted, which is precisely the point: this
is an internal equity problem *before* it becomes an attrition problem. Finding it
requires an intra-level, intra-tenure cut that a segment-average view will miss.

### C — the designed false positive

Base compa-ratio of 0.88 looks like a problem. It is not. The variable target for this
segment is 41 % against a market norm of 25 %, so total target cash lands at 0.99. Its
attrition of 15.8 % is *below* LATAM's own 16.4 %: within its region, this segment is
not an outlier at all. **An analysis that reads base salary
in isolation will flag this segment and be wrong.** The correct recommendation is to
take no action here, and to say why.

### D — the second decoy

Attrition at 2.4× the baseline, which looks like the same problem as segment A. But
the compa-ratio is 1.01, comfortably inside band. The cause is organizational: span of
control of 15.1 against 6.7 across the rest of the company, and only 4 % of the segment
sits below band minimum. The correct recommendation
is a supervisory layer, not a pay adjustment — spending money here would not move the
number.

### Background noise

Roughly 3 % of employees carry a random compa-ratio deviation with no segment pattern.
This must not surface as a prioritized segment. It is the control for over-fitting.

---

## Why C and D matter most

Any analysis can find segment A. The segments that separate a competent analysis from
a superficial one are the two that must be rejected: C tests whether the analyst looks
at total compensation rather than base pay, and D tests whether the analyst considers
non-financial causes of attrition before recommending a spend.

A recommendation that explicitly states *"I am not recommending action in São Paulo or
Singapore, and here is why"* is the deliverable. A ranked list of every segment with a
low compa-ratio is not.

The machine-readable version of this specification, including the observed values for
every segment, is in [`ground_truth.json`](./ground_truth.json). The validation suite
scores detection logic against it and reports precision and recall.
