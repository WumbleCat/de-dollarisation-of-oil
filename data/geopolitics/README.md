# Geopolitics data (tracker rows D37–D42)

Everything for the *Geopolitics* category of `data/Oil_Dedollarisation_Data_Tracker.xlsx` (sheet "Data Sources")
lives here, following `.claude/rules/data-layout.md`.

```
data/geopolitics/
  download_geopolitics.py   pull every raw file -> raw/<source>/ (+ raw/manifest.json)
  clean_geopolitics.py      raw/ -> clean/*.csv, with sanity checks that must all pass
  raw/                      untouched source files, one folder per source; vintages/ for revised files (git-ignored)
  clean/                    tidy CSVs (git-ignored) + CHECKS.md + series_catalog.csv + tracker_status.csv
```

Run (project venv; stdlib for the download, pandas/openpyxl/xlrd for the clean):

```
.venv/Scripts/python.exe data/geopolitics/download_geopolitics.py            # ~2 min + ~25 min for the OFAC crawl
.venv/Scripts/python.exe data/geopolitics/download_geopolitics.py --only ofac # re-crawl the index, fetch only new actions
.venv/Scripts/python.exe data/geopolitics/clean_geopolitics.py
```

Read the results through `bristolpy.geopolitics` (`g.gpr()`, `g.ofac()`, `g.sdn()`, `g.baumeister_hamilton()`,
`g.kanzig()`, `g.opec_announcement_dates()`, `g.chokepoints()`, `g.disruptions()`).

## Sources

| ID | Source | Raw | Clean | Notes |
|---|---|---|---|---|
| D37 | Caldara & Iacoviello GPR index (matteoiacoviello.com) | `raw/gpr/data_gpr_export.xls` (monthly, 1900-01 →), `raw/gpr/data_gpr_daily_recent.xls` (daily, 1985-01-01 →) + `vintages/` | `gpr.csv` | long: `freq` M/D, `series_id` = the author's variable names (GPR, GPRT threats, GPRA acts, GPRH historical, GPRC_<ISO3> country indexes incl. RUS, SAU, USA, UKR; daily GPRD, GPRD_ACT, GPRD_THREAT, moving averages), `series_name` = the author's label, `event` = the daily file's event label. The whole history is revised with each monthly update, so the files are re-downloaded every run and a dated copy kept. No Iran country index exists in the source (the tracker's "country GPR (Iran ...)": use GPRC_SAU / ISR / RUS or the oil-related share series) |
| D38 | Global Sanctions Database (GSDB) | `raw/gsdb/manual/` (empty) + `raw/gsdb/README.md` | – | **Not obtainable by script**: released by e-mail request for academic use; the website did not answer at all (connection timed out from two networks) on 2026-10-21. Manual steps in `raw/gsdb/README.md`; a hand-placed workbook is recorded in the manifest as `manual` and `tracker_status.csv` switches to "Downloaded". Until then the Iran / Russia sanction dummies must be built from the OFAC actions (D39) and the Event Dates sheet |
| D39 | US Treasury OFAC – Recent Actions (HTML) + SDN list files | `raw/ofac/listing/page_NNN.html` (318 index pages, re-crawled every run), `raw/ofac/index.json`, `raw/ofac/actions/<slug>.html` (one page per action, 2001 →, fetched once), `raw/ofac/sdn/{sdn,add,alt,sdn_comments}.csv` + `vintages/` | `ofac_recent_actions.csv`, `ofac_sdn.csv` | one row per action: `date`, `title`, `category` (Sanctions List Updates / General Licenses / Enforcement Actions / Regulations and Guidance / Miscellaneous), press-release link, `programs` = the sanctions-programme tags found in square brackets on the page (e.g. `IRAN-EO13902`, `RUSSIA-EO14024`), `n_sdn_added/removed/updated` = entries counted under the page's "The following … have been added/removed/updated" headings, `is_iran/is_russia/is_venezuela/is_oil_shipping` keyword flags (title + tags + first lines), `body_text` = the narrative paragraphs (SDN entry lists are left in the raw HTML). `ofac_sdn.csv` is the current SDN snapshot (entry number, name, type, programme, remarks). 4 parallel connections, 0.25 s pause per page |
| D40 | Baumeister & Hamilton (2019, AER) structural shocks | `raw/baumeister_hamilton/BH2_supply_shocks.xlsx`, `BH2_demand_shocks.xlsx`, `OECD_plus6_industrial_production.xlsx`, `market-based_oil_price_shocks.xlsx` + `vintages/` | `baumeister_hamilton.csv` | Google-Drive links taken from the author's research page (the page itself redirects scripts to a Google login; the file links do not). Four posterior-median shocks, monthly 1975-02 → 2026-06: `oil_supply_shocks`, `economic_activity_shocks`, `oil_consumption_demand_shocks`, `oil_inventory_demand_shocks`, plus the VAR input `oecd_6nme_industrial_production` (1958 →). Shocks are re-estimated at each update (correlation with the 2023 vintage 0.93–0.99), hence `vintage`. The market-based (Baumeister 2023) file is kept raw only |
| D41 | Känzig (2021, AER) oil supply news shocks (GitHub `dkaenzig/oilsupplynews`) | `raw/kanzig/oilSupplyNewsShocks_<YYYYMmm>.xlsx` (every vintage, 2017M12 … 2025M12), `VARdata.xlsx`, `README.md` | `kanzig.csv` | latest vintage only, `sample` full / pre_covid. Daily (`freq` D): futures-price surprises on the 169 OPEC announcement dates 1983-07-19 → 2025-12-01 by contract (`surprise_front`, `surprise_1m` … `surprise_12m`) and first principal component `surprise_pc`; monthly (`freq` M, 1975-01 →): `monthly_surprise` (= sum of the month's daily PC surprises, checked) and the VAR-identified `news_shock`. The daily dates are the OPEC event list the tracker asks for (`bristolpy.geopolitics.opec_announcement_dates()`) |
| D42 | IMF PortWatch (ArcGIS REST, no key) | `raw/portwatch/daily_chokepoints.json` (+ `vintages/`), `chokepoints_database.json`, `disruptions_database.json` | `portwatch_chokepoints.csv`, `portwatch_disruptions.csv` | daily 2019-01-01 → (3-day lag), all 28 chokepoints incl. Strait of Hormuz, Bab el-Mandeb, Suez, Cape of Good Hope: vessel counts by type (`n_tanker`, `n_container` … `n_total`) and capacity in DWT (`capacity_*`); identities n_total = n_cargo + n_tanker etc. checked. Kept in the source's one-row-per-chokepoint-day shape (several measures per row, like the Comtrade file). Disruptions: 132 events (type, dates, affected ports). The service's `Daily_Ports_Data` (5.9 M rows, port level) is not pulled |

## Checks

`clean_geopolitics.py` refuses to write any data file when a check fails; `clean/CHECKS.md` lists every check.
They cover: raw-cell reconciliation (every numeric cell in each workbook / JSON lands in the output), key
uniqueness, date contiguity (monthly, calendar-daily), coverage against the tracker's "Coverage from" and the
expected publication lag, index normalisation (GPR = 100 on average over 1985–2019, GPRH over 1900–2019), accounting
identities inside PortWatch (counts and capacities by vessel type), the Känzig monthly-surprise = sum-of-daily
identity, centred structural shocks, OFAC page/listing agreement (dates, titles) and crawl completeness, plus INFO
lines such as the Strait of Hormuz tanker transits (2025 average vs March 2026) and the cross-vintage correlation of
the BH shocks.

`clean/tracker_status.csv` holds the Status / Date retrieved / Saved file values to paste into the tracker (the
workbook is not modified by the scripts).
