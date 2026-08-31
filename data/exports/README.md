# Exports

Output from the semantic model, committed so the reconciliation can read it.

| File | Produced by |
|---|---|
| `segment_scan_pbi.csv` | The **Segment scan (export)** page → `Export data` → *Data with current layout* |

The columns and the grain are defined by
[`../../PowerBI/queries/segment_scan.dax`](../../PowerBI/queries/segment_scan.dax).
`tests/test_reconciliation.py` compares this file against an independent
implementation of the same rule in `validation/reference_rule.py`, then scores it
against `docs/case/ground_truth.json`.

**This file is an output, not a source.** It is committed because Power BI has no
XMLA endpoint without Premium capacity, so there is no way for Python to query the
model directly — the export is the only bridge between the two. It has to be
regenerated whenever the model changes, and the reconciliation tests skip with
instructions rather than failing when it is missing.
[`docs/case/reconciliation.md`](../../docs/case/reconciliation.md) explains what
the arrangement proves and what it does not.

Nothing here is read by the model, by SQL, or by the report. Deleting it costs
nothing but a re-export.
