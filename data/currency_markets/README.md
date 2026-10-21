# Currency markets data (tracker rows D43–D50)

Placeholder for the *Currency markets* category of `data/Oil_Dedollarisation_Data_Tracker.xlsx` (sheet "Data Sources").
Nothing has been downloaded or cleaned yet. When a pipeline is added, follow the layout in
`.claude/rules/data-layout.md`: `download_currency_markets.py -> raw/<source>/`, `clean_currency_markets.py ->
clean/*.csv + CHECKS.md`, and register the clean files in `bristolpy/paths.py`.

```
data/currency_markets/
  raw/     untouched source files, one folder per source (not yet created)
  clean/   tidy CSVs + CHECKS.md (not yet created)
```

## Rows in the tracker

| ID | Variable | Specific series / ticker | Primary source | Frequency | Access | Format / API |
|---|---|---|---|---|---|---|
| D43 | Trade invoicing by currency | Share of exports/imports invoiced in USD, EUR, own currency, other | IMF invoicing dataset (Boz, Casas, Georgiadis, Gopinath et al.) | Annual (ends ~2019) | Free | Excel (attachment on the WP page) |
| D44 | Renminbi trade settlement | RMB cross-border receipts & payments; RMB settlement of goods trade | People's Bank of China RMB Internationalisation Report | Monthly / Annual | Free | PDF → manual extraction to `raw/pboc_rmb/manual/` |
| D45 | Reserve currency shares | COFER – allocated reserves by currency | IMF COFER | Quarterly | Free | CSV / API (data.imf.org 403s curl; browser export) |
| D46 | Payment currency shares | SWIFT RMB Tracker – share of international payments by currency | SWIFT | Monthly | Free (registration) | PDF → hand-collected CSV in `raw/swift_rmb_tracker/manual/` |
| D47 | CIPS volumes | CIPS value & volume of transactions, participants | CIPS Co. annual report / PBoC Payment System Report | Annual / Quarterly | Free | PDF → manual extraction |
| D48 | FX turnover by currency | BIS Triennial Survey – OTC FX turnover by currency | BIS (data.bis.org) | Triennial | Free | CSV / API |
| D49 | Foreign holdings of Treasuries | Major Foreign Holders of Treasury Securities (MFH) | US Treasury TIC | Monthly | Free | Text / Excel (HTML table + Excel) |
| D50 | Central bank gold holdings | Official gold reserves by country | World Gold Council (IMF IFS) | Monthly / Quarterly | Free (registration) | Excel (Goldhub login; IMF IFS as backup) |

Notes from the tracker: D43 is the gold standard for invoicing shares; use the RMB share of China goods-trade
settlement as the RMB invoicing proxy (D44); COFER has a series break at 2016Q4 when CNY was added (D45); D48 is
structural context only (every 3 years); focus D49 on China, Japan, Saudi Arabia and the GCC.
