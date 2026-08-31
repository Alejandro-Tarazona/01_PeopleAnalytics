# Reconciliation and Scoring

Two questions, in this order, because the second is worthless without the first.

1. **Does the model agree with an independent implementation of the same rule?**
   If the DAX and `validation/reference_rule.py` disagree, at least one of them is
   wrong and no score means anything.
2. **Given that they agree, does the rule find what is actually there?**
   Precision and recall against `ground_truth.json` — the answer key written
   before the data existed.

This is the reason the project uses synthetic data. On real data an analysis can
only be described. Here it can be marked.

---

## The honest limitation, first

**Python cannot query the semantic model.** Reading a Power BI model
programmatically needs the XMLA endpoint, and the XMLA endpoint needs Premium
capacity, which this project does not have. There is no way around it that does
not involve buying something.

So the bridge is a file. The model exports the scan, the export is committed, and
the reconciliation reads it:

```
Power BI ──► data/exports/segment_scan_pbi.csv ──► tests/test_reconciliation.py
                                                            ▲
PostgreSQL ──► validation/reference_rule.py ────────────────┘
```

This is a **golden-file test**. What it costs, stated plainly:

- The export is a manual step. It can go stale, and nothing but discipline stops
  the file being older than the model that produced it.
- It proves the model *as exported*, not the model as it stands right now.

What it still buys, which is most of the value:

- Every number the rule reads is checked against an independent implementation.
  A DAX mistake — a wrong filter context, a blank compared as zero, a measure
  quietly returning the grand total — surfaces as a failing test rather than as a
  slide nobody questions.
- The comparison is reproducible by anyone who clones the repository, refreshes
  and re-exports.

With an XMLA endpoint the same tests would run against the live model and the
manual step would disappear. Nothing else about them would change, which is the
point of keeping the export contract explicit.

---

## Producing the export

`PowerBI/queries/segment_scan.dax` is the definition: the grain, the columns and
the materiality filter. The CSV must be that query's result.

1. Rebuild the database and **refresh the model**. Block 6 added four dimension
   keys to the movement fact; without a refresh the new relationships have no
   data behind them.
2. Open the **Segment scan (export)** page, select the table visual — a *table*,
   not a matrix, with its totals row switched off — then `Export data` →
   **Data with current layout** → `.csv`. A matrix nests the three key columns
   into one hierarchy and exports blanks for the repeated levels; a table gives
   one flat row per cell, which is the grain the rule works at.
3. Save it as `data/exports/segment_scan_pbi.csv`.
4. `pytest tests/test_reconciliation.py -q`

Until the file exists the reconciliation tests skip with those instructions
rather than failing. A missing export means the model has not been refreshed
yet; it does not mean anything is broken, and a test suite that cannot tell the
difference trains people to ignore it.

Every measure on that page is formatted as a plain decimal — no percent signs, no
currency symbols, no thousands separators — because a reconciliation that trips
over `$46,622` is testing the export dialog rather than the model.
`validation/pbi_export.py` still sniffs the delimiter and the decimal separator,
since Power BI Desktop writes what the machine's locale tells it to and a
reviewer on a different regional setting should not see a false failure.

---

## What is compared, and to what precision

Each of the ten inputs the rule reads, cell by cell, plus the three verdicts.

| Compared | Why it is checked separately |
|---|---|
| `Average Headcount LTM`, `Voluntary Exits LTM` | The rate's two halves. A denominator on a different basis from the numerator is the classic way to manufacture a signal. |
| `Expected Exits LTM`, `Attrition p-value` | The significance test. Also checked for being *discriminating*: a measure returning blank everywhere would reconcile perfectly against nothing. |
| `Weighted Average TTC Compa-Ratio` | The single most consequential figure in the rule. |
| `Average Span of Control` | What separates a pay problem from an organisational one. |
| The four cohort figures | Rule 2 lives entirely in these; the cell average is blind to it by construction. |
| The three flags | Inputs can agree to four decimals and verdicts still differ when a value sits on a threshold. Worth knowing about explicitly. |

Comparison is to **the precision the export carries** — half a unit in the last
decimal place of each measure's format string. A figure formatted to two decimals
cannot be checked to six, and demanding it would fail on rounding rather than on
disagreement. The tolerances are declared in `validation/pbi_export.py` next to
the format strings they come from, so the two can never drift apart silently.

---

## The Poisson tail in DAX

DAX has no Poisson function and no factorial, so `[Attrition p-value]` computes the
exact one-sided tail by summing it:

```
P(X >= x) = 1 - SUM over k = 0..x-1 of EXP( -lambda + k*LN(lambda) - LN(k!) )
```

Working in logarithms is what makes it safe — 171! already overflows a double,
while `LN(k!)` for k = 500 is about 2,611 and every term stays comfortably in
range. `LN(k!)` comes from `LnFactorial`, a 501-row disconnected calculated table
built once at refresh, so the sum is a single `SUMX` over a lookup rather than a
factorial recomputed per term.

### Checking it without scipy

The first version of this checked the DAX against `scipy.stats.poisson`. That
stopped working: on a machine with Windows Application Control enabled, importing
`scipy.stats` fails because it pulls in `scipy.optimize`, whose compiled DLL the
policy blocks. Not a bug — a corporate control doing its job, and one that any
reviewer on a managed laptop would hit too.

The dependency went away instead. Forty lines of standard library replaced a 90 MB
package for a function used once, and the repository now needs pandas, openpyxl,
psycopg and pytest.

That removed the outside authority the DAX was measured against, so the check moved
inside. `validation/poisson.py` holds **two** implementations:

| | Method | Role |
|---|---|---|
| `survival` | Sums `EXP(-λ + k·ln λ − ln k!)`, mirroring the DAX line for line | What the reference rule uses |
| `survival_by_recurrence` | Multiplies each term by λ/k from `EXP(-λ)`. No logarithms, no gamma function | Checks the first |

The two share no arithmetic, so they have no plausible way to agree on a wrong
answer. `tests/test_reconciliation.py` requires them to agree to **1e-12** across
every rate and count the model produces, and pins three textbook values besides.
The DAX is then reconciled against `survival` cell by cell like every other figure.

Three implementations of one formula — DAX in logs, Python in logs, Python by
recurrence — is one more than strictly needed. It is also the reason a blocked DLL
turned into a better test instead of a blocked afternoon.

The alternative was to precompute the p-value in SQL. It was rejected: the
significance test is part of the *rule*, not part of the data, and the rule
belongs where the analyst can see and change it. Pushing it into the warehouse
would have made the DAX shorter and the analysis less honest about where its
judgement lives.

---

## Three defects this block found

All three are worth recording, because a reconciliation that never finds anything
is decoration. The third is the one that justifies the arrangement.

**The movement fact had no dimension keys.** `Facts_Movement` related only to
`Dim_Employee` and `Dim_Date`. Slicing attrition by city therefore returned the
*company* total for every city — a wrong number that looks entirely plausible and
would have gone straight into the report. Fixed in `03_facts.sql`: the movement
fact now carries its own job, org, location and company keys, fixed to the
position the person held when the event happened, which is also the only correct
attribution for a promotion or a transfer.

**Two silent row drops, one on each side.** Fixing the above with a `CROSS JOIN
LATERAL` quietly removed 77 events belonging to 76 people who left on the first
month-end of the horizon and so never appear in a snapshot. The same shape of
mistake was in the reference implementation, where a `how="left"` merge dropped a
single exit whose cell had no exposure — enough to move the company baseline in
the fourth decimal and shift every p-value in the model.

The second one is the instructive one. It was one row in 599, it changed no
verdict, and nothing but a tie-out to four decimal places would ever have found
it. Both are now explicit: the SQL filters with a comment and a test that pins the
count, and the reference raises rather than continues if the cell table stops
accounting for every exit.

**A city that was not the same city.** `\copy` reads the file on the client and
hands it to the server in whatever `client_encoding` that psql session happens to
have, which psql derives on Windows from the console code page. A build run from a
WIN1252 console read the UTF-8 bytes of `Bogotá` as latin-1 and re-encoded them, so
`d_location` stored a seven-character `BogotÃ¡`. Nothing raised. The row counts
were exact. The model imported it faithfully and the report rendered it.

It surfaced as **precision 50 %, recall 67 %** on a rule that was working
perfectly. The scoring matches a cell to a designed segment with `==` on the city,
and `BogotÃ¡` is not the `Bogotá` in `ground_truth.json`. Segment A went unfound,
and the two flags it had correctly fired were counted as false positives instead —
one defect, four failing tests, a headline score halved. Bogotá is the only
accented city among the segments carrying an `expected_rule`, which is why Dublin
and Singapore scored clean and the damage looked like a detection failure.

Then the part that earns it a place here: **this defect passed the numeric
reconciliation intact.** Zero disagreements across all fifteen numeric columns,
identical verdicts on all three flags, in all eleven cells. The DAX and the
reference agreed completely — because they were reading the same corrupted string
from the same database. A tie-out between two implementations can only find what
the two implementations disagree about, and a defect upstream of both is invisible
to it by construction. What caught this one was the second question: scoring
against an answer key written before the data existed, which is the only check in
the project that does not read from the warehouse.

It is also a lesson in where a broken score sends you looking. Recall drops, three
of the four flags are attrition-driven, and block 6 had just added four
relationships to the movement fact — so the first hypothesis is an inactive
relationship, and it is a good hypothesis. It was wrong twice over: the TMDL has
all four active, and had they not been, every cell would have returned the same
company-wide exit count instead of eleven different ones matching the reference
exactly. The evidence that clears the model is in the export the model produced.

`01_load_raw.sql` now declares `ENCODING 'UTF8'` on every `\copy`, so the load says
what it reads rather than inheriting it from the reviewer's terminal, and
`test_accented_text_survives_the_load` compares the dimension's spellings against
the source file so the declaration cannot rot. The same principle as
`validation/pbi_export.py` sniffing the delimiter: a format that varies by machine
is declared or detected, never assumed.

---

## The result

Eleven cells clear the thirty-person materiality floor, out of 746 in the
organisation. Four rules fire across them.

| City | Job | Level | HC LTM | Exits | Expected | *p* | TTC | Span | Rule fired |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Bogotá | DAT | IC3 | 70.7 | 24 | 9.5 | 0.000059 | 0.85 | 7.9 | **Pay adjustment** |
| Bogotá | DAT | IC4 | 79.4 | 25 | 10.7 | 0.000134 | 0.85 | 7.9 | **Pay adjustment** |
| Bogotá | ENG | IC2 | 30.8 | 5 | 4.2 | 0.402 | 0.98 | 6.5 | — |
| Bogotá | ENG | IC3 | 37.8 | 7 | 5.1 | 0.251 | 0.98 | 6.2 | — |
| Bogotá | OPS | IC3 | 35.1 | 8 | 4.7 | 0.107 | 0.95 | 6.3 | — |
| Dublin | ENG | IC5 | 90.0 | 9 | 12.1 | 0.854 | 0.99 | 7.6 | **Internal equity** |
| Miami | ENG | IC3 | 32.6 | 5 | 4.4 | 0.448 | 0.98 | 6.9 | — |
| Singapore | RSK | IC2 | 100.2 | 28 | 13.5 | 0.000373 | 1.01 | 15.1 | **Organisational** |
| São Paulo | SAL | IC3 | 35.1 | 8 | 4.7 | 0.107 | 1.00 | 3.6 | — |
| São Paulo | SAL | IC4 | 48.8 | 7 | 6.6 | 0.487 | 0.99 | 3.7 | — |
| São Paulo | SAL | M1 | 36.6 | 4 | 4.9 | 0.726 | 0.98 | 8.0 | — |

**Precision 100 %, recall 100 %.**

The rows that fire are not the interesting part. These are:

- **The three São Paulo rows are silent.** Base compa-ratio there is 0.88 and 62 %
  of the population sits below band minimum. Total target cash is 0.99, because a
  41 % variable target meets a 25 % market norm, and attrition is *below* LATAM's
  own rate. An analysis reading base salary alone recommends a raise for a
  population that was never underpaid.
- **Bogotá ENG and OPS look elevated and are not.** Attrition at 1.2× to 1.7× the
  baseline, on thirty to thirty-eight people. Every one of them fails the
  significance test. Under the "1.5× the baseline" rule of thumb this block
  replaced, Bogotá OPS IC3 and São Paulo SAL IC3 would both have been flagged —
  two false positives, on identical numbers, at *p* = 0.107.
- **Dublin fires on nothing to do with attrition.** Its attrition is 0.74× the
  baseline; *p* = 0.854. Rule 2 catches it through the cohort split alone —
  incumbents at the 25th peer percentile against recent hires at the 74th. It is
  the only segment found before attrition reacted, which is the only time an
  equity adjustment is cheap.
- **Singapore fires, and the answer is not money.** Attrition at 2.1× the
  baseline, *p* = 0.00037, compa-ratio 1.01, span of control 15.1 against 6.7
  company-wide. Rule 3 exists so that the analysis has more than one lever;
  without it, every problem starts to look like a pay problem.

Scoring runs off `expected_rule` rather than the business verdict. Segment D
carries the verdict *dismiss* because no pay adjustment is warranted there, yet a
rule should still fire on it. Dismissing a segment for pay and detecting it as an
organisational problem are the same correct answer said two ways.

---

## What would break this

- **The thresholds are calibrated on one organisation.** A company with different
  baseline attrition or a flatter pay structure needs them re-derived, not copied.
- **A perfect score on data built to be found is not a perfect score on real
  data.** What this demonstrates is that the logic separates a real signal from
  two plausible decoys — not that it would do so at an employer whose problems
  nobody wrote down in advance.
- **The export is manual.** See the first section. It is the weakest link and it
  is named rather than hidden.
