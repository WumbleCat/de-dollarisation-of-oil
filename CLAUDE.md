# de-dollarisation-oil

Research project on the de-dollarisation of oil markets (University of Bristol). Python 3.11+, project venv at
`.venv/` (run everything with `.venv/Scripts/python.exe`), pandas / openpyxl / statsmodels stack, notebooks in
`quant/`.

## What is where

```
data/Oil_Dedollarisation_Data_Tracker.xlsx   the data tracker: sheet "Data Sources" lists every series (D01-D50),
                                             its URL, access, format, status and limitations. Scripts READ it only.
data/<data type>/                            one folder per tracker category: raw/, clean/, download_*.py, clean_*.py
data/jodi/                                   JODI-Oil bulk database pipeline (feeds fundamentals rows D02/D09)
bristolpy/                                   the data library notebooks import (editable install): typed loaders over clean/
quant/                                       research notebooks (read data via bristolpy, never raw CSV paths)
.claude/skills/                              data-sources, data-fetch, data-store (see below)
.claude/rules/data-layout.md                 the storage rule
```

## Data rule (short form; full text in `.claude/rules/data-layout.md`)

Everything is stored in `./data/<data type>/` where `<data type>` is the tracker category slug:
`fundamentals` (D01-D12), `market_technicals` (D13-D29), `macro_controls` (D30-D36), `geopolitics` (D37-D42),
`currency_markets` (D43-D50). Raw files go to `raw/<source>/` with a `manifest.json`; cleaned tidy CSVs go to
`clean/` and are only written when `clean/CHECKS.md` passes. No data files anywhere else.

## Skills

- `data-sources`: look up any tracker row / category / source and its folder
  (`.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py D13`).
- `data-fetch`: download raw files for tracker rows into `data/<data type>/raw/` via `download_<data type>.py`.
- `data-store`: clean raw into `data/<data type>/clean/*.csv` with checks, register in `bristolpy`, write
  `tracker_status.csv` and the folder README.

Use them in that order for any "get me the data for ..." request.

## Conventions

- One `download_<data type>.py` and one `clean_<data type>.py` per category; one function per source; `--only`
  and `--refresh` flags; re-runs are idempotent.
- Tidy long CSVs with `tracker_ids, source, <dims>, unit, date, value, flag` (+ `vintage` for revised sources);
  no fills, clips or transformations in cleaners.
- Every cleaner writes `CHECKS.md`, `series_catalog.csv`, `tracker_status.csv`; a FAIL aborts the data write.
- API keys in `./.env` only (`FRED_API_KEY`, `EIA_API_KEY`, `COMTRADE_API_KEY`).
- Never modify the tracker workbook from code; never commit `raw/` or clean CSVs (see `.gitignore`).
- Known blockers: OPEC (Cloudflare), FRED CSV endpoint (Akamai; use the API key), Comtrade preview quota
  (~120 calls/hour), SWIFT / GSDB / Goldhub (registration or email request), ICE Gasoil (terminal only).
