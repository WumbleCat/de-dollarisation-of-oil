# Geopolitics clean-up checks

Run: 2026-10-21T23:17:22+00:00  
Result: **ALL PASSED**  
FAIL 0 · WARN 0 · PASS 120 · INFO 23

## Outputs

| file | rows | columns |
|---|---:|---|
| gpr.csv | 208,914 | tracker_ids, source, file, freq, series_id, series_name, date, value, event, vintage |
| ofac_recent_actions.csv | 3,178 | tracker_ids, source, slug, url, date, title, category, press_release_url, press_release_title, programs, n_programs, n_sdn_added, n_sdn_removed, n_sdn_updated, is_iran, is_russia, is_venezuela, is_oil_shipping, body_text, body_chars |
| ofac_sdn.csv | 19,471 | tracker_ids, source, ent_num, sdn_name, sdn_type, program, title, call_sign, vess_type, tonnage, grt, vess_flag, vess_owner, remarks, snapshot |
| baumeister_hamilton.csv | 3,291 | tracker_ids, source, file, kind, series_id, series_name, unit, date, value, vintage |
| kanzig.csv | 6,392 | tracker_ids, source, file, vintage, sample, freq, series_id, series_name, unit, date, value |
| portwatch_chokepoints.csv | 79,744 | tracker_ids, source, portid, portname, date, n_container, n_dry_bulk, n_general_cargo, n_roro, n_tanker, n_cargo, n_total, capacity_container, capacity_dry_bulk, capacity_general_cargo, capacity_roro, capacity_tanker, capacity_cargo, capacity, unit, vintage |
| portwatch_disruptions.csv | 132 | tracker_ids, source, eventid, eventtype, eventname, alertlevel, country, fromdate, todate, year, severitytext, lat, long, affectedports, n_affectedports, affectedpopulation, editdate |

## Checks

### gpr

| status | check | detail |
|---|---|---|
| PASS | raw files present | data_gpr_export.xls, data_gpr_daily_recent.xls |
| PASS | monthly: every series column is numeric | 112 series |
| PASS | monthly: dates contiguous | 1900-01-01 .. 2026-09-01, 1521 periods, 0 missing |
| PASS | monthly: coverage starts 1900-01-01 (tracker: 1900 hist / 1985) | 1900-01-01 |
| PASS | monthly: last observation recent | last 2026-09-01, today 2026-10-22 |
| PASS | monthly: GPR averages 100 over its base period 1985-2019 | mean 100.00 |
| PASS | monthly: GPRH averages 100 over its base period 1900-2019 | mean 100.00 |
| PASS | monthly: GPRT averages 100 over its base period 1985-2019 | mean 100.00 |
| PASS | monthly: GPRA averages 100 over its base period 1985-2019 | mean 100.00 |
| PASS | monthly: no negative values (indexes, shares, counts) | 0 negative cells |
| PASS | daily: every series column is numeric | 6 series |
| PASS | daily: dates contiguous | 1985-01-01 .. 2026-10-19, 15267 periods, 0 missing |
| PASS | daily: coverage starts 1985-01-01 (tracker: 1900 hist / 1985) | 1985-01-01 |
| PASS | daily: last observation recent | last 2026-10-19, today 2026-10-22 |
| PASS | daily: GPRD averages 100 over its base period 1985-2019 | mean 100.00 |
| PASS | daily: GPRD_ACT averages 100 over its base period 1985-2019 | mean 100.00 |
| PASS | daily: GPRD_THREAT averages 100 over its base period 1985-2019 | mean 100.00 |
| PASS | daily: no negative values (indexes, shares, counts) | 0 negative cells |
| PASS | every numeric raw cell captured | 208,914 numeric cells -> 208,914 rows |
| PASS | no duplicate (file, series_id, date) |  |
| PASS | monthly GPR vs monthly mean of daily GPRD: correlation > 0.9 | corr 0.998 over 501 months |
| INFO | country indexes | ARG, AUS, BEL, BRA, CAN, CHE, CHL, CHN, COL, DEU, DNK, EGY, ESP, FIN, FRA, GBR, HKG, HUN, IDN, IND, ISR, ITA, JPN, KOR, MEX, MYS, NLD, NOR, PER, PHL, POL, PRT, RUS, SAU, SWE, THA, TUN, TUR, TWN, UKR, USA, VEN, VNM, ZAF |
| INFO | daily rows carrying an event label | 11 dates |

### ofac

| status | check | detail |
|---|---|---|
| PASS | listing index present (raw/ofac/index.json) |  |
| INFO | listing crawl | 3178 results reported by the site, 318 pages, 3178 unique actions indexed, crawled 2026-10-21T23:15:55 |
| PASS | listing complete: unique actions >= results reported - 10 | 3178 vs 3178 |
| PASS | every indexed action has its page on disk | 0 missing of 3178 (re-run download_geopolitics.py --only ofac) |
| PASS | every page yields a release date | 0 pages without a date: [] |
| PASS | every action has a parseable date | 0 unparsed |
| PASS | page release date agrees with the listing date | 0 differ of 3178 |
| PASS | page title agrees with the listing title (>= 95%) | 100.0% of 3178 pages with a title |
| PASS | no duplicate slug |  |
| PASS | every page has body text | 0 empty bodies |
| PASS | coverage: actions from 2010 or earlier to this month | 2001-01-10 .. 2026-10-21 |
| PASS | categories are the site's five sections | Enforcement Actions, General Licenses, Miscellaneous, Regulations and Guidance, Sanctions List Updates |
| INFO | actions per year | 2001: 37, 2002: 53, 2003: 72, 2004: 67, 2005: 45, 2006: 69, 2007: 69, 2008: 97, 2009: 93, 2010: 100, 2011: 149, 2012: 129, 2013: 134, 2014: 154, 2015: 128, 2016: 130, 2017: 128, 2018: 140, 2019: 165, 2020: 174, 2021: 160, 2022: 185, 2023: 174, 2024: 192, 2025: 164, 2026: 170 |
| INFO | Iran / Russia / Venezuela / oil-shipping flagged actions | 570 / 440 / 200 / 117 of 3178 |
| INFO | SDN entries counted on the pages | added 20,795, removed 391, updated 381 |
| INFO | most frequent programme tags | SDGT (740), SDNTK (317), NPWMD (250), IFSR (207), RUSSIA-EO14024 (164), SDNT (159), FTO (121), IRGC (98), GLOMAG (98), SYRIA (86), ILLICIT-DRUGS-EO14059 (84), IRAN (73) |
| PASS | programme tags found on most Sanctions List Updates pages | 97.7% |

### ofac_sdn

| status | check | detail |
|---|---|---|
| PASS | raw sdn.csv present |  |
| PASS | 12 columns as documented (sdn.csv layout) | (19472, 12) |
| INFO | blank trailing rows dropped | 1 (first column ["'\\x1a'"]) |
| PASS | ent_num numeric and unique | 0 non-numeric, 0 duplicates |
| PASS | plausible size (> 10,000 entries) | 19,471 entries |
| PASS | every entry has a programme | 0 blank |
| INFO | entries by type | : 10042, individual: 7519, vessel: 1568, aircraft: 342 |
| INFO | largest programmes | RUSSIA-EO14024 (6346), SDGT (3360), IFSR (1620), SDNTK (1363), NPWMD (1205), IRAN-EO13902 (1078), ILLICIT-DRUGS-EO14059 (787), GLOMAG (739), IRAN (679), UKRAINE-EO13662 (536) |

### baumeister_hamilton

| status | check | detail |
|---|---|---|
| PASS | raw files present | BH2_supply_shocks.xlsx, BH2_demand_shocks.xlsx, OECD_plus6_industrial_production.xlsx |
| INFO | BH2_supply_shocks.xlsx: series | oil supply shocks |
| INFO | BH2_demand_shocks.xlsx: series | economic activity shocks, oil consumption demand shocks, oil inventory demand shocks |
| INFO | OECD_plus6_industrial_production.xlsx: series | OECD+6NME industrial production |
| PASS | every numeric raw cell captured | 3,291 cells -> 3,291 rows |
| PASS | no duplicate (series_id, date) |  |
| PASS | four structural shock series | economic_activity_shocks, oil_consumption_demand_shocks, oil_inventory_demand_shocks, oil_supply_shocks |
| PASS | shock series share one sample | 1975-02-01 .. 2026-06-01 |
| PASS | economic_activity_shocks: months contiguous | 1975-02-01 .. 2026-06-01, 617 periods, 0 missing |
| PASS | oecd_6nme_industrial_production: months contiguous | 1958-01-01 .. 2026-07-01, 823 periods, 0 missing |
| PASS | oil_consumption_demand_shocks: months contiguous | 1975-02-01 .. 2026-06-01, 617 periods, 0 missing |
| PASS | oil_inventory_demand_shocks: months contiguous | 1975-02-01 .. 2026-06-01, 617 periods, 0 missing |
| PASS | oil_supply_shocks: months contiguous | 1975-02-01 .. 2026-06-01, 617 periods, 0 missing |
| PASS | coverage: shocks start 1975 (tracker: 1975) | 1975-02-01 |
| PASS | shocks updated within the last 12 months | 2026-06-01 |
| PASS | economic_activity_shocks: shock centred and finite (|mean| < 0.3, 0.3 < sd < 5) | mean -0.014, sd 0.652 |
| PASS | oil_consumption_demand_shocks: shock centred and finite (|mean| < 0.3, 0.3 < sd < 5) | mean -0.088, sd 3.091 |
| PASS | oil_inventory_demand_shocks: shock centred and finite (|mean| < 0.3, 0.3 < sd < 5) | mean 0.008, sd 1.111 |
| PASS | oil_supply_shocks: shock centred and finite (|mean| < 0.3, 0.3 < sd < 5) | mean -0.046, sd 1.812 |
| PASS | world IP index positive | 12.22 .. 111.49 |
| INFO | economic_activity_shocks: correlation with the 2023 vintage (re-estimation drift) | 0.931 over 579 months |
| INFO | oil_consumption_demand_shocks: correlation with the 2023 vintage (re-estimation drift) | 0.985 over 579 months |
| INFO | oil_inventory_demand_shocks: correlation with the 2023 vintage (re-estimation drift) | 0.994 over 579 months |
| INFO | oil_supply_shocks: correlation with the 2023 vintage (re-estimation drift) | 0.981 over 579 months |

### kanzig

| status | check | detail |
|---|---|---|
| PASS | raw vintage files present | 12 files |
| INFO | vintages on disk | 2017M12, 2020M12, 2021M08, 2021M12, 2022M06, 2022M12, 2023M06, 2023M12, 2024M06, 2024M12, 2025M06, 2025M12; cleaned: 2025M12 |
| PASS | four sheets as documented in the README | Daily (pre-Covid), Monthly (pre-Covid), Daily, Monthly |
| PASS | Daily (pre-Covid): announcement dates unique | 123 dates 1983-07-19 .. 2019-12-06 |
| PASS | Monthly (pre-Covid): expected columns | date, Oil supply surprise series, Oil supply news shock |
| PASS | Monthly (pre-Covid): months contiguous | 1975-01-01 .. 2019-12-01, 540 periods, 0 missing |
| PASS | Daily: announcement dates unique | 169 dates 1983-07-19 .. 2025-12-01 |
| PASS | Monthly: expected columns | date, Oil supply surprise series, Oil supply news shock |
| PASS | Monthly: months contiguous | 1975-01-01 .. 2025-12-01, 612 periods, 0 missing |
| PASS | every numeric raw cell captured | 6,392 cells -> 6,392 rows |
| PASS | no duplicate (sample, series_id, date) |  |
| PASS | monthly series start 1975 (tracker: 1983 daily / 1975 monthly) | 1975-01-01 |
| PASS | latest vintage month equals the last monthly observation | 2025-12-01 |
| PASS | full: monthly surprise = sum of daily PC surprises in the month | max \|diff\| 0.00e+00 over 612 months |
| PASS | full: news shock standardised (|mean| < 0.3, 0.5 < sd < 2.5) | mean 0.000, sd 0.593 |
| PASS | pre_covid: monthly surprise = sum of daily PC surprises in the month | max \|diff\| 0.00e+00 over 540 months |
| PASS | pre_covid: news shock standardised (|mean| < 0.3, 0.5 < sd < 2.5) | mean 0.000, sd 0.602 |
| INFO | OPEC announcement dates in the full sample (event-study list) | 169 dates, 1983-07-19 .. 2025-12-01 |

### portwatch

| status | check | detail |
|---|---|---|
| PASS | raw daily_chokepoints.json present |  |
| PASS | rows fetched = count reported by the ArcGIS service | 79,744 vs 79,744 |
| PASS | expected columns present | date, year, month, day, portid, portname, n_container, n_dry_bulk, n_general_cargo, n_roro, n_tanker, n_cargo, n_total, capacity_container, capacity_dry_bulk, capacity_general_cargo, capacity_roro, capacity_tanker, capacity_cargo, capacity, ObjectId |
| PASS | date agrees with year/month/day fields |  |
| PASS | no duplicate (portid, date) |  |
| PASS | 28 chokepoints, all present in the daily table | 28 in daily, 28 in the chokepoint database |
| PASS | chokepoint names agree with the chokepoint database |  |
| PASS | Suez Canal (chokepoint1): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Oresund Strait (chokepoint10): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Taiwan Strait (chokepoint11): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Korea Strait (chokepoint12): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Tsugaru Strait (chokepoint13): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Luzon Strait (chokepoint14): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Lombok Strait (chokepoint15): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Ombai Strait (chokepoint16): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Bohai Strait (chokepoint17): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Torres Strait (chokepoint18): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Sunda Strait (chokepoint19): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Panama Canal (chokepoint2): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Makassar Strait (chokepoint20): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Magellan Strait (chokepoint21): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Yucatan Channel (chokepoint22): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Windward Passage (chokepoint23): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Mona Passage (chokepoint24): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Balabac Strait (chokepoint25): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Bering Strait (chokepoint26): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Mindoro Strait (chokepoint27): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Kerch Strait (chokepoint28): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Bosporus Strait (chokepoint3): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Bab el-Mandeb Strait (chokepoint4): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Malacca Strait (chokepoint5): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Strait of Hormuz (chokepoint6): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Cape of Good Hope (chokepoint7): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Gibraltar Strait (chokepoint8): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | Dover Strait (chokepoint9): days contiguous | 2019-01-01 .. 2026-10-18, 2848 periods, 0 missing |
| PASS | coverage: every chokepoint starts 2019-01-01 (tracker: 2019) | 2019-01-01 .. 2019-01-01 |
| PASS | every chokepoint ends on the same day | 2026-10-18 |
| PASS | last observation within 10 days of today | last 2026-10-18, today 2026-10-22 |
| PASS | counts and capacities numeric, no missing | 0 missing |
| PASS | no negative counts / capacities | 0 negative |
| PASS | identity: n_total = n_cargo + n_tanker | max \|diff\| 0 |
| PASS | identity: n_cargo = container + dry bulk + general cargo + roro | max \|diff\| 0 |
| PASS | identity: capacity = capacity_cargo + capacity_tanker (integer rounding, tol 5 t) | max \|diff\| 1 |
| PASS | identity: capacity_cargo = sum of cargo-type capacities (integer rounding, tol 5 t) | max \|diff\| 3 |
| PASS | capacity is zero whenever the count is zero |  |
| INFO | tanker transits with no capacity estimate (count > 0, capacity 0) | 3903 chokepoint-days of 79,744 |
| INFO | Strait of Hormuz tanker transits per day: 2025 mean vs March 2026 mean vs last 30 days | 48.2 vs 0.9 vs 0.8 |
| INFO | Bab el-Mandeb total transits per day: 2023-H1 mean vs 2024 mean | 74.1 vs 32.5 |

### portwatch_disruptions

| status | check | detail |
|---|---|---|
| PASS | raw disruptions_database.json present |  |
| PASS | rows = count reported | 132 vs 132 |
| PASS | every event has a start date | 0 missing |
| PASS | eventid unique |  |
| INFO | events by type | TC: 72, EQ: 32, FL: 14, OT: 5, DR: 4, WF: 3, VO: 2 |
