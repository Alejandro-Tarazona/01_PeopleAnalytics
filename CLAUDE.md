# MPG People & Corporate Services Analytics

Business case with an end-to-end analytical asset. Source data is synthetic, designed
as a controlled test bed with a known ground truth.

## Hard rules

- **NEVER** edit files under `/model` or `/report` while Power BI Desktop is open.
  Desktop holds state in memory and will overwrite the changes.
- TMDL/PBIR files: UTF-8 **without BOM**, **CRLF** line endings.
- Do not invent columns or measures. Check `/model/**/definition/tables/` and
  `/docs/data-dictionary.md` before writing DAX.
- `/data/raw/` holds source extracts only. Never code, never pre-computed columns
  (compa-ratio, USD amounts, span of control), never ground-truth flags. All of that
  is derived in the SQL layer or in the model.
- Do not edit `/docs/case/ground_truth.json` to make an analysis pass. It is the
  answer key detection logic is scored against; changing it invalidates the project.
- Everything in this repository is written in **English** — code, comments, docs,
  measure names, column names, commit messages.

## Source of truth and derived values

- Salary in **local currency** (`base_salary_local` + `currency_code`) is the master value.
- USD amounts are **always derived** through `D_FXRate`. Never stored as master data.
- All pay-position and trend analysis uses **constant currency**
  (`rate_local_per_usd_constant`). The actual rate is only for Finance reconciliation.
- Span of control is derived from `manager_id`, not carried as a column.

## Modelling conventions

- Star schema. Facts prefixed `F_`, dimensions `D_`.
- All measures live in an empty `_Measures` table.
- Measure naming: `<Metric> <Qualifier>` — "Weighted Average Compa-Ratio",
  "Voluntary Attrition % LTM". English, consistent, no abbreviations.
- Explicit base measures only. Implicit aggregations are forbidden.
- Formatting: percentages 1 decimal · USD amounts no decimals with thousands separator
  · ratios 2 decimals.
- DAX: use `VAR` rather than repeating expressions. Maximum two levels of nested
  `CALCULATE`.
- Every measure carries a description explaining the **business rule**, not the syntax.

## Python conventions

- No absolute paths. Everything relative to the repository root.
- Type hints on public signatures. One-line docstrings saying *what*, not *how*.
- Tests must not depend on execution order or shared state.
- Keep it readable over clever: this code is read by reviewers, not just executed.

## Workflow

1. Read `/docs/data-dictionary.md` before touching the model.
2. After changing the SQL layer: `pytest tests/ -q`
3. After changing the model: regenerate docs with `python scripts/generate_docs.py`.
4. If a test fails, fix the code. Never adjust the test to make it pass.

## Case rules

- Segments **C (São Paulo)** and **D (Singapore)** are decoys by design. Any analysis
  that proposes a salary adjustment for them is wrong.
- C's real cause is a variable-pay target above market: the correct analysis compares
  **total target cash**, not base salary.
- D's real cause is organisational (span of control), not financial.
- If case figures disagree with what the data shows, **the data wins**. Adjust the
  narrative, never the other way round.

## Out of scope

- Do not analyse gender pay gap. The dimension exists in the model as an attribute
  only; the exclusion is documented in the README.
- Do not add CI/CD or Best Practice Analyzer unless asked. Outside the time budget.
