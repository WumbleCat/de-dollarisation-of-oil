# Geopolitics data (tracker rows D37–D42)

Placeholder for the *Geopolitics* category of `data/Oil_Dedollarisation_Data_Tracker.xlsx` (sheet "Data Sources").
Nothing has been downloaded or cleaned yet. When a pipeline is added, follow the layout in
`.claude/rules/data-layout.md`: `download_geopolitics.py -> raw/<source>/`, `clean_geopolitics.py ->
clean/*.csv + CHECKS.md`, and register the clean files in `bristolpy/paths.py`.

```
data/geopolitics/
  raw/     untouched source files, one folder per source (not yet created)
  clean/   tidy CSVs + CHECKS.md (not yet created)
```

## Rows in the tracker

| ID | Variable | Specific series / ticker | Primary source | Frequency | Access | Format / API |
|---|---|---|---|---|---|---|
| D37 | Geopolitical risk | GPR index; GPR Threats / Acts; country GPR (Iran, Russia, Saudi) | Caldara & Iacoviello | Daily / Monthly | Free | Excel (`data_gpr_export.xls`, direct) |
| D38 | Sanctions | Sanctions episodes by country pair, type & objective | Global Sanctions Database (GSDB) | Annual (episodes) | Free (email request) | Excel → place in `raw/gsdb/manual/` |
| D39 | Sanctions – event detail | OFAC recent actions; EU sanctions packages | US Treasury OFAC | Event | Free | Web (HTML; SDN list files for structured data) |
| D40 | Structural oil shocks | Supply / aggregate demand / oil-specific demand shocks | Baumeister & Hamilton (2019) | Monthly | Free | Excel (direct link) |
| D41 | OPEC supply news shocks | High-frequency oil supply news shock series | Känzig (2021, AER), GitHub `dkaenzig/oilsupplynews` | Daily (OPEC dates) / Monthly | Free | Excel / GitHub |
| D42 | Shipping / chokepoints | Strait of Hormuz & Red Sea transit counts | IMF PortWatch | Daily | Free | CSV / ArcGIS REST API (no key) |

Notes from the tracker: separate GPR-Acts from GPR-Threats (realised vs anticipated risk); build sanction dummies
for Iran (2012, 2018) and Russia (2014, 2022, price cap); D39 feeds the "Event Dates" sheet; D41 includes the
OPEC announcement dates for the event study.
