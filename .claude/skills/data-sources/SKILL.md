---
name: data-sources
description: Look up what a tracker ID (D01-D50), variable, source or category is, where it is downloaded from, how it is accessed and which ./data folder it belongs in, by reading the "Data Sources" sheet of data/Oil_Dedollarisation_Data_Tracker.xlsx. Use before any data fetching, cleaning or storing, and whenever the user mentions a tracker ID, a series/ticker, a source (FRED, EIA, JODI, Comtrade ...) or a category (fundamentals, market technicals, macro controls, geopolitics, currency markets).
---

# Data sources (tracker lookup)

The single source of truth for *what* data this project uses is the workbook
`data/Oil_Dedollarisation_Data_Tracker.xlsx`, sheet **Data Sources** (50 rows, IDs D01-D50). Never answer from
memory about a source: read the row.

## Look a row up

```
.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py                 # all rows, one line each
.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py D13 D19 D24     # full record per ID
.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py -c "Macro controls"
.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py -g comtrade     # text search
.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py --folders       # category -> folder
.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py D27 --json
```

Run it from the repo root (it walks up from the cwd to find `data/…xlsx`; `--xlsx <path>` or `$TRACKER_XLSX`
override). It needs `openpyxl`, which is in the project venv.

## Columns and what they mean for you

| column | use it for |
|---|---|
| `ID`, `Category`, `Variable` | identity; `Category` decides the folder (below) |
| `Specific series / ticker` | the exact series codes to request (e.g. `DCOILBRENTEU`, `WCESTUS1`) |
| `Primary source`, `URL` | where to download from first |
| `Alternative / backup source` | fallback when the primary is paid/blocked |
| `Frequency`, `Coverage from` | expected cadence and start year: use them as sanity checks on what you fetched |
| `Access`, `Format / API` | Free / Free (registration) / Free (API key) / Paid; CSV / API / Excel / PDF / Web |
| `Notes` | modelling hints (e.g. "handle April 2020 negative WTI before logs") |
| `Findings / limitations`, `Access check (2026-10-15)` | what actually worked when the URLs were tested; which sources block scripts |
| `Status`, `Date retrieved`, `Saved file / location` | the yellow progress cells. They are maintained in the workbook by the user, **not** by scripts: pipelines write suggested values to `data/<category>/clean/tracker_status.csv` |

## Category -> folder

Every row is stored under `./data/<category slug>/` where the slug is the Category lower-cased with spaces
replaced by underscores. This is the rule in `.claude/rules/data-layout.md`.

| Category | IDs | folder |
|---|---|---|
| Fundamentals | D01-D12 | `data/fundamentals/` (JODI rows D02/D09 are fetched by `data/jodi/` and only read from fundamentals) |
| Market technicals | D13-D29 | `data/market_technicals/` |
| Macro controls | D30-D36 | `data/macro_controls/` |
| Geopolitics | D37-D42 | `data/geopolitics/` |
| Currency markets | D43-D50 | `data/currency_markets/` |

A source shared by several rows (FRED, EIA STEO, EIA WPSR, Baumeister's page ...) is downloaded **once** into
the category folder of its rows; a source used by rows in two categories (FRED: D13-D25 and D30/D32/D35) is
downloaded in each category's own script so that each folder stays self-contained.

## Other sheets

- **Event Dates**: event-study dates (OPEC decisions, sanctions, INE launch ...) with a `Verified?` column.
- **Methodology**: which IDs each method needs (e.g. Johansen/VECM: D13, D19, D24). Useful to decide which rows
  to prioritise when a user asks for "the data for the cointegration test".
- **Summary**: counts by Status; formulas over the Data Sources sheet.

`reference.md` in this folder digests the per-source access findings (what blocks scripts, which keys exist,
manual steps). Read it before writing a downloader.
