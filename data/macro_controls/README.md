# Macro controls data (tracker rows D30–D36)

Everything for the *Macro controls* category of `data/Oil_Dedollarisation_Data_Tracker.xlsx` (sheet "Data Sources")
lives here, following `.claude/rules/data-layout.md`.

```
data/macro_controls/
  download_macro_controls.py   pull every raw file -> raw/<source>/ (+ raw/manifest.json)
  clean_macro_controls.py      raw/ -> clean/*.csv, with sanity checks that must all pass
  raw/                         untouched source files, one folder per source (vintages/ for revised files)
  clean/                       tidy CSVs + CHECKS.md + series_catalog.csv + tracker_status.csv
```

Run (project venv; stdlib for the downloader, pandas/openpyxl for the cleaner):

```
.venv/Scripts/python.exe data/macro_controls/download_macro_controls.py            # --only <source> / --refresh
.venv/Scripts/python.exe data/macro_controls/clean_macro_controls.py               # --only <source>
```

Read the result through `bristolpy.macro` (`fed_funds()`, `shadow_rate()`, `policy_shocks()`, `jk_shocks()`, `us_cpi()`,
`global_inflation()`, `world_ip()`, `gecon()`, `igrea()`, `epu()`, `wui()`, `describe()`).

## FRED is blocked, the primary publishers are not

The tracker points D30, D32 and D35 at FRED. FRED's Akamai layer resets every scripted connection from this
machine (Python, curl and PowerShell all fail, as the tracker's access check warned), and no `FRED_API_KEY` is set.
The three rows are therefore taken from the institutions that produce the FRED series, which serve the identical
numbers without a key:

| FRED series | here | source |
|---|---|---|
| DFF (daily) / FEDFUNDS (monthly) | `fed_h15.csv`, `RIFSPFF_N.D` / `RIFSPFF_N.M` | Federal Reserve Board H.15 data-download package |
| CPIAUCSL / CPILFESL | `bls_cpi.csv`, `CUSR0000SA0` / `CUSR0000SA0L1E` | BLS public API v1 (no key, 10-year windows) |
| IGREA | `dallasfed_igrea.csv` | Dallas Fed `igrea.xlsx` (the Dallas Fed maintains the index FRED republishes) |

If `FRED_API_KEY=<key>` is added to `./.env`, `--only fred` also pulls the five FRED series into `raw/fred/` and the
cleaner cross-checks them against the files above (`fred` section of CHECKS.md).

## Sources

| IDs | Source | Raw | Clean | Notes |
|---|---|---|---|---|
| D30 | Fed H.15 (effective federal funds rate) | `raw/fed_h15/H15_data.zip` (SDMX-ML, whole release) | `fed_h15.csv` | daily (every calendar day, = DFF), business-daily, weekly (Wednesday-ending) and monthly (= FEDFUNDS, average of the daily series: checked), 1954-07 onwards. `ND` status cells become blank with `flag = ND` |
| D30 | NY Fed EFFR | `raw/nyfed_effr/effr.csv` | `nyfed_effr.csv` | rate, 1st/25th/75th/99th percentiles, volume ($ bn), target range, business days from 2016-03-01; identical to the H.15 business-daily series on every overlapping day (checked) |
| D30 | Wu–Xia shadow rate (Atlanta Fed) | `raw/wu_xia/WuXiaShadowRate.xlsx` | `wu_xia.csv` | monthly 1960-01 .. **2022-02** (the Atlanta Fed stopped updating). `SHADOW_RATE` is blank outside ZLB months; the file's `EFFR` column is the end-of-month effective rate (checked against H.15) |
| D31 | Bauer & Swanson (2023) | `raw/bauer_swanson/FOMC_Bauer_Swanson.xlsx` (+ `vintages/`) | `bauer_swanson.csv` | table `fomc_announcements`: 323 announcements 1988-02 .. 2019-12 with `MPS`, `MPS_ORTH`, futures/Treasury/S&P responses and the six orthogonalisation variables; table `monthly_svar`: 1973-01 .. 2020-02 with the monthly `MPS` (= sum of announcement MPS, checked) and the SVAR variables. 2001-09-17 has no MPS by construction (documented). The xlsx is not extended beyond 2019: use Jarociński–Karadi for recent years |
| D31 | Jarociński–Karadi | `raw/jarocinski_karadi/shocks_fed_jk_{m,t}.csv` (+ `vintages/`) | `jarocinski_karadi.csv` | `MP_pm`, `CBI_pm`, `MP_median`, `CBI_median`, `pc1`, `SP500`, monthly 1990-02 onwards (updated after each FOMC meeting, latest 2026-09) and per announcement; monthly = sum of announcements (checked, except SP500 in 3 months, listed in CHECKS.md) |
| D32 | BLS CPI-U | `raw/bls_cpi/cpi_<y0>_<y1>.json` | `bls_cpi.csv` | `CUSR0000SA0` (all items SA, 1947-01 ->), `CUSR0000SA0L1E` (core SA, 1957-01 ->), `CUSR0000SA0E` (energy SA), `CUUR0000SA0`, `CUUR0000SA0L1E` (NSA); index 1982-84 = 100; column `fred_alias` gives the FRED name. BLS v1 API: 25 calls/day, 10 years/call – the run uses 8 |
| D33 | World Bank Global Database of Inflation | `raw/world_bank_inflation/Inflation-data.xlsx` (+ `vintages/`; link scraped from the brief page each run) | `world_bank_inflation.csv` (monthly + quarterly index sheets), `world_bank_inflation_annual.csv` (annual rates + `Aggregate` sheet) | sheets `hcpi/fcpi/ecpi/ccpi/ppi/def` × `m/q/a`; blank grid cells are dropped (every numeric cell is reconciled), `raw_row` keeps apart countries that appear on several rows. Current release ends 2025-03 (monthly). **The USA monthly headline series does not track CPI-U** (see CHECKS.md, cross-source): use `bls_cpi.csv` for the US |
| D34 | Baumeister & Hamilton world IP; Baumeister–Korobilis–Lee GECON | `raw/baumeister/OECD_plus6_industrial_production.xlsx`, `WIP_vintages.xlsx`, `GECON_indicator.xlsx` (Google Drive links scraped from `sites.google.com/site/cjsbaumeister/datasets`; + `vintages/`) | `baumeister_wip.csv`, `baumeister_wip_vintages.csv` | `WIP` monthly 1958-01 .. 2026-07 (index 2021 = 100); 175 real-time vintages 2012-03 .. 2026-09 (latest = current file, checked); `GECON`, `GECON_STD`, `GECON3_SMOOTH`, `GECON3_STD` 1973-02 .. 2026-09 |
| D35 | Dallas Fed IGREA (Kilian index) | `raw/dallasfed_igrea/igrea.xlsx` (+ `vintages/`) | `dallasfed_igrea.csv` | monthly 1968-01 .. 2026-09; the file dates recent months on the 25th/26th – normalised to month start, original in `source_date` |
| D36 | policyuncertainty.com EPU | `raw/epu/*.xlsx`, `All_Daily_Policy_Data.csv` | `epu.csv` | tables `global` (GEPU_current/ppp 1997-01 ->), `all_country` (21 countries + GEPU + SCMP / Mainland China, 1985-01 ->), `us_news`, `us_legacy` (three-component index and parts), `us_daily` (every calendar day from 1985-01-01), `china_scmp` (1995-01 .. 2019-04), `china_mainland` (1949-10 ->). Identities across files checked; the all-country `SCMP China` column is a differently normalised series (INFO) |
| D36 | World Uncertainty Index | `raw/wui/WUI_Data.xlsx` (link scraped from the data page) | `wui.csv` | quarterly tables T1 (global/regional), T2 (WUI by country), T3/T4/T5 (word, total-word and page counts – T2 = T3/T4 × 1000, checked), T6 (3-quarter weighted MA, the authors' preferred country measure), T8 (trade uncertainty), 1952Q1/1990Q1 .. 2026Q3, with a short `table_name` (full T0 text in CHECKS.md) and country names/regions from T7. T9 (annual GDP weights) is not exported |

## Clean file conventions

Tidy long format, one row per observation: `tracker_ids, source, <dimensions>, unit, date, value, flag` (+ `vintage`
for revised sources). `date` is ISO (daily as published, weekly = week-ending Wednesday, monthly = first of month,
quarterly = first day of the quarter); the annual World Bank file carries an integer `year` instead. `flag` holds the
source's non-numeric token (`ND`, footnote codes). Nothing is filled, clipped, deflated or rebased.

## Checks

`clean_macro_controls.py` refuses to write any data file when a check fails; `clean/CHECKS.md` lists every check.
They cover raw-cell reconciliation (every numeric cell lands in the output), key uniqueness, date contiguity at the
declared frequency, coverage against the tracker's "Coverage from" and the expected publication lag, plausible ranges,
identities inside each source (H.15 monthly = mean of daily; Bauer–Swanson and Jarociński–Karadi monthly = sum of
announcements; WUI = count / total words; latest world-IP vintage = current file; EPU all-country columns = the
single-country files) and cross-source comparisons (H.15 vs NY Fed EFFR, Wu–Xia EFFR vs H.15, World Bank vs BLS for
the US, world IP vs IGREA).

`clean/tracker_status.csv` holds the Status / Date retrieved / Saved file values to paste into the tracker (the
workbook is not modified by the scripts).
