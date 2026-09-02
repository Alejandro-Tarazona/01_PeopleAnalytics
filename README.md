# MPG People & Corporate Services Analytics

An end-to-end business case on workforce cost exposure and retention risk: from raw
HRIS extracts to a costed recommendation for the executive committee.

> **On the data.** The source files in `data/raw/` are synthetic, generated to a
> specification I designed and documented in
> [`docs/case/data-design.md`](docs/case/data-design.md). Real compensation data is
> confidential and cannot be published — and synthetic data buys something real data
> cannot: a **known ground truth**. Because the anomalies were specified in advance,
> the analysis can be scored rather than merely asserted. This repository is about
> everything downstream of those files: ingestion, transformation, validation,
> modeling, security and the analysis that ends in a recommendation.

---

## The case

**Situation.** Meridian Payments Group (MPG) — a global payments company, 4,500
employees across nine cities and four regions, operating a hub model. LATAM holds
34 % of headcount and is the fastest-growing region.

**Complication.** Over the last twelve months voluntary attrition in LATAM reached
**16.4 %**, against **13.5 %** globally and 9.5 % in North America. LATAM also sits
lowest on pay position, at a mean compa-ratio of 0.94 against 0.98 company-wide. HR
has put a proposal to the executive committee: a **blanket 6 % salary adjustment
across the LATAM hub**.

**The CEO's question.**

> *"Before I approve this I need to know three things. Are we losing people
> everywhere, or in specific places? Is this actually a money problem? And if it is,
> what is the smallest number that fixes most of it?"*

The blanket 6 % is the proposal the analysis has to evaluate and, if the evidence
supports it, replace.

### Hypotheses

| # | Hypothesis | Expected verdict |
|---|---|---|
| H1 | Attrition is not company-wide; it concentrates in a small number of segments | Confirmed |
| H2 | The segments with the highest attrition sit below a 0.90 compa-ratio | Partially confirmed |
| H3 | Every segment with a low compa-ratio shows elevated attrition | **Rejected** |
| H4 | All elevated attrition has a compensation cause | **Rejected** |
| H5 | A blanket adjustment is economically inferior to a targeted one | Confirmed |

H3 and H4 carry the case. They are what block the lazy conclusion that paying more
fixes attrition, and each is rejected against a segment built into the data for that
purpose.

---

## Project status

| Block | Status |
|---|---|
| 1 · Source data and case design | **Complete** |
| 2 · SQL layer (PostgreSQL) | **Complete** |
| 3 · Data validation suite | **Complete** |
| 4 · Semantic model (PBIP/TMDL), Power Query cleansing and DAX measures | **Complete** |
| 5 · Hierarchical RLS and minimum group size rule | **Complete** |
| 6 · Python ↔ DAX reconciliation and detection scoring | **Complete** |
| 7 · Four-page Power BI report | **Complete** |
| 8 · Executive presentation | Pending |

---

## Source data

`data/raw/` holds source extracts only — CSV and Excel as a source system would hand
them over. No pre-computed columns: span of control and USD conversion are derived in
the SQL layer, compa-ratio in the semantic model.

| File | Rows | Simulated origin |
|---|---:|---|
| `market_bands.xlsx` | 404 | Salary survey from the compensation vendor. Deliberately dirty. |
| `fx_rates.csv` | 168 | Treasury. Actual and constant rate per month and currency. |
| `ref_locations.csv` | 9 | Corporate master: cities, regions, legal entities, cost index. |
| `ref_job_catalog.csv` | 100 | Job catalog: family, level, track. |
| `hris_employees.csv` | 6,009 | HRIS employee master. |
| `hris_headcount_monthly.csv` | 107,124 | Monthly headcount snapshot. Grain: employee × month. |
| `hris_movements.csv` | 12,338 | Events: hires, merit increases, promotions, exits. |

Horizon: 24 monthly closes, September 2024 to August 2026.

### Currency handling

Local currency is the source of truth; USD is always derived. `fx_rates.csv` carries
two rates per month and currency:

- `rate_local_per_usd_actual` — reproduces the accounting figure, reconciles to Finance.
- `rate_local_per_usd_constant` — base-month rate, neutralises FX movement.

All pay-position and trend analysis runs in **constant currency**. Without it, the
Colombian peso's depreciation over the horizon (3,900 → 4,420) would make Bogotá's
payroll "fall" in USD without a single salary having changed.

### The dirty file

`market_bands.xlsx` arrives the way a salary survey actually arrives: four preamble
rows before the header, 70 amounts stored as currency-formatted text, 30 job codes
with stray whitespace, 25 levels written as "IC 3", two exact duplicate rows and a
footer note. Cleansing it is part of the exercise; proving it was cleansed correctly
is part of the test suite.

---

## Ground truth

Four anomalies are built into the data. **Only two should be acted on.**

| Seg | Segment | HC | Base compa | TTC compa | Below band | Span | Attrition | vs. baseline | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **A** | Data & Analytics IC3–IC4 · Bogotá | 150 | **0.85** | 0.85 | 15 % | 7.9 | 32.7 % | **2.42×** | **Detect — high** |
| **B** | Engineering IC5 · Dublin | 90 | 0.99 | 0.99 | 0 % | 7.6 | 10.0 % | 0.74× | **Detect — medium** |
| **C** | Sales IC3–M1 · São Paulo | 122 | 0.88 | **0.99** | 7 % | 5.0 | 15.8 % | 1.17× | **Dismiss** |
| **D** | Risk & Compliance IC2 · Singapore | 100 | 1.01 | 1.01 | 0 % | **15.1** | 28.0 % | **2.07×** | **Dismiss** |

Company baseline: 13.5 % voluntary attrition, mean compa-ratio 0.98, mean span 6.7.

- **A** is the strong signal: a mean compa-ratio of 0.85 with attrition at 2.4× the
  baseline. Only 15 % of it sits below band minimum — the band floor is 80 % of
  midpoint, so sustained drift of this size moves the whole distribution without
  pushing most of it under the floor. Costing the fix to that floor would price it at
  $35K; lifting the segment to 0.95 of market costs $811K, and that is the number.
  This is where a targeted adjustment pays for itself, in under five months.
- **B** is invisible in the segment average, which sits at 0.99. A tenure-cohort cut
  shows incumbents with 3+ years at **0.912** against recent hires at **1.062** — a
  15-point compression gap. Attrition has not reacted yet: an internal equity problem
  *before* it becomes a retention problem.
- **C** is a **designed false positive**: base compa-ratio 0.88, but a 41 % variable
  target against a 25 % market norm, so total target cash lands at 0.99. Its 15.8 %
  attrition is *below* LATAM's own 16.4 %. Only an analysis reading base salary in
  isolation flags it.
- **D** is the **second decoy**: attrition at 2.1× the baseline with a compa-ratio
  inside band and nobody below minimum. The cause is organizational — span of
  control of 15.1 against 6.7 company-wide. A pay adjustment here would resolve nothing.

Plus ~3 % of employees carrying random compa-ratio deviation with no segment pattern,
as a control against over-fitting.

Full specification: [`docs/case/data-design.md`](docs/case/data-design.md).
Machine-readable answer key: [`docs/case/ground_truth.json`](docs/case/ground_truth.json).

---

## Validation

Python's only job in this repository is validation. It recomputes what SQL
produced and compares. **It does not produce findings** — those come from the
semantic model, and Python's role is to make the model's output checkable rather
than merely asserted.

Three levels, 63 tests:

| Level | What it proves |
|---|---|
| **Source** | Referential integrity, unique grain, closed domains, temporal coherence, and that the vendor survey was cleansed correctly — footer removed, duplicates dropped, `$120,000` parsed, `IC 3` normalized |
| **Transformation** | Every derived value recomputed independently in pandas from the source files and compared against SQL: currency conversion, span of control, target cash, the five-peer suppression rule, and that every source movement is either loaded or explained |
| **Reconciliation** | The Poisson tail itself, by two algorithms that share no arithmetic; then the DAX implementation of the prioritization rule against a second implementation of the same specification in pandas — ten inputs and three verdicts, cell by cell — and then that implementation scored against the answer key |

This is double-entry bookkeeping applied to data: two independent
implementations of the same calculation that must agree. It is the cheapest
insurance against the most expensive failure in BI, which is reporting a number
that does not match the source.

**It has earned its keep.** The reconciliation found that the movement fact
carried no dimension keys, so attrition sliced by city was returning the *company*
total for every city — a wrong number that looks entirely plausible and was on its
way into the report. Fixing that introduced a silent 77-row drop, and the tie-out
then caught a single lost exit, one row in 599, that moved the company attrition
baseline in the fourth decimal.
[`docs/case/reconciliation.md`](docs/case/reconciliation.md) has the details, the
method, and what the arrangement does **not** prove.

```bash
pytest
```

The 21 reconciliation tests skip with instructions until the model has been
refreshed and its scan exported to `data/exports/segment_scan_pbi.csv`; the other
42 need only a built database.

---

## The prioritization rule

Which segments get recommended for action is an explicit, written rule rather
than a judgement call over a dashboard: it can be reviewed, repeated by someone
else, and shown to be wrong. It is specified in
[`docs/case/detection-rule.md`](docs/case/detection-rule.md) and implemented
twice: as DAX measures in the semantic model, and as a reference implementation
in `validation/reference_rule.py` that exists only to check them.

Three problems need three different answers, so there are three rules: **pay
adjustment** (genuinely below market on total cash, with attrition to match),
**internal equity** (incumbents fallen behind their own recent hires), and
**organizational** (attrition is real but pay is not the cause).

The single most consequential choice is reading **total target cash rather than
base salary**. Base pay alone flags São Paulo Sales at 0.88 — a false positive
whose price is a raise for a population that was never underpaid.

An earlier draft used "attrition ≥ 1.5× the baseline". It was replaced by a
one-sided Poisson test, because at a 13.5 % baseline a 1.5× reading on thirty
people has a **22 % chance of being noise**. DAX has no Poisson function, so the
exact tail is summed in logarithms against a disconnected table of ln(k!), and
checked against two independent implementations in `validation/poisson.py` that
agree to 1e-12. The repository depends on pandas, openpyxl, psycopg and pytest —
scipy was removed once it turned out not to import on a machine with Windows
Application Control enabled, which is exactly the kind of machine a reviewer has.

Scanned against the answer key: **precision 100 %, recall 100 %.** Eleven of 746
cells clear the materiality floor and four rules fire, each inside the segment
that expects it. The near misses matter more than the hits — Bogotá Operations
and São Paulo Sales both run at 1.69× the baseline on thirty-five people, and the
significance test stops both at *p* = 0.107. Under the threshold this rule started
with, both would have been recommended for a raise.

---

## Critical assumption: the replacement factor

The entire economic recommendation rests on it. It expresses the cost of replacing
someone as a multiple of their annual salary: recruitment, interview time, onboarding,
team overload while the seat is empty, knowledge loss and — the largest component —
lost productivity during ramp-up.

| Job family | Factor |
|---|---|
| Operations | 0.5× |
| Finance · HR · Legal · Risk · Marketing | 1.0× |
| Engineering · Data & Analytics · Product · Sales | 1.5× |
| Management (M1–M4) | 2.0× |

HR literature puts the range between 0.5× and 2× of annual salary, rising with role
specialisation and ramp time. These figures are widely cited and rarely audited, so
the position taken here is not to defend a precise number but to **declare it as an
assumption and test its sensitivity**: the recommendation is evaluated at 1.0× / 1.5×
/ 2.0×, and slide 11 shows where it stops holding.

---

## Scope decisions

| Excluded | Reason |
|---|---|
| Gender pay-gap analysis | Requires multivariate statistical control. On synthetic data the result would not be interpretable, so the dimension exists in the model as an attribute but is not analyzed. |
| CI/CD and Best Practice Analyzer | High value, outside the time budget. First candidate for extension. |
| Fabric deployment / XMLA endpoint | Requires Premium capacity, unavailable in a personal environment. Its absence is why the reconciliation reads an exported file rather than querying the model live — [`reconciliation.md`](docs/case/reconciliation.md) sets out exactly what that costs. |
| Licensed salary survey data | Proprietary. Bands are synthetic and calibrated against public cost-of-labor indices. |

---

## The SQL layer

PostgreSQL. Two schemas, one responsibility each: `raw` is the landing zone where
extracts arrive verbatim, `analytics` is the consumption layer Power BI reads.

| Script | Builds |
|---|---|
| `00_schema.sql` | Schemas, dropped and recreated so the build is idempotent |
| `01_load_raw.sql` | Typed landing tables and the `\copy` of six extracts |
| `02_dimensions.sql` | `d_date`, `d_employee`, `d_job`, `d_org`, `d_location`, `d_company`, `d_fx_rate` — surrogate keys throughout |
| `03_facts.sql` | `f_headcount` (employee × month) and `f_movement` (event), with span of control, currency conversion, internal pay position, and the dimension keys that fix each event to the position held when it happened |
| `04_role.sql` | The read-only role Power BI connects with. Password passed in at run time, never committed |
| `05_grants.sql` | Its privileges, re-applied by `build.sql` as the last step — `DROP SCHEMA ... CASCADE` takes every grant with it, so a rebuild would otherwise leave the report disconnected |

**Nothing here is orphaned.** Every object in `analytics` is imported by the semantic
model. There are no exploratory views: anything DAX can compute natively — medians,
percentiles, tenure, rolling attrition — is left to DAX. SQL keeps only what it does
demonstrably better, which in practice means set-based work over the whole population:
span of control from the manager self-reference, and internal pay position via
`PERCENT_RANK` over each city × job × level cohort. The DAX equivalent of that last one
is a `RANKX` over a filtered table evaluated once per row; in SQL it is one pass.

**What the SQL layer deliberately does not own.** Anything relative to the market
band. The salary survey is cleansed in Power Query and joined in the semantic model,
so compa-ratio and band position are DAX measures. Currency conversion, by contrast,
*is* done in SQL: a row-level conversion is deterministic and does not depend on
filter context, so pushing it into the model would only make every measure heavier.

Power BI connects as `mpg_reader` and reads one-line native queries
(`SELECT * FROM analytics.d_employee`). The heavy logic lives in versioned `.sql`
files where it can be tested — not buried inside the report.

---

## Running it

```bash
# 1. Create the database
psql -U postgres -c "CREATE DATABASE mpg_analytics WITH ENCODING 'UTF8' \
     LC_COLLATE='C' LC_CTYPE='C' TEMPLATE=template0;"

# 2. Build it (from the repository root — \copy resolves paths from here)
psql -U postgres -d mpg_analytics -v ON_ERROR_STOP=1 -f sql/build.sql

# 3. Create the read-only role Power BI connects with (once)
psql -U postgres -d mpg_analytics -v reader_password='<your password>' -f sql/04_role.sql

# 4. Validate
pytest
```

The build takes a few seconds and is idempotent, and it re-applies the reader's
privileges every time, so a rebuild can never leave the report without access.
Source data is committed; nothing needs to be generated.

Step 3 comes after step 2 the first time only — the role has to exist before
`build.sql` can grant to it, and from then on `build.sql` handles it.

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/case/data-design.md`](docs/case/data-design.md) | How the source data was specified, and what was deliberately made dirty |
| [`docs/case/detection-rule.md`](docs/case/detection-rule.md) | The prioritization rule: every threshold and why it is what it is |
| [`docs/case/reconciliation.md`](docs/case/reconciliation.md) | How the model's output is checked and scored, and what that does not prove |
| [`docs/case/rls.md`](docs/case/rls.md) | Row-level security, the minimum group size rule, and the limits of both |
| [`docs/case/report.md`](docs/case/report.md) | What each report page is for, and what is deliberately left off it |
| [`docs/MPG_PeopleAnalytics_PBI_Report.pdf`](docs/MPG_PeopleAnalytics_PBI_Report.pdf) | The four report pages, each followed by its documentation panel |
| [`docs/pbi-model.md`](docs/pbi-model.md) | The semantic model: tables, relationships, and the reasoning behind each design decision |
| [`CLAUDE.md`](CLAUDE.md) | Conventions this repository is held to |
