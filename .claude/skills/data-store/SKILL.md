---
name: data-store
description: Clean, tidy, validate and store downloaded data as CSVs under ./data/<category>/clean/ with a CHECKS.md gate, then register it in bristolpy and the folder README and write tracker_status.csv. Use whenever the user asks to clean, tidy, normalise, store, save, process, merge, validate or "make available" data, or right after the data-fetch skill has downloaded raw files.
---

# Data store (clean + register)

Clean data lives in **`./data/<category slug>/clean/<source slug>.csv`** (rule: `.claude/rules/data-layout.md`).
One script per category, `data/<category>/clean_<category>.py`, raw -> clean, with sanity checks that must all
pass before any data file is written. Reference implementation: `data/fundamentals/clean_fundamentals.py`
(check registry `check / warn / info`, `write_checks_md`, `tracker_status`, `catalog_rows`). Start a new script
from `templates/clean_template.py` in this skill folder.

## Workflow

1. **Know the rows**: `.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py <IDs>`:
   `Frequency`, `Coverage from`, `Notes` tell you the expected cadence, start date and modelling caveats.
2. **Read raw/manifest.json** for which files exist and their status (`ok`, `manual`, `blocked`, `failed`).
   A `blocked`/`failed` source is reported, never silently skipped.
3. **Tidy long format**, one CSV per source, one row per observation:

   | column | rule |
   |---|---|
   | `tracker_ids` | `D13` or `D13;D14` when a row serves several tracker IDs |
   | `source` | source slug (same as the raw folder) |
   | dimension columns | `series_id`, `series_name`, `country`/`geo`, `product`, `table` ... as the source has them; keep source codes *and* labels |
   | `unit` | explicit, as published (`$/bbl`, `kb/d`, `index 2006=100`, `percent`) |
   | `date` | ISO `YYYY-MM-DD`: daily as is, weekly = week-ending date, monthly = first of month, quarterly = first day of quarter; annual data uses an integer `year` column instead |
   | `value` | float; empty when the source has no number |
   | `flag` | the source's non-numeric token kept verbatim (`.`, `-`, `..`, `x`, `N/A`, `e`, `p`) |
   | `vintage` | `YYYY-MM-DD` of the raw file for revised sources (forecasts, shock series, benchmark-revised series) |

   Never forward-fill, interpolate, clip or deflate in the cleaner: those are modelling steps (see tracker Notes,
   e.g. WTI 2020-04-20 negative price stays negative). Convert units only when the tracker row asks for it and
   keep both columns (`value_per_gal`, `value_per_bbl`).
4. **Checks** (every one is a `check()` call that lands in CHECKS.md; a FAIL aborts the write and exits 1):
   - reconciliation: every numeric cell in the raw file is in the output (count raw vs rows);
   - key uniqueness: no duplicate (series, date);
   - date contiguity at the declared frequency (gaps are listed, holidays allowed for daily);
   - coverage: first date <= tracker `Coverage from` + tolerance, last date within the expected lag of today;
   - plausible ranges (prices > 0 except known exceptions, shares in [0, 1], indices finite);
   - accounting identities inside the source (totals = sum of parts) and cross-source comparisons where two
     rows measure the same thing (e.g. FRED WTI vs EIA spot WTI);
   - `warn()` only for coverage gaps caused by the source's access limits, never for data errors.
5. **Write outputs** in `clean/`: `<source>.csv` per source, `series_catalog.csv`
   (`file,tracker_ids,series_key,first,last,n_obs,n_missing`), `tracker_status.csv`
   (`ID,Status,Date retrieved,Saved file / location`; Status from the workbook's dropdown: Not started, Located,
   Access requested, Downloaded, Cleaned, Merged into panel, Blocked / unavailable) and `CHECKS.md`
   (run time, `Result: ALL PASSED` or `FAILED`, counts `FAIL n · WARN n · PASS n · INFO n`, Outputs table with
   rows and columns, then one check table per source). Write CHECKS.md even when checks fail.
6. **Register in bristolpy** so the data is reachable from notebooks:
   - `bristolpy/paths.py`: `<CATEGORY> = DATA / "<slug>"`, `<CATEGORY>_CLEAN = <CATEGORY> / "clean"`;
   - a loader per source in the category module (`bristolpy/<slug>.py`, pattern of `fundamental.py`'s
     `_load_source` + `_filtered`: cached read, simple equality filters, `reload()`);
   - export it in `bristolpy/__init__.py` and document the calls in `bristolpy/README.md`.
7. **Document**: update `data/<category>/README.md` (layout, run commands, per-source table: IDs, raw, clean,
   notes) and `.gitignore` if a new bulky path appears (raw files and clean CSVs are ignored; scripts, READMEs,
   CHECKS.md, series_catalog.csv and tracker_status.csv are committed).
8. **Run and verify** with the project venv, read CHECKS.md, and report: rows per file, date range, every WARN,
   and the `tracker_status.csv` lines the user should paste into the workbook (the scripts never modify the
   workbook).

## Don'ts

- No data files outside `data/<category>/{raw,clean}` (not the repo root, not `quant/`, not `scripts/`, not tmp).
- No clean CSV without a passing CHECKS.md next to it.
- No wide/pivoted "convenience" CSVs in `clean/`: wide views are built in bristolpy (`wide=True`) or notebooks.
- Never hand-edit a clean CSV; fix the cleaner and re-run.
