"""Print the model's export beside the reference, cell by cell.

`pytest` tells you a reconciliation failed and which column. This tells you what
the two sides actually said, which is the next question every time.

    python scripts/compare_export.py

Needs the database built and data/exports/segment_scan_pbi.csv present. Reads
both; writes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validation.db import connect                                    # noqa: E402
from validation.pbi_export import (DECIMALS, EXPORT_PATH, FLAGS,     # noqa: E402
                                   TEXT_COLUMNS, load_export, tolerance)
from validation.reference_rule import (CELL, MIN_MATERIALITY,        # noqa: E402
                                       segment_scan)


def main() -> int:
    if not EXPORT_PATH.exists():
        print(f"no export at {EXPORT_PATH}. Refresh the model and export the "
              "Segment scan page first.")
        return 1

    exported = load_export()
    with connect() as connection:
        scan = segment_scan(connection)
    reference = (scan[scan["avg_headcount_ltm"] >= MIN_MATERIALITY]
                 .sort_values(CELL).reset_index(drop=True))

    print(f"export {len(exported)} rows · reference {len(reference)} rows\n")

    paired = exported.merge(reference, on=CELL, how="outer",
                            suffixes=("_pbi", "_ref"), indicator=True)
    unmatched = paired[paired["_merge"] != "both"]
    if not unmatched.empty:
        print("CELLS ON ONE SIDE ONLY")
        print(unmatched[CELL + ["_merge"]].to_string(index=False), "\n")

    both = paired[paired["_merge"] == "both"]
    columns = [c for c in DECIMALS if c not in TEXT_COLUMNS]

    print("DISAGREEMENTS, worst first")
    rows = []
    for column in columns:
        limit = tolerance(column)
        gap = (both[f"{column}_pbi"] - both[f"{column}_ref"]).abs()
        for index in gap[gap > limit].index:
            rows.append({
                "cell": " / ".join(str(both.loc[index, k]) for k in CELL),
                "column": column,
                "power bi": both.loc[index, f"{column}_pbi"],
                "reference": both.loc[index, f"{column}_ref"],
                "gap": gap[index],
                "allowed": limit,
            })
    if rows:
        frame = pd.DataFrame(rows).sort_values("gap", ascending=False)
        print(frame.to_string(index=False))
    else:
        print("none — every figure agrees to the precision the export carries")

    print("\nVERDICTS")
    verdicts = both[CELL].copy()
    for flag in FLAGS:
        verdicts[flag] = [
            "both" if p == r == 1 else
            "POWER BI ONLY" if p == 1 else
            "REFERENCE ONLY" if r == 1 else "-"
            for p, r in zip(both[f"{flag}_pbi"], both[f"{flag}_ref"])
        ]
    print(verdicts.to_string(index=False))

    print("\nSIDE BY SIDE")
    for column in columns:
        wide = both[CELL + [f"{column}_pbi", f"{column}_ref"]].copy()
        wide.columns = CELL + ["power bi", "reference"]
        print(f"\n-- {column}")
        print(wide.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
