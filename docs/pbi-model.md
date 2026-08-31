# Power BI Model

What the semantic model contains, how it is put together, and why each decision
was made that way. The model is stored as a Power BI project (`.pbip`), so the
tables, relationships and measures live in this repository as text and can be
reviewed in a diff like any other code.

```
PowerBI/MPG_PeopleAnalytics.pbip
PowerBI/MPG_PeopleAnalytics.SemanticModel/definition/   ← TMDL: tables, relationships, measures
PowerBI/MPG_PeopleAnalytics.Report/definition/          ← PBIR: pages and visuals
PowerBI/queries/segment_scan.dax                        ← the export contract for block 6
```

---

## Where the data comes from

Two sources, and the split is deliberate.

**PostgreSQL** supplies ten tables — the star schema built by `sql/build.sql`.
The model reads them with one-line queries (`SELECT * FROM analytics.Dim_Employee`).
All the heavy work — joins, window functions, currency conversion, span of
control — already happened in versioned SQL files where it can be tested.

**One Excel file** supplies one more: the vendor salary survey, cleansed in
Power Query. It is the only source that does not come from the database, because
it is the only one that does not belong there — a spreadsheet that arrives by
email every year, dirty, is a Power Query problem, not a warehouse problem.

That division is the point of the architecture: **logic in the database, thin
queries in the report**. A sixty-line query pasted into Power Query is buried
where it cannot be tested, reused, or reviewed. A one-line query says what the
report consumes and nothing more.

---

## The star

| Table | Grain | Rows | Source |
|---|---|---:|---|
| `Facts_HeadCount` | employee × month-end | 107,124 | PostgreSQL |
| `Facts_Movement` | one row per event | 12,261 | PostgreSQL |
| `Dim_Date` | one row per day | 1,096 | PostgreSQL |
| `Dim_Employee` | one row per person, active or not | 6,009 | PostgreSQL |
| `Dim_Job` | job code × level | 100 | PostgreSQL |
| `Dim_Organization` | business unit × department | 16 | PostgreSQL |
| `Dim_Location` | one row per city | 9 | PostgreSQL |
| `Dim_Company` | one row per legal entity | 7 | PostgreSQL |
| `Dim_FX_Rate` | month × currency | 168 | PostgreSQL |
| `Dim_Market_Band` | job code × level × geo tier | 400 | Excel, via Power Query |
| `Dim_Security` | user × access scope | 10 | PostgreSQL |
| `LnFactorial` | one row per integer 0–500 | 501 | Calculated in DAX |

`Dim_Security` and `LnFactorial` are both hidden and neither is part of the star.
The first drives row-level security ([`case/rls.md`](case/rls.md)); the second is a
table of mathematical constants that exists only so the Poisson tail in
`[Attrition p-value]` can be summed without a factorial overflowing a double. It is
disconnected on purpose — no filter, slicer or security role should ever reach it.

Two facts at different grains, and both are necessary. The snapshot answers
*"how did we look in March?"*; the event table answers *"what changed between
February and March?"* Attrition cannot be derived from snapshots alone, and pay
position cannot be derived from events alone.

### Relationships

Every relationship is many-to-one with a single filter direction, from fact to
dimension.

| From | To |
|---|---|
| `Facts_HeadCount[snapshot_date_key]` | `Dim_Date[date_key]` |
| `Facts_HeadCount[employee_key]` | `Dim_Employee[employee_key]` |
| `Facts_HeadCount[job_key]` | `Dim_Job[job_key]` |
| `Facts_HeadCount[org_key]` | `Dim_Organization[org_key]` |
| `Facts_HeadCount[location_key]` | `Dim_Location[location_key]` |
| `Facts_HeadCount[company_key]` | `Dim_Company[company_key]` |
| `Facts_HeadCount[band_key]` | `Dim_Market_Band[band_key]` |
| `Facts_Movement[event_date_key]` | `Dim_Date[date_key]` |
| `Facts_Movement[employee_key]` | `Dim_Employee[employee_key]` |
| `Facts_Movement[job_key]` | `Dim_Job[job_key]` |
| `Facts_Movement[org_key]` | `Dim_Organization[org_key]` |
| `Facts_Movement[location_key]` | `Dim_Location[location_key]` |
| `Facts_Movement[company_key]` | `Dim_Company[company_key]` |
| `Dim_Date[date_key]` | `Dim_FX_Rate[date_key]` |

**The movement fact carries its own dimension keys, and that is not optional.**
The first version of this model related it to the employee and the date alone,
which looks sufficient until somebody slices attrition by city: with no location
on the event, every city returned the *company* total. A wrong number that looks
entirely plausible. An event fact has to be conformed at the event — the keys are
fixed to the position the person held when it happened, which is also the only
correct attribution for a promotion or a transfer.

Filter direction stays single everywhere. Bidirectional filtering solves one
problem the day you turn it on and creates ambiguous results forever after.

---

## Design decisions

### The composite band key

The market band joins on **three** columns — job code, level and geographic tier
— and Power BI supports single-column relationships only.

Both sides therefore carry the same concatenated string:

```
DAT|IC3|T4
```

SQL builds it in `03_facts.sql`, Power Query builds it identically in
`Dim_Market_Band`. It is not elegant, and the alternatives are worse: a
`LOOKUPVALUE` evaluated once per row is slow and fragile, and moving the bands
into PostgreSQL would defeat the reason for cleansing them in Power Query.

### Compa-ratio is a measure, not a column

Pay position is calculated in DAX rather than stored, because it depends on
filter context. Averaging a stored per-row ratio gives the average of ratios,
which is not the ratio of averages and is the wrong number for any group.

Currency conversion goes the other way: it *is* a stored column, computed in SQL.
A row-level conversion is deterministic — it does not change with what is
filtered — so pushing it into the model would only make every measure heavier
and require a two-column relationship the engine does not support.

The rule: **deterministic at row level → SQL. Depends on filter context → DAX.**

### Import mode

The model imports rather than querying live. There is no Premium capacity behind
it, DirectQuery would put a local PostgreSQL instance in the path of every visual
interaction, and at 107,000 rows the entire model fits in memory comfortably.

### A read-only connection

Power BI connects as `mpg_reader`, which can select from `analytics` and cannot
see `raw` at all. A reporting tool has no business being able to drop a table,
and least privilege here costs two statements.

### Auto date/time off

Power BI's automatic date hierarchy creates a hidden calendar table for **every**
date column in the model. With a proper `Dim_Date` in place they are pure weight
— duplicated tables, a larger file, and two competing ways to slice by year.

`Dim_Date` is marked as the model's date table instead, which is what makes time
intelligence behave predictably.

---

## The salary survey cleansing

The one transformation that lives in the model. Eight steps, all declarative,
against a file that arrives the way vendor spreadsheets actually arrive.

The path comes from a **parameter** (`RepositoryFolder`), so no machine-specific
path is buried inside a query — anyone reproducing this changes one value.

```m
let
    FilePath = RepositoryFolder & "\data\raw\market_bands.xlsx",
    Source = Excel.Workbook(File.Contents(FilePath), null, true),
    Sheet = Source{0}[Data],

    // The vendor puts four rows of preamble above the real header, and is free to
    // change how many. Locate the header row instead of hard-coding a skip count.
    FirstColumn = List.Transform(
        Table.Column(Sheet, "Column1"),
        each if _ = null then "" else Text.Trim(Text.From(_))
    ),
    HeaderIndex = List.PositionOf(FirstColumn, "Job Code"),
    Located = if HeaderIndex = -1
              then error "No header row found in market_bands.xlsx: expected a cell reading 'Job Code'"
              else Table.Skip(Sheet, HeaderIndex),
    Promoted = Table.PromoteHeaders(Located, [PromoteAllScalars = true]),

    NoBlanks = Table.SelectRows(Promoted, each [Job Code] <> null),

    Trimmed = Table.TransformColumns(NoBlanks, {
        {"Job Code",   each Text.Trim(Text.From(_)), type text},
        {"Job Family", each Text.Trim(Text.From(_)), type text},
        {"Track",      each Text.Trim(Text.From(_)), type text},
        {"Geo Tier",   each Text.Trim(Text.From(_)), type text}
    }),

    // The vendor's footer note sits in the job code column. Keeping only rows whose
    // code matches the catalogue's shape removes it without hard-coding the note's
    // text, which the vendor is free to change between editions.
    OnlyJobCodes = Table.SelectRows(Trimmed, each
        Text.Length([Job Code]) = 3 and Text.Select([Job Code], {"A".."Z"}) = [Job Code]),

    // "IC 3" and "IC3" are the same level written two ways.
    Levels = Table.TransformColumns(OnlyJobCodes, {
        {"Job Level", each Text.Trim(Text.Replace(Text.From(_), " ", "")), type text}
    }),

    // Roughly 18% of the amounts arrive as currency-formatted text.
    ToAmount = (value) =>
        if value is number then value
        else Number.FromText(Text.Select(Text.From(value), {"0".."9", "."})),
    Amounts = Table.TransformColumns(Levels, {
        {"Band Min", ToAmount, type number},
        {"Band Mid", ToAmount, type number},
        {"Band Max", ToAmount, type number},
        {"Variable Target %", each Number.From(_), type number},
        {"Survey Year", each Int64.From(_), Int64.Type}
    }),

    WithKey = Table.AddColumn(Amounts, "band_key",
        each [Job Code] & "|" & [Job Level] & "|" & [Geo Tier], type text),

    // The vendor file contains one exact duplicate row.
    Deduplicated = Table.Distinct(WithKey, {"band_key"}),

    Renamed = Table.RenameColumns(Deduplicated, {
        {"Job Code", "job_code"}, {"Job Family", "job_family"},
        {"Job Level", "job_level"}, {"Track", "track"}, {"Geo Tier", "geo_tier"},
        {"Band Min", "band_min_usd"}, {"Band Mid", "band_mid_usd"},
        {"Band Max", "band_max_usd"},
        {"Variable Target %", "market_variable_pct"}, {"Survey Year", "survey_year"}
    }),
    Final = Table.SelectColumns(Renamed, {
        "band_key", "job_code", "job_family", "job_level", "track", "geo_tier",
        "band_min_usd", "band_mid_usd", "band_max_usd",
        "market_variable_pct", "survey_year"
    })
in
    Final
```

**The result must be 400 rows** — ten job codes × ten levels × four geographic
tiers, a complete grid with no duplicates.

That number is not decoration. The same cleansing exists a second time, in
`validation/bands.py`, and the two implementations are expected to agree exactly.
If this query drifts, the reconciliation catches it. Two independent
implementations of one rule that must match is double-entry bookkeeping applied
to data.

---

## Reproducing it

The `.pbip` is committed, so opening it is enough — but it needs a database
behind it and credentials it deliberately does not store.

**1. Build the database** (see the [README](../README.md)):

```powershell
psql -U postgres -d mpg_analytics -v reader_password='<choose one>' -f sql/04_role.sql
psql -U postgres -d mpg_analytics -v ON_ERROR_STOP=1 -f sql/build.sql
```

**2. Enable the PBIP format** in Power BI Desktop, if it is not already on:
`File > Options and settings > Options > Preview features` →
**Power BI Project (.pbip) save option**. Restart.

**3. Open** `PowerBI/MPG_PeopleAnalytics.pbip`.

**4. Point the parameter at your copy.** `Transform data > Manage parameters` →
set `RepositoryFolder` to wherever the repository was cloned.

**5. Supply credentials** when prompted: user `mpg_reader` and the password from
step 1. Privacy level Organizational.

**6. Refresh.** The row counts to expect are in the table above.

---

## Working on the model

**Close Power BI Desktop before editing the TMDL by hand.** Desktop holds the
model in memory and rewrites the files when it saves, so anything changed on disk
while it is open is lost. This is the single most common way to lose work in a
PBIP project, and it is the reason measures are written with the application
closed.

Naming, formatting and documentation conventions for measures are in
[`../CLAUDE.md`](../CLAUDE.md).
