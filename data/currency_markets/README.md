# Currency markets data (tracker rows D43–D50)

Everything for the *Currency markets* category of `data/Oil_Dedollarisation_Data_Tracker.xlsx` (sheet "Data Sources")
lives here, in the same layout as `data/fundamentals/`:

```
data/currency_markets/
  download_currency_markets.py   pull every raw file -> raw/ (+ raw/manifest.json with url, status, sha256, timestamp)
  clean_currency_markets.py      raw/ -> clean/*.csv, with sanity checks that must all pass
  raw/                           untouched source files, one folder per source (gitignored except READMEs)
  clean/                         tidy CSVs + CHECKS.md + series_catalog.csv + tracker_status.csv (CSVs gitignored)
```

Run (project venv; stdlib + pandas/openpyxl/xlrd/pypdf — `uv pip install --python .venv/Scripts/python.exe pypdf`):

```
.venv/Scripts/python.exe data/currency_markets/download_currency_markets.py      # ~90 s
.venv/Scripts/python.exe data/currency_markets/clean_currency_markets.py         # ~1 min (BIS bulk file is 730 MB unzipped)
```

Read the results with `bristolpy.currency` (see `bristolpy/README.md`).

## Sources

| ID | Tracker source | What was actually fetched | Raw | Clean | Coverage |
|---|---|---|---|---|---|
| D43 | IMF WP – Boz, Casas, Georgiadis, Gopinath, Le Mezo, Mehl & Nguyen invoicing dataset | imf.org refuses scripted requests (403); the authors' replication files on **Mendeley Data** (doi 10.17632/6z6w78968m.1, `Section2.zip`) carry the same `all_countries_update.dta` | `raw/imf_invoicing/` | `imf_invoicing_currency.csv` – country × year × flow × currency, % | annual 1990–2019, 110 countries (no update since the 2022 JIE paper) |
| D44 | PBoC RMB Internationalisation Report | **SAFE** "Cross-border Receipts and Payments by Non-banking Sectors" time series – monthly receipts / payments / balance *by currency* (RMB, USD, HKD, EUR, JPY, other) and by transaction (goods, services, income, FDI, portfolio, other), in CNY and USD sheets. PBoC report PDFs (2016–2025) are saved raw but not parsed | `raw/safe/`, `raw/pboc_rmb_report/` | `safe_crossborder_by_currency.csv` (long) and `safe_rmb_share.csv` (RMB share of receipts / payments / total, %) | monthly 2010-01 → 2026-09, annual 2010 → 2025 |
| D45 | IMF COFER | IMF SDMX 3.0 API (`api.imf.org`, dataflow `IMF.STA/COFER`) – the data.imf.org portal itself 403s scripts | `raw/imf_cofer/` | `imf_cofer.csv` – world / advanced / EMDE × indicator (allocated, unallocated, total) × currency × shares (%) or USD | quarterly 1999-Q1 → 2026-Q2 (CNY from 2016-Q4), annual 1995 → 2025 |
| D46 | SWIFT RMB Tracker | **Blocked**: swift.com answers 403 and the monthly PDFs sit behind a free login. `raw/swift_rmb_tracker/README.md` describes the hand-collection CSV the clean script picks up | `raw/swift_rmb_tracker/README.md` | `swift_rmb_tracker.csv` only once the manual CSV exists | – |
| D47 | CIPS annual report / PBoC payment system report | CIPS "Statistics" page publishes two PDF tables (English and Chinese): current-year monthly (transactions, value, working days, daily averages) and annual history; both languages are parsed and cross-checked, and the page's overview sentence is used as a check | `raw/cips/` | `cips_volumes.csv` (bn CNY) | monthly 2026-01 → 2026-09, annual 2015 → 2025 |
| D48 | BIS Triennial Survey | BIS bulk file `WS_DER_OTC_TOV_csv_flat.zip` (14 MB zip / 734 MB CSV), filtered to FX risk, all reporting countries, net-net basis, daily averages in April | `raw/bis_triennial/` | `bis_fx_turnover.csv` (instrument × counterparty × currency pair) and `bis_fx_turnover_by_currency.csv` (share of 200%, with an `OTH` residual row) | triennial 1989 → 2025 |
| D49 | US Treasury TIC – Major Foreign Holders | `slt_table5.txt` (latest 13 months; the tracker URL is its HTML rendering) + `mfhhis01.txt` (yearly blocks 2000 → 2025). The legacy `mfh.txt` stopped updating in January 2023 and is kept raw only | `raw/tic/` | `tic_major_foreign_holders.csv` – country × month, USD bn, plus All Other, Grand Total and foreign-official memo rows | monthly 2000-03 → 2026-08 |
| D50 | World Gold Council (IMF IFS) | gold.org Excel needs a free Goldhub login (403): **IMF IRFCL** (SDMX API) monthly gold in troy ounces and USD for ~95 SDDS reporters, plus **World Bank WDI** annual total reserves with / without gold (implied gold value at market) as the all-country backup | `raw/imf_irfcl/`, `raw/worldbank/`, `raw/wgc_gold/README.md` | `imf_irfcl_gold_reserves.csv` (oz, tonnes, USD, official reserve assets) and `wb_gold_reserves_annual.csv` | monthly 1999-12 → 2026-09; annual 1960 → 2025 |

## Conventions

* One long CSV per source; `period` is the source period (`YYYY`, `YYYY-MM`, `YYYY-Qn`) and `date` is the first day of
  that period. Stock series (COFER, TIC, IRFCL, WDI) are end-of-period values.
* Values are kept exactly as published (no rescaling); units are stated in a `unit` column or in the column name.
* `clean/CHECKS.md` lists every check. The script refuses to write data when a check fails. Checks cover cell
  reconciliation (every numeric cell in the source lands in the output), duplicates, date contiguity, accounting
  identities (SAFE RMB + foreign currency = total and receipts − payments = balance; COFER shares sum to 100 and
  allocated + unallocated = total; TIC countries + All Other = Grand Total; CIPS English = Chinese tables and
  daily averages × working days = totals; BIS currency legs ≤ 200%), plausibility (US gold ≈ 8,133 t, USD reserve
  share 50–65%, USD FX share 85–92%) and cross-source comparisons (IRFCL vs WDI gold value).
* Known data quirks handled in code: TIC series-break "comparison" columns are dropped and the mis-aligned January
  column of the 2002–2011 blocks is re-aligned; IRFCL rows whose reported ounces imply > 9,000 t for a single country
  (Brazil from 2026-03, Angola) are flagged `implausible_volume_in_source` with the derived volume blanked; several
  countries value gold at book / statutory prices in IRFCL (USA at 42.22 USD/oz) – use ounces, not USD, for them;
  BIS publishes no "other currencies" row, so the residual to 200% is added as `OTH`.
* `clean/tracker_status.csv` holds the Status / Date retrieved / Saved file values to paste into the tracker (the
  workbook itself is not modified).
