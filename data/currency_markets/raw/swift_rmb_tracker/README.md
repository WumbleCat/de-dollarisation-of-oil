# SWIFT RMB Tracker (tracker D46) - manual step

swift.com answers scripted requests with HTTP 403 ("SWIFT site off-line" interstitial) and the monthly
RMB Tracker PDFs sit behind a free swift.com registration form, so nothing is downloaded automatically.

To fill this source by hand:
1. Open https://www.swift.com/our-solutions/compliance-and-shared-services/business-intelligence/renminbi/rmb-tracker in a browser, register (free) and download the monthly "RMB Tracker" PDFs.
2. Record, per month, the headline figures SWIFT publishes: RMB share of global payments by value (%),
   RMB rank, RMB share excluding intra-eurozone payments and the top-5/top-10 currency shares, into
   `raw/swift_rmb_tracker/swift_rmb_tracker.csv` with columns
   `month,currency,share_pct,rank,basis,source_pdf` (basis = "all" or "ex_eurozone").
3. Re-run `clean_currency_markets.py`; it picks the CSV up and writes `clean/swift_rmb_tracker.csv`.
