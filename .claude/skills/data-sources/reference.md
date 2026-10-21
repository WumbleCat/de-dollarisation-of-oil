# Source access reference (digest of the tracker's "Findings / limitations", checked 2026-10-15, plus what the
# existing pipelines learned)

Grouped by access pattern. `key` = environment variable read from `./.env` at the repo root (never hard-code).

## Direct file, no login (plain HTTP GET works with a browser User-Agent)

| rows | source | what to fetch | notes |
|---|---|---|---|
| D01 D05 D07 | EIA STEO | `https://www.eia.gov/outlooks/steo/xls/STEO_m.xlsx` | forecasts are revised monthly: keep a dated copy in `raw/eia_steo/vintages/`. API v2 needs `EIA_API_KEY` but the xlsx does not |
| D04 D06 D08 | EIA WPSR | `https://www.eia.gov/dnav/pet/hist_xls/<SERIES>w.xls` (full history per series) + `https://ir.eia.gov/wpsr/psw01.xls` | release Wednesdays 10:30 ET |
| D15 D16 | EIA spot prices | `https://www.eia.gov/dnav/pet/xls/PET_PRI_SPT_S1_D.xls` (~3.4 MB, all spot series) | $/gal x 42 = $/bbl for products; 3-2-1 = (2xRBOB + 1xHO)x42/3 - WTI |
| D10 | Eurostat `nrg_cb_oilm` | SDMX bulk TSV (~28 MB) + code lists; see `data/fundamentals/download_fundamentals.py` | filter geo = FR, DE, EU27_2020 after download |
| D11 | Energy Institute Statistical Review | workbook link discovered from the resources page | 403 to plain curl, fine with a browser UA; annual |
| D29 | World Bank Pink Sheet | `CMO-Historical-Data-Monthly.xlsx` from the commodity-markets page | monthly; also monthly gold as backup for D26 |
| D33 | World Bank Global Inflation DB | Excel linked from the page; the file name changes each release: scrape the link, do not hard-code | annual / quarterly / monthly tabs |
| D34 D40 | Baumeister (Google Sites) | direct Excel links on the research page: world IP, structural shocks | may lag several months; check end date |
| D31 | Bauer & Swanson shocks | direct Excel on michaeldbauer.com | updated irregularly |
| D36 | policyuncertainty.com | `All_Country_Data.xlsx` + US daily file | monthly (US daily) |
| D37 | GPR (Caldara & Iacoviello) | `data_gpr_export.xls` (~2.7 MB) + daily variant | monthly + daily |
| D41 | Kanzig oil supply news | public GitHub repo `dkaenzig/oilsupplynews` (zip download) | ends at the paper's sample unless updated; includes OPEC announcement dates |
| D42 | IMF PortWatch | ArcGIS REST API (no key) or dashboard CSV export | daily from 2019 |
| D43 | IMF invoicing dataset (Boz et al.) | Excel attachment on the IMF WP page | annual, ends ~2019 |
| D48 | BIS Triennial Survey | CSV from data.bis.org tables | triennial |
| D49 | US Treasury TIC MFH | HTML table `slt_table5.html` + Excel versions on the TIC site | monthly, ~6-week lag; large annual benchmark revisions |

## API key (free) - put the key in `.env`

| rows | source | key | endpoint |
|---|---|---|---|
| D13 D14 D19-D25 D30 D32 D35 | FRED | `FRED_API_KEY` | `https://api.stlouisfed.org/fred/series/observations?series_id=<ID>&api_key=<KEY>&file_type=json` (also `/fred/series` for metadata). FRED's Akamai layer blocks `fredgraph.csv` from scripts; the API works. Series: DCOILBRENTEU, DCOILWTICO, DTWEXBGS, DEXUSEU, DEXUSUK, DEXCHUS, DEXJPUS, DGS2, DGS10, DFII10, VIXCLS, OVXCLS, DFF, FEDFUNDS, CPIAUCSL, CPILFESL, IGREA, FDHBFIN (backup for D49) |
| D01 D05 D07 (optional) | EIA API v2 | `EIA_API_KEY` | only if the STEO xlsx is not enough |
| D12 | UN Comtrade | `COMTRADE_API_KEY` | without a key the public *preview* endpoint is used: 500 records per call, ~120 calls per hour (403 "Quota Exceeded"), 429 with `Retry-After` 1 s. With a key: 100k records per call. See `data/fundamentals/download_fundamentals.py` |

## Registration wall (free account) - script cannot log in; document the manual step

| rows | source | manual step | automation available |
|---|---|---|---|
| D02 D09 | JODI | none needed any more: `data/jodi/download_jodi.py` uses the jodidata.org bulk zips | yes (done) |
| D18 | FIA ETD tracker | headline press releases are free; contract-level files need a FIA login | partial |
| D26 | LBMA gold | recent prices/charts free, full daily history paid | use World Bank monthly (D29 file) or FRED backup |
| D38 | Global Sanctions Database | data sent by email on request (academic use), days of turnaround | no: drop the file into `raw/gsdb/` |
| D46 | SWIFT RMB Tracker | monthly PDF behind a swift.com form; 403 to scripts | no: hand-collect headline shares into a CSV in `raw/swift_rmb_tracker/` |
| D50 | World Gold Council | Excel behind free Goldhub registration | backup: IMF IFS reserves (no login) |

## Bot protection / HTML only - cannot be scripted reliably

| rows | source | what works |
|---|---|---|
| D03 | OPEC MOMR | Cloudflare JS challenge; download PDFs in a browser into `raw/opec_momr/`; STEO table 3d OPEC members is the tracker-suggested stand-in |
| D27 | INE Shanghai crude (SC) | English site publishes daily settlements as HTML: scrape the daily page politely or use a terminal export; no bulk file |
| D28 | Urals (minfin.gov.ru) | monthly averages published as news items / PDF; hand-collect, daily is paid (Argus) |
| D39 | OFAC recent actions | HTML only; use the structured SDN list files for machine-readable data |
| D44 D47 | PBoC RMB report, CIPS annual report | PDF tables; manual extraction into CSV under `raw/<source>/manual/` |
| D45 | IMF COFER | data.imf.org returns 403 to curl; browser CSV export, or try the IMF SDMX endpoint with a browser UA. Series break at 2016Q4 when CNY was added |

## Paid / terminal only

| rows | source | note |
|---|---|---|
| D17 | ICE Low Sulphur Gasoil | Bloomberg QS1 / LSEG LGO export from the University of Bristol library terminal; $/tonne / 7.45 = $/bbl. Status in tracker: Blocked / unavailable |

## Known gotchas when parsing

- JODI bulk tokens `-`, `N/A`, `..`, `x` are status flags: read with `keep_default_na=False` and keep them in a `flag` column.
- WTI (D14) is negative on 2020-04-20: keep it, handle before logs in the model, never clip.
- FRED daily series use `.` for missing in CSV and `"."` in the JSON API: map to NaN, keep the date row.
- STEO / forecasts: never overwrite the previous vintage; tag rows with `vintage` and `is_historical`.
- Weekly EIA: date = week-ending Friday; monthly = first of month; annual = `year` integer column.
