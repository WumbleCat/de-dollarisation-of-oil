# Currency markets (D43-D50) - clean checks, 2026-10-22

Result: **ALL PASSED**

| source | check | status | detail |
|---|---|---|---|
| D43 invoicing | every non-missing share in the .dta lands in the output | PASS | 14218 vs 14218 |
| D43 invoicing | reported currency shares (USD, EUR, home, unclassified) within 0-100 | PASS | min 0.000 max 100.000 |
| D43 invoicing | residual categories (other, other excl. USD/EUR) within -5 .. 100 | PASS | min -3.780 max 99.000 |
| D43 invoicing | negative residual shares kept as published (100 - USD - EUR computed by the authors) | INFO | HRV 2005 Other_Excl_USDEUR -0.65; HRV 2006 Other_Excl_USDEUR -1.66; HRV 2007 Other_Excl_USDEUR -1.07; HRV 2008 Other_Excl_USDEUR -1.67; HRV 2009 Other_Excl_USDEUR -3.78 |
| D43 invoicing | USD + EUR + other (excl. USD/EUR) = 100 where all three reported (authors' own check) | PASS | 2502 rows; max /dev/ 0.0000 |
| D43 invoicing | USD + EUR + home + other <= 100 (+0.5) where all four reported | PASS | 1833 rows; max 100.025 |
| D43 invoicing | coverage 1990-2019 and >= 100 countries | PASS | 1989-2019, 110 countries |
| D43 invoicing | countries without any invoicing data | INFO | none |
| D43 invoicing | source | INFO | Mendeley Data 6z6w78968m v1 (replication files of Boz et al. 2022, JIE) -> Data/all_countries_update.dta; ends 2019; the imf.org attachment is the same dataset but refuses scripted downloads |
| D44 SAFE | every numeric cell of the 4 sheets lands in the output | PASS | 20832 cells, 20832 rows |
| D44 SAFE | no duplicate (freq, period, flow, item, unit) rows | PASS | 0 duplicates |
| D44 SAFE | monthly periods contiguous | PASS | 2010-01 -> 2026-09; missing [] |
| D44 SAFE | RMB + foreign currency = total (receipts, payments, balance) | PASS | max /dev/ 0.077 (100 million; source values are rounded) |
| D44 SAFE | USD + HKD + EUR + JPY + other = foreign currency | PASS | max /dev/ 0.000 |
| D44 SAFE | receipts - payments = balance | PASS | max /dev/ 0.000 |
| D44 SAFE | annual value = sum of the 12 months (complete years) | PASS | 768 comparisons; max /dev/ 0.000 |
| D44 SAFE | RMB share identical in the CNY- and USD-denominated sheets (±0.1 pp) | PASS | 434 rows; max /dev/ 0.0458 pp |
| D44 SAFE | latest month 2026-09: RMB share of receipts / payments (USD sheet) | INFO | 46.3% / 51.2% |
| D44 SAFE | derived RMB shares within 0-100 | PASS |  |
| D44 SAFE | by-region workbooks kept raw only | INFO | 2020.xlsx, 2021.xlsx, 2022.xlsx, 2023.xlsx, 2024.xlsx, 2025.xlsx, 2026.xlsx |
| D45 COFER | every observation in the SDMX message lands in the output | PASS | 3154 vs 3154 |
| D45 COFER | no duplicate series x period | PASS | 0 |
| D45 COFER | allocated-reserve currency shares sum to 100 (±0.15) | PASS | 159 groups; min 100.000 max 100.000 |
| D45 COFER | USD sum of currency claims = allocated total (±0.01%) | PASS | 159 groups; max rel dev 4.73e-15 |
| D45 COFER | allocated + unallocated = total reserves (±0.01%) | PASS | 159 groups; max rel dev 5.42e-15 |
| D45 COFER | world quarterly USD-share series contiguous | PASS | 1999-Q1 -> 2026-Q2; missing [] |
| D45 COFER | latest world USD share plausible (50-65%) | PASS | 2026-Q2: 56.70% |
| D45 COFER | CNY first reported quarter (series break when CNY added) | INFO | 2016-Q4 (1.00%); latest 2026-Q2 2.11% |
| D45 COFER | country groups | INFO | G001=World, G110=Advanced Economies, G200=Emerging Market and Developing Economies |
| D46 SWIFT | status | INFO | blocked for scripts (swift.com 403 + login wall); hand-collected CSV not present - see raw/swift_rmb_tracker/README.md |
| D47 CIPS | English monthly + annual tables parsed | PASS | [('cn', 'annual'), ('cn', 'monthly'), ('en', 'annual'), ('en', 'monthly')] |
| D47 CIPS | overview sentences found on the statistics page | PASS | In September 2026, the CIPS system processed a total of 865,000 RMB payment transactions, with a total amount of 22.6 tr |
| D47 CIPS | Chinese and English monthly tables agree (亿元/10 = bn yuan) | PASS | 9 vs 9 rows |
| D47 CIPS | Chinese and English annual tables agree | PASS | 11 vs 11 rows |
| D47 CIPS | monthly rows: daily average x working days = total (±1%) | PASS | 9 months |
| D47 CIPS | months of the current year contiguous from January | PASS | [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0] |
| D47 CIPS | latest month (September 2026) matches the page overview | PASS | page 865,000 tx / 22.6 tn vs table 865,045 / 22.589 tn |
| D47 CIPS | year-to-date sum of months matches the page overview (±0.5%) | PASS | page 6,888,000 / 162.3 tn vs sum 6,888,450 / 162.282 tn |
| D47 CIPS | annual history starts 2015 and is contiguous | PASS | [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025] |
| D47 CIPS | annual values increase every year (CIPS has grown each year since launch) | PASS |  |
| D48 BIS | bulk file | INFO | WS_DER_OTC_TOV_csv_flat.csv: 1,342,771 rows scanned; 161,116 rows match the FX / all-countries / net-net key |
| D48 BIS | every non-missing value of the key subset lands in the output | PASS | 58996 |
| D48 BIS | units are USD millions | PASS |  |
| D48 BIS | survey years are triennial (1989, 1992, ... ) | PASS | [np.int64(1989), np.int64(1992), np.int64(1995), np.int64(1998), np.int64(2001), np.int64(2004), np.int64(2007), np.int64(2010), np.int64(2013), np.int64(2016), np.int64(2019), np.int64(2022), np.int64(2025)] |
| D48 BIS | no duplicate keys | PASS | 0 |
| D48 BIS | listed currencies sum to <= 200% (each trade has two legs) and >= 175% | PASS | 1989: 181.03; 1992: 186.88; 1995: 184.18; 1998: 179.91; 2001: 193.48; 2004: 193.51; 2007: 192.53; 2010: 195.42; 2013: 198.46; 2016: 197.96; 2019: 198.16; 2022: 197.69; 2025: 196.61 |
| D48 BIS | residual 'other currencies' non-negative | PASS | min 1.54 |
| D48 BIS | USD share in 2022 and 2025 within 85-92% | PASS | 1989: 89.9%; 1992: 81.7%; 1995: 83.0%; 1998: 86.8%; 2001: 89.9%; 2004: 88.0%; 2007: 85.6%; 2010: 84.9%; 2013: 87.0%; 2016: 87.6%; 2019: 88.3%; 2022: 88.4%; 2025: 89.1% |
| D48 BIS | CNY share of global FX turnover | INFO | 1998: 0.01%; 2001: 0.01%; 2004: 0.10%; 2007: 0.45%; 2010: 0.86%; 2013: 2.23%; 2016: 3.99%; 2019: 4.33%; 2022: 7.01%; 2025: 8.60% |
| D48 BIS | global FX turnover, USD bn per day | INFO | 1989: 539; 1992: 817; 1995: 1,182; 1998: 1,527; 2001: 1,239; 2004: 1,934; 2007: 3,324; 2010: 3,973; 2013: 5,357; 2016: 5,066; 2019: 6,581; 2022: 7,468; 2025: 9,510 |
| D49 TIC | both files parsed | PASS | slt_table5.txt 325 cells, mfhhis01.txt 12343 cells |
| D49 TIC | series-break comparison columns dropped (older series 'shown for comparison only') | INFO | 11 |
| D49 TIC | the two files overlap on at least 3 months | PASS | ['2025-08', '2025-09', '2025-10', '2025-11', '2025-12'] |
| D49 TIC | overlapping months agree between slt_table5.txt and mfhhis01.txt (±0.05 bn; revisions expected after benchmark surveys) | WARN | 125 overlapping cells, 16 differ |
| D49 TIC | holders listed in mfhhis01.txt but folded into 'All Other' in slt_table5.txt (so absent after its last month) | INFO | Australia, Chile, Colombia, El Salvador, Germany, Israel, Italy, Kuwait, Mexico, Netherlands, Peru, Philippines, Poland, Spain, Sweden, Thailand |
| D49 TIC | every holder of the current table also appears in the history file | PASS | [] |
| D49 TIC | aggregate rows typed as 'country' (older vintages) | INFO | Carib Bnkng Ctrs, Oil Exporters |
| D49 TIC | no duplicate country x month | PASS | 0 |
| D49 TIC | Grand Total months contiguous | PASS | 2000-03 -> 2026-08; missing [] |
| D49 TIC | countries + All Other = Grand Total (±0.55 bn: ~45 rows rounded to 0.1) | PASS | 318 months; worst 0.50 bn |
| D49 TIC | memo: foreign-official Treasury Bills + T-Bonds & Notes = For. Official (±0.35 bn) | PASS | 318 months; worst 0.10 |
| D49 TIC | memo: foreign official holdings below Grand Total | PASS | 318 months |
| D49 TIC | Japan: months contiguous | PASS | 2000-03 -> 2026-08; missing [] |
| D49 TIC | China, Mainland: months contiguous | PASS | 2000-03 -> 2026-08; missing [] |
| D49 TIC | top holders 2026-08 (USD bn) | INFO | Japan 1,068.3; United Kingdom 1,009.5; China, Mainland 590.7; Belgium 490.5; Canada 464.6 |
| D49 TIC | series breaks | INFO | holdings are benchmark-survey based; footnoted series breaks every June (see raw/tic/mfhhis01.txt notes). The new series is kept at each break; the old-series comparison column is dropped |
| D49 TIC | legacy raw/tic/mfh.txt | INFO | not parsed: the file stopped updating in January 2023 and is fully covered by mfhhis01.txt |
| D50 IRFCL gold | every observation in the SDMX messages lands in the output | PASS | 82977 vs 82977 |
| D50 IRFCL gold | no duplicate country x sector x measure x month | PASS | 0 |
| D50 IRFCL gold | rows flagged implausible_volume_in_source (reported ounces imply > 9,000 t; volume blanked, reported value kept) | INFO | AGO/S1XS1311: 70 months 2020-10..2026-07; BRA/S1XS1311: 7 months 2026-03..2026-09 |
| D50 IRFCL gold | USA holds ~8,133 tonnes (±1%) | PASS | 2026-07: 8,133.5 t |
| D50 IRFCL gold | no single reporter above 9,000 tonnes after flagging; euro-area aggregate 10,000-13,000 t | PASS | max country 8,137 t; G163 10,765-12,570 t |
| D50 IRFCL gold | ounces and USD values non-negative | PASS |  |
| D50 IRFCL gold | implied price (USD value / ounces) at market for most reporters: median of latest month within 1,000-10,000 USD/oz | PASS | median 4,442 USD/oz over 82 reporters |
| D50 IRFCL gold | reporters valuing gold at book / statutory value (implied price < 500 USD/oz in the latest month) - use ounces, not USD, for these | INFO | SAU 42; USA 42; HRV 272; ARM 396; NOR 396 |
| D50 IRFCL gold | CHN gold, tonnes | INFO | 2015-06 1,658 -> 2026-08 2,387 (135 months) |
| D50 IRFCL gold | RUS gold, tonnes | INFO | 2004-12 387 -> 2026-08 2,271 (261 months) |
| D50 IRFCL gold | IND gold, tonnes | INFO | 2007-10 358 -> 2026-08 881 (222 months) |
| D50 IRFCL gold | SAU gold, tonnes | INFO | 2014-01 323 -> 2026-08 323 (152 months) |
| D50 IRFCL gold | TUR gold, tonnes | INFO | 2000-08 116 -> 2026-08 791 (313 months) |
| D50 IRFCL gold | POL gold, tonnes | INFO | 2000-04 103 -> 2026-08 648 (314 months) |
| D50 IRFCL gold | coverage | INFO | 96 reporters, 1999-12 -> 2026-09; sectors ['S1311', 'S1X', 'S1XS1311'] |
| D50 WDI reserves | every WDI observation lands in the output | PASS | 19030 |
| D50 WDI reserves | implied gold value never negative | PASS | 0 rows |
| D50 WDI reserves | coverage | INFO | 183 economies (incl. aggregates), 1960-2025 |
| D50 cross-check | IRFCL December gold value vs WDI annual implied gold value: median rel. diff < 10% | PASS | 1381 country-years; median 0.3%, 90th pct 10.0% (WDI gold is at London PM fix, IRFCL at national valuation) |

## Output files

| file | rows | columns |
|---|---|---|
| imf_invoicing_currency.csv | 14,218 | country, iso3, imf_code, year, flow, currency, share_pct |
| safe_crossborder_by_currency.csv | 20,832 | freq, period, date, flow, group, item, parent, unit_currency, unit, value |
| safe_rmb_share.csv | 217 | freq, period, date, receipts_total_usd_100mn, receipts_rmb_usd_100mn, payments_total_usd_100mn, payments_rmb_usd_100mn, goods_receipts_usd_100mn, goods_payments_usd_100mn, rmb_share_receipts_pct, rmb_share_payments_pct, rmb_share_total_pct |
| imf_cofer.csv | 3,154 | country_code, country, indicator_code, indicator, currency_code, currency, transformation, unit, freq, period, date, value, derivation, status |
| cips_volumes.csv | 20 | freq, period, date, year, month, transactions, amount_bn_cny, working_days, daily_avg_transactions, daily_avg_amount_bn_cny, source_file |
| bis_fx_turnover.csv | 58,996 | year, instrument_code, instrument, counterparty_code, counterparty, currency_1, currency_1_name, currency_2, currency_2_name, value_usd_mn, obs_status, unit |
| bis_fx_turnover_by_currency.csv | 503 | year, currency, currency_name, turnover_usd_mn, share_pct_of_200, unit |
| tic_major_foreign_holders.csv | 12,543 | country, row_type, period, date, holdings_usd_bn, source_file |
| imf_irfcl_gold_reserves.csv | 29,054 | iso3, country, sector_code, sector, period, date, gold_troy_oz, gold_tonnes, gold_usd, official_reserve_assets_usd, gold_troy_oz_reported, flag |
| wb_gold_reserves_annual.csv | 9,515 | iso3, country, year, total_reserves_usd, reserves_ex_gold_usd, gold_usd |
| series_catalog.csv | 1,917 | file, series, first, last, n_obs |
| tracker_status.csv | 8 | ID, Status, Date retrieved, Saved file / location |
