# bristolpy

Built-in data library for this project. It reads the cleaned data sets produced by the pipelines in
`data/jodi/` (JODI-Oil World Database, monthly from January 2002) and `data/fundamentals/` and hands them back as
pandas DataFrames. JODI is read one balance at a time from the per-balance files and cached, so the first call
for a balance takes a few seconds and later calls are instant.

```
bristolpy/
  fundamental.py   oil fundamentals: demand, production, imports, exports, stocks, refinery intake/output ...
  jodi.py          low-level query over the compiled JODI table
  paths.py         where the data files live
```

Installed in the project venv in editable mode (`pyproject.toml` at the repo root), so it imports from
anywhere with the venv's Python:

```
uv pip install --python .venv/Scripts/python.exe -e .
```

## fundamental

One function per JODI balance. All share the same keyword arguments.

```python
from bristolpy import fundamental as f

f.demand("China", product="Total oil products")                      # kb/d, one row per month
f.production(["Saudi Arabia", "Iraq"], product="Crude oil", wide=True)  # months as columns
f.imports("India", unit="kmt", start="2026-01", end="2026-03")
f.exports("Russian Federation", product="Gas/diesel oil", numeric_only=True)
f.closing_stocks("Japan", product="Crude oil")                       # alias: f.stocks
f.refinery_intake("Germany", product="Crude oil")
f.refinery_output("Korea")
f.stock_change(report="primary")                                     # all countries, all primary products
f.net_imports("United States of America", product="Crude oil")       # imports - exports
f.get("Statistical difference", country="Brazil")                    # any balance by name
```

| argument | meaning |
|---|---|
| `country` | name or list of names, case-insensitive; a typo raises with suggestions. `None` = all 118 |
| `product` | name or list. Primary: Crude oil, NGL, Other, Total. Secondary: Fuel oil, Gas/diesel oil, Kerosenes, Liquefied petroleum gases, Motor and aviation gasoline, Naphtha, Other oil products, Total oil products, of which: kerosene type jet fuel |
| `unit` | `"kb/d"` (default), `"kbbl"`, `"kl"`, `"kmt"`, `"conv"` (barrels per kilotonne), or `None` for all five |
| `report` | `"primary"`, `"secondary"` or `None` for both (Imports, Exports, Closing stocks, Stock change, Statistical difference exist in both) |
| `start`, `end` | inclusive month bounds, `"YYYY-MM"`; the data runs from 2002-01 |
| `numeric_only` | drop cells jodidb reports as a status token |
| `wide` | months as columns instead of rows (flags dropped) |

Long result columns: `report, balance, country, unit, period, date, product, value, flag, assessment`. When `value`
is empty, `flag` holds JODI's token: `-` not available, `N/A` not applicable, `..` not reported, `x` confidential.
`assessment` is JODI's data-quality code for the cell: 1 reasonable comparability, 2 consult metadata / use with
caution, 3 not assessed.

Discovery helpers: `f.balances()`, `f.countries()`, `f.products(report=...)`, `f.periods()`, `f.describe()`.

### Other fundamentals sources

The per-source CSVs from `data/fundamentals/clean_fundamentals.py`, with simple equality filters:

```python
f.steo(table="3a", series_code="copr_opec")     # EIA STEO monthly
f.wpsr("WCESTUS1")                              # EIA WPSR weekly US stocks
f.eurostat(geo="DE", nrg_bal="IMP")             # Eurostat nrg_cb_oilm
f.energy_institute(sheet="Oil Production - barrels")
f.comtrade(reporter="China", flow="Imports", cmd_code=2709)
f.jodi_tracker("D02")                           # JODI as cleaned for tracker rows D02/D09
f.catalog(); f.tracker_status(); f.sources()
```

## jodi

```python
from bristolpy import jodi
jodi.query(balance="Production", country="Saudi Arabia", product="Crude oil", unit="kb/d")
jodi.wide("Imports")                                  # the per-balance table, products as columns
jodi.balances(); jodi.products("secondary"); jodi.countries(); jodi.units(); jodi.manifest()
jodi.checks_passed()      # True when every balance's CHECKS.md says ALL PASSED
jodi.reload()             # after re-running the pipeline (tables are cached in memory)
```

## currency

The *Currency markets* rows of the tracker (D43–D50), from `data/currency_markets/clean_currency_markets.py`.

```python
from bristolpy import currency as c

c.invoicing("JPN", wide=True)                              # D43 invoicing shares, % of exports/imports, 1990-2019
c.rmb_share()                                              # D44 RMB share of China's cross-border receipts/payments (SAFE)
c.safe_crossborder(flow="Receipts", group="by_currency")   # D44 SAFE receipts by currency, USD 100 million, monthly
c.cofer(currency=["USD", "EUR", "CNY"], wide=True)         # D45 COFER shares of allocated reserves, quarterly
c.cips(freq="A")                                           # D47 CIPS value (bn CNY) and transactions
c.fx_turnover_by_currency(currency=["USD", "CNY"])         # D48 BIS Triennial share of 200%
c.fx_turnover(instrument_code="B", currency_2="TO1")       # D48 spot turnover by currency, USD mn/day
c.treasury_holders(["Japan", "China, Mainland"], wide=True)  # D49 TIC holdings, USD bn, monthly
c.gold_reserves(["RUS", "CHN", "IND"], wide=True)          # D50 IMF IRFCL gold, tonnes, monthly
c.gold_reserves_annual("SAU")                              # D50 WDI implied gold value, USD, annual
c.sources(); c.catalog(); c.tracker_status()
```

D46 (SWIFT RMB Tracker) needs a manual download; `c.swift()` works once the hand-collected CSV described in
`data/currency_markets/raw/swift_rmb_tracker/README.md` exists.

## Data provenance

| data | produced by |
|---|---|
| `data/jodi/raw/world_{Primary,Secondary}_CSV.zip` | `data/jodi/download_jodi.py` (jodidata.org bulk files, validated) |
| `data/jodi/balances/<balance>/<balance>.csv` | `clean_jodi.py` (wide, one row per report × country × unit × month; what bristolpy reads) |
| `data/jodi/clean/final_clean/jodi_oil.csv` | `compile_jodi.py` (long, ~22.7 M rows; one compiled file for other tools) |
| `data/fundamentals/clean/*.csv` | `data/fundamentals/download_fundamentals.py` → `clean_fundamentals.py` |
| `data/currency_markets/clean/*.csv` | `data/currency_markets/download_currency_markets.py` → `clean_currency_markets.py` |

Each pipeline writes a `CHECKS.md` next to its output and refuses to write data when a check fails.
