# World Gold Council - gold reserves by country (tracker D50) - manual step

https://www.gold.org/goldhub/data/gold-reserves-by-country lists the Excel files (World_official_gold_holdings_as_of_Oct2026_IFS.xlsx , Changes_latest_as_of_Oct2026_IFS.xlsx, World_official_gold_holdings_as_of_Oct2026_IFS.xlsx , CBGA_sales.xlsx, Changes_latest_as_of_Oct2026_IFS.xlsx, Quarterly_gold_and_FX_Reserves_Q2_2026.xlsx)
but the downloads need a free Goldhub registration (HTTP 403 to scripts). To use the WGC file:
1. Log in to Goldhub in a browser, download "World_official_gold_holdings_as_of_<Mon><Year>_IFS.xlsx" and
   "Quarterly_gold_and_FX_Reserves_<Q>_<Year>.xlsx" and drop them in this folder.
2. Re-run `clean_currency_markets.py` (it reports them in CHECKS.md but the cleaned gold series come from the
   IMF IRFCL backup, `raw/imf_irfcl/`, and the World Bank WDI annual backup, `raw/worldbank/`).
WGC's figures are themselves compiled from IMF IFS, so the IRFCL monthly series are the same underlying data for
the ~90 SDDS-reporting countries (China, Russia, India, Saudi Arabia, Türkiye, Poland ... included).
