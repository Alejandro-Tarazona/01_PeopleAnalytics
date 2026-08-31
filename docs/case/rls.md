# Row-Level Security

Compensation data is the most restricted dataset most companies hold. A People
Analytics model that ignores that is a model nobody in HR would deploy, so
security here is part of the design rather than something bolted on afterwards.

Two independent controls, answering two different questions.

| Control | Question | Mechanism |
|---|---|---|
| **Row-level security** | Which people may this person see at all? | Four roles, filtering by region, legal entity or business unit |
| **Minimum group size** | May this figure be displayed for this group? | Measures return blank below five employees |

They are separate on purpose. A regional HRBP may legitimately need pay detail
inside their region; a global analyst may legitimately need to see everyone but
only in aggregate. Collapsing the two into one setting forces a false choice
between scope and depth.

---

## The bridge table

`Dim_Security` maps a user to everything they may see. One row per user per
scope, so somebody covering two regions is two rows rather than a special case
in the DAX.

| Column | Meaning |
|---|---|
| `user_email` | Matched against `USERPRINCIPALNAME()`, stored lower-case |
| `scope_type` | `Global`, `Region`, `LegalEntity`, `BusinessUnit`, `CompensationAccess` |
| `scope_value` | The value granted, or `ALL` |
| `role_description` | Plain-language note, for whoever reviews the matrix |

It comes from `data/raw/ref_security.csv`, which means **the access matrix is a
file in the repository**: reviewable in a pull request, diffable when it changes,
and answerable to the question "who approved this access and when". An access
matrix living inside a report is none of those things.

The table is hidden in the model. It is plumbing, not something to slice by.

---

## The four roles

Create them in Power BI Desktop under `Modeling > Manage roles`. Each filters one
dimension; the filter propagates to the facts through the existing relationships,
so no fact table needs a rule of its own.

### Global HR

No filters. Full visibility.

### Regional HRBP — filter on `Dim_Location`

```dax
CONTAINS (
    FILTER (
        Dim_Security,
        Dim_Security[user_email] = LOWER ( USERPRINCIPALNAME () )
            && Dim_Security[scope_type] = "Region"
    ),
    Dim_Security[scope_value], Dim_Location[region]
)
```

### Country HR — filter on `Dim_Company`

```dax
CONTAINS (
    FILTER (
        Dim_Security,
        Dim_Security[user_email] = LOWER ( USERPRINCIPALNAME () )
            && Dim_Security[scope_type] = "LegalEntity"
    ),
    Dim_Security[scope_value], Dim_Company[legal_entity]
)
```

### BU HRBP — filter on `Dim_Organization`

```dax
CONTAINS (
    FILTER (
        Dim_Security,
        Dim_Security[user_email] = LOWER ( USERPRINCIPALNAME () )
            && Dim_Security[scope_type] = "BusinessUnit"
    ),
    Dim_Security[scope_value], Dim_Organization[business_unit]
)
```

The three filters are the same shape with one word changed, which is the point:
adding a fourth scope later means one more row type and one more role, not a
rewrite.

Each of them filters a dimension, and the dimension filters **both** facts. That is
worth stating because it was not true when these roles were written: the movement
fact carried no job, org or location key, so a regional role restricted the
headcount a viewer saw while leaving every exit visible. Block 6 added those keys,
and attrition is now scoped by the same three filters as everything else.

---

## Compensation access is not a role

The exemption from the minimum group size rule is an attribute in the bridge
table, not a fifth role.

A role controls **which rows** you see. The exemption controls **which figures
are displayed**. Making it a role would mean a regional HRBP could never be given
pay detail without also being given global visibility — the two would travel
together whether or not that was intended.

The hidden measure that reads it:

```dax
_Has Compensation Access =
NOT ISEMPTY (
    FILTER (
        ALL ( Dim_Security ),
        Dim_Security[user_email] = LOWER ( USERPRINCIPALNAME () )
            && Dim_Security[scope_type] = "CompensationAccess"
    )
)
```

`ALL` matters: without it, a role filtering `Dim_Security` would filter the very
table the exemption is read from.

Seven measures consult it — average and median base salary, both compa-ratios,
and the three band-position shares. All of them return blank below five employees
unless the viewer holds compensation access.

**Five, not three or ten.** Below five people a figure starts to identify
individuals: in a group of two, each person can derive the other's salary from
the average. Five is the threshold most compensation teams use and the one this
model applies everywhere, not only where somebody remembered to.

---

## Testing it

`Modeling > View as`, tick a role, and use **Other user** to supply the email the
role should resolve for. `USERPRINCIPALNAME()` returns that address, which is how
dynamic security is tested without deploying anything.

| Role | Test as | Expected |
|---|---|---|
| Regional HRBP | `lac.hrbp@mpg.example` | LAC only — around 1,580 employees |
| Regional HRBP | `emea.hrbp@mpg.example` | EMEA **and** APAC, the two-scope case |
| Country HR | `colombia.hr@mpg.example` | MPG Colombia S.A.S. only |
| BU HRBP | `tech.hrbp@mpg.example` | Technology, across every region |
| Global HR | `global.hr@mpg.example` | All 4,500 |
| Global HR | `comp.analyst@mpg.example` | All 4,500, **and** figures visible in groups below five |

The last two rows are the interesting pair: identical row visibility, different
figure visibility, driven entirely by the bridge table.

Screenshots of each go in `docs/rls-evidence/`. Security that is described but
never shown is a claim; security that is demonstrated is evidence.

---

## What this does not do

Honest limits, because a security model is judged on what it fails to stop.

- **Import mode means the data sits in the file.** RLS filters what a viewer sees
  through the report; it does not encrypt the model. Anyone who obtains the
  `.pbix` and can open it in Desktop sees everything. Real deployments rely on
  workspace permissions and sensitivity labels for that, and PBIP projects do not
  support sensitivity labels today.
- **The minimum group size rule stops the obvious disclosure, not a determined
  one.** Someone who can slice freely can still narrow a population down and
  compare totals across two nearly identical filters. Differential privacy is the
  real answer to that, and it is out of scope here.
- **The bridge table is only as good as its review.** Being a file in the
  repository is what makes review possible; it does not make review happen.
