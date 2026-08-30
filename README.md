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
> modelling, security and the analysis that ends in a recommendation.

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
| 3 · Salary-survey cleansing in Power Query · data validation suite | Pending |
| 4 · Semantic model (PBIP/TMDL) and DAX measures | Pending |
| 5 · Hierarchical RLS and minimum group size rule | Pending |
| 6 · Python ↔ DAX reconciliation | Pending |
| 7 · Three-page report | Pending |
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
| `ref_job_catalog.csv` | 100 | Job catalogue: family, level, track. |
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
| **A** | Data & Analytics IC3–IC4 · Bogotá | 150 | **0.85** | 0.85 | 86 % | 7.9 | 34.7 % | **2.57×** | **Detect — high** |
| **B** | Engineering IC5 · Dublin | 90 | 0.99 | 0.99 | 22 % | 7.6 | 12.2 % | 0.91× | **Detect — medium** |
| **C** | Sales IC3–M1 · São Paulo | 122 | 0.88 | **0.99** | 62 % | 5.0 | 15.8 % | 1.17× | **Dismiss** |
| **D** | Risk & Compliance IC2 · Singapore | 100 | 1.01 | 1.01 | 4 % | **15.1** | 32.9 % | **2.44×** | **Dismiss** |

Company baseline: 13.5 % voluntary attrition, mean compa-ratio 0.98, mean span 6.7.

- **A** is the strong signal: 86 % of the segment sits below band minimum and attrition
  runs at 2.6× the baseline. This is where a targeted adjustment pays for itself.
- **B** is invisible in the segment average, which sits at 0.99. A tenure-cohort cut
  shows incumbents with 3+ years at **0.912** against recent hires at **1.062** — a
  15-point compression gap. Attrition has not reacted yet: an internal equity problem
  *before* it becomes a retention problem.
- **C** is a **designed false positive**: base compa-ratio 0.88, but a 41 % variable
  target against a 25 % market norm, so total target cash lands at 0.99. Its 15.8 %
  attrition is *below* LATAM's own 16.4 %. Only an analysis reading base salary in
  isolation flags it.
- **D** is the **second decoy**: attrition at 2.4× the baseline with a compa-ratio
  inside band and only 4 % below minimum. The cause is organisational — span of
  control of 15.1 against 6.7 company-wide. A pay adjustment here would resolve nothing.

Plus ~3 % of employees carrying random compa-ratio deviation with no segment pattern,
as a control against over-fitting.

Full specification: [`docs/case/data-design.md`](docs/case/data-design.md).
Machine-readable answer key: [`docs/case/ground_truth.json`](docs/case/ground_truth.json).

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
| Gender pay-gap analysis | Requires multivariate statistical control. On synthetic data the result would not be interpretable, so the dimension exists in the model as an attribute but is not analysed. |
| CI/CD and Best Practice Analyzer | High value, outside the time budget. First candidate for extension. |
| Fabric deployment / XMLA endpoint | Requires Premium capacity, unavailable in a personal environment. Quality gates run locally. |
| Licensed salary survey data | Proprietary. Bands are synthetic and calibrated against public cost-of-labour indices. |

---

## The SQL layer

PostgreSQL. Two schemas, one responsibility each: `raw` is the landing zone where
extracts arrive verbatim, `analytics` is the consumption layer Power BI reads.

| Script | Builds |
|---|---|
| `00_schema.sql` | Schemas, dropped and recreated so the build is idempotent |
| `01_load_raw.sql` | Typed landing tables and the `\copy` of six extracts |
| `02_dimensions.sql` | `d_date`, `d_employee`, `d_job`, `d_org`, `d_location`, `d_company`, `d_fx_rate` — surrogate keys throughout |
| `03_facts.sql` | `f_headcount` (employee × month) and `f_movement` (event), with span of control, currency conversion and internal pay position |
| `04_grants.sql` | Read-only role for Power BI. Password passed in at run time, never committed |

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

# 3. Create the read-only role Power BI connects with
psql -U postgres -d mpg_analytics -v reader_password='<your password>' -f sql/04_grants.sql
```

The build takes a few seconds and is idempotent. Source data is committed; nothing
needs to be generated.
