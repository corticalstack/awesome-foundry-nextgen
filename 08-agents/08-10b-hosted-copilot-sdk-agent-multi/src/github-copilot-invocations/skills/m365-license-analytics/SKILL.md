---
name: m365-license-analytics
description: Analyse Microsoft 365 license export CSVs - profile the data, compute per-SKU and per-department aggregates, identify reclaimable licenses, and return clean markdown tables.
---

# M365 license analytics

Use this whenever the user asks you to analyse an M365 license export CSV
(columns like `UserPrincipalName`, `Ext.5`, `Ext.6`, `AccountEnabled`,
`LastSignInDateTime`, `whenCreated`).

## Method

1. Locate the files (`find $HOME /files -name '*.csv' -o -name '*.json' 2>/dev/null`),
   inspect the header(s), and profile the data (row count, distinct values per
   column) before answering.
2. Prefer `python` / `pandas` for joins, date math, and aggregation; `awk` for
   quick counts. Show the computed numbers, not just prose.
3. **Costs and department names are not built in.** Join against whatever reference
   the caller uploads to the session (e.g. a `*-reference.json` with per-SKU monthly
   costs and department-code names). Never invent prices or department names.
4. Always return a **markdown table**, sorted as the user asked, and end with a
   one-line total or summary.

## Column glossary

| Column | Meaning |
|--------|---------|
| `UserPrincipalName` | The user's sign-in identity |
| `Ext.5` | License SKU (e.g. `SPE_E5`, `SPE_E3`, `ENTERPRISEPACK`) |
| `Ext.6` | Department code (resolve names from the uploaded reference) |
| `AccountEnabled` | `TRUE` / `FALSE` |
| `LastSignInDateTime` | Last interactive sign-in; may be empty |
| `whenCreated` | Account creation date |

## Reclaim candidates

A license is reclaimable if the user matches ANY of:
- `AccountEnabled` is `FALSE`, or
- `LastSignInDateTime` is non-empty and older than 90 days, or
- `LastSignInDateTime` is empty and `whenCreated` is older than 30 days.

Use the date the caller gives as "today" for all day-age math. Reclaimable spend
is the sum of those users' SKU cost, taken from the uploaded reference.
