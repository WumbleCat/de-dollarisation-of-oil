# Macro controls data (tracker rows D30–D36)

Placeholder for the *Macro controls* category of `data/Oil_Dedollarisation_Data_Tracker.xlsx` (sheet "Data Sources").
Nothing has been downloaded or cleaned yet. When a pipeline is added, follow the layout in
`.claude/rules/data-layout.md`: `download_macro_controls.py -> raw/<source>/`, `clean_macro_controls.py ->
clean/*.csv + CHECKS.md`, and register the clean files in `bristolpy/paths.py`.

```
data/macro_controls/
  raw/     untouched source files, one folder per source (not yet created)
  clean/   tidy CSVs + CHECKS.md (not yet created)
```

## Rows in the tracker

| ID | Variable | Specific series / ticker | Primary source | Frequency | Access | Format / API |
|---|---|---|---|---|---|---|
| D30 | Fed policy rate | Effective Fed funds rate (DFF / FEDFUNDS) | FRED | Daily / Monthly | Free | CSV / API (needs `FRED_API_KEY` for scripts) |
| D31 | Monetary policy shocks | High-frequency Fed policy surprises | Bauer & Swanson (2023); Jarociński–Karadi | FOMC dates / monthly | Free | Excel (direct link) |
| D32 | US CPI | CPI-U all items (CPIAUCSL); core (CPILFESL) | FRED (BLS) | Monthly | Free | CSV / API |
| D33 | Global inflation | Headline / core / energy CPI, 200 countries | World Bank Global Database of Inflation | Monthly / Quarterly / Annual | Free | Excel (link changes each release) |
| D34 | World industrial production | World IP index | Baumeister & Hamilton / OECD+6 IP | Monthly | Free | Excel (direct link) |
| D35 | Global real activity | Kilian index (IGREA) | FRED / Lutz Kilian's site | Monthly | Free | CSV / API |
| D36 | Economic policy uncertainty | Global EPU; US EPU; China EPU | policyuncertainty.com | Monthly / Daily (US) | Free | Excel (`All_Country_Data.xlsx`) |

Notes from the tracker: use the Wu–Xia shadow rate for 2009–15 and 2020–22 if the sample includes the ZLB (D30);
CPI is used to deflate oil prices (D32); world IP / IGREA are the standard demand proxies in oil SVARs (D34, D35).
