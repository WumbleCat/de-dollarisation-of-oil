# Data layout rule

All data in this repository lives under **`./data/<data type>/`**, where `<data type>` is the tracker
category of the source: the `Category` column of `data/Oil_Dedollarisation_Data_Tracker.xlsx`, sheet
"Data Sources", lower-cased with spaces replaced by underscores.

| Category (tracker) | IDs | folder |
|---|---|---|
| Fundamentals | D01-D12 | `data/fundamentals/` |
| Market technicals | D13-D29 | `data/market_technicals/` |
| Macro controls | D30-D36 | `data/macro_controls/` |
| Geopolitics | D37-D42 | `data/geopolitics/` |
| Currency markets | D43-D50 | `data/currency_markets/` |
| (JODI-Oil bulk database, feeds D02/D09) | – | `data/jodi/` |

Inside every category folder:

```
data/<data type>/
  download_<data type>.py   every raw file for the category -> raw/<source>/ (+ raw/manifest.json)
  clean_<data type>.py      raw/ -> clean/<source>.csv, series_catalog.csv, tracker_status.csv, CHECKS.md
  README.md                 what is here, how to run it, per-source table (IDs, raw, clean, limits)
  raw/<source>/             untouched source files, one folder per source; vintages/ for revised files
  clean/                    tidy long CSVs + CHECKS.md (the gate) + series_catalog.csv + tracker_status.csv
```

Rules:

1. **Nothing is stored anywhere else.** Not the repo root, not `quant/`, not `bristolpy/`, not a `scripts/`
   folder, not a temp directory. A new source goes into the folder of its tracker category; if the tracker
   has no row for it, add the row to the workbook first (ask the user) and then use its category.
2. **Raw is immutable**: files are kept as served, never edited; revised publications get a dated copy in
   `raw/<source>/vintages/`. Anything hand-collected (PDF tables, email deliveries) goes in
   `raw/<source>/manual/` with a README stating where it came from and when.
3. **Clean is generated**: every `clean/*.csv` comes from the category's `clean_*.py` and is only written when
   every check in `clean/CHECKS.md` passes (`Result: ALL PASSED`). Never hand-edit a clean file.
4. **The workbook is read-only for scripts.** Suggested Status / Date retrieved / Saved file values go to
   `clean/tracker_status.csv` for the user to paste into the yellow cells.
5. **Code reads data through `bristolpy`**: register new folders and files in `bristolpy/paths.py` and add
   loaders; notebooks in `quant/` must not open CSV paths directly.
6. **Git**: `data/*/raw/` and `data/*/clean/*.csv` are ignored (bulky, regenerable); scripts, READMEs,
   CHECKS.md, series_catalog.csv, tracker_status.csv and the tracker workbook are committed.
7. **Secrets** (`FRED_API_KEY`, `EIA_API_KEY`, `COMTRADE_API_KEY` ...) live in `./.env` (git-ignored) and are
   never written into code, manifests or output.
8. Run every pipeline with the project venv: `.venv/Scripts/python.exe data/<data type>/<script>.py`.

Use the project skills: `data-sources` (look a row up), `data-fetch` (download), `data-store` (clean + register).
