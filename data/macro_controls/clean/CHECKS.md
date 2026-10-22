# Macro controls clean-up checks

Run: 2026-10-21T23:14:21+00:00  
Result: **ALL PASSED**  
FAIL 0 · WARN 0 · PASS 224 · INFO 20

## Outputs

| file | rows | columns |
|---|---:|---|
| fed_h15.csv | 49,913 | tracker_ids, source, series_id, series_name, freq, fred_alias, unit, date, source_date, value, flag |
| nyfed_effr.csv | 21,386 | tracker_ids, source, series_id, series_name, unit, date, value, flag |
| wu_xia.csv | 1,492 | tracker_ids, source, series_id, series_name, unit, date, value, flag |
| bauer_swanson.csv | 14,384 | tracker_ids, source, table, series_id, unit, date, time, unscheduled, value, flag, vintage |
| jarocinski_karadi.csv | 4,644 | tracker_ids, source, table, series_id, unit, date, time, value, flag, vintage |
| bls_cpi.csv | 4,425 | tracker_ids, source, series_id, series_name, seasonal, fred_alias, unit, date, value, flag |
| world_bank_inflation.csv | 310,092 | tracker_ids, source, sheet, indicator, freq, raw_row, country_code, imf_country_code, country, indicator_type, series_name, data_source, note, unit, period, date, value, flag, vintage |
| world_bank_inflation_annual.csv | 45,022 | tracker_ids, source, sheet, indicator, freq, raw_row, country_code, imf_country_code, country, indicator_type, series_name, aggregation, sample_country, data_source, note, unit, year, value, flag, vintage |
| baumeister_wip.csv | 3,399 | tracker_ids, source, series_id, series_name, unit, date, value, flag, vintage |
| baumeister_wip_vintages.csv | 97,300 | tracker_ids, source, series_id, unit, vintage, date, value, flag |
| dallasfed_igrea.csv | 705 | tracker_ids, source, series_id, series_name, unit, date, source_date, value, flag, vintage |
| epu.csv | 33,515 | tracker_ids, source, table, series_id, unit, date, value, flag |
| wui.csv | 200,037 | tracker_ids, source, table, table_name, series_id, country_code, country_name, region, unit, date, value, flag |

## Checks

### fed_h15

| status | check | detail |
|---|---|---|
| PASS | raw file present | H15_data.zip |
| PASS | RIFSPFF_N.{D,B,WW,M} series found in the XML | ['RIFSPFF_N.B', 'RIFSPFF_N.D', 'RIFSPFF_N.M', 'RIFSPFF_N.WW'] |
| INFO | series skipped (not in output) | RIFSPFF_N.A (71 obs), RIFSPFF_N.BWAW (1886 obs) |
| PASS | no duplicate (series_id, date) |  |
| PASS | RIFSPFF_N.B: dates contiguous (B) | 1954-07-01 .. 2026-10-20, 18864 days, 0 gaps > 4 days |
| PASS | RIFSPFF_N.B: values in a plausible range (0-25 %) | min 0.04 max 22.36 |
| PASS | RIFSPFF_N.B: starts 1954-07 (tracker coverage from 1954) | 1954-07-01 |
| PASS | RIFSPFF_N.D: dates contiguous (D) | 1954-07-01 .. 2026-10-20, 26410 periods, 0 missing, 0 off-grid |
| PASS | RIFSPFF_N.D: values in a plausible range (0-25 %) | min 0.04 max 22.36 |
| PASS | RIFSPFF_N.D: starts 1954-07 (tracker coverage from 1954) | 1954-07-01 |
| PASS | RIFSPFF_N.M: dates contiguous (MS) | 1954-07-01 .. 2026-09-01, 867 periods, 0 missing, 0 off-grid |
| PASS | RIFSPFF_N.M: values in a plausible range (0-25 %) | min 0.05 max 19.1 |
| PASS | RIFSPFF_N.M: starts 1954-07 (tracker coverage from 1954) | 1954-07-01 |
| PASS | RIFSPFF_N.WW: dates contiguous (W-WED) | 1954-07-07 .. 2026-10-14, 3772 periods, 0 missing, 0 off-grid |
| PASS | RIFSPFF_N.WW: values in a plausible range (0-25 %) | min 0.04 max 20.06 |
| PASS | RIFSPFF_N.WW: starts 1954-07 (tracker coverage from 1954) | 1954-07-07 |
| PASS | RIFSPFF_N.D ends within 10 days of today | 2026-10-20 |
| PASS | monthly RIFSPFF_N.M = mean of daily RIFSPFF_N.D (tolerance 0.01 pp, all full months) | 867 months, max \|diff\| 0.0050 (last month 0.0033) |
| INFO | cells with a status flag instead of a number (ND = no data, -9999 in the XML) | 680 |

### nyfed_effr

| status | check | detail |
|---|---|---|
| PASS | raw file present | effr.csv |
| PASS | columns as expected (Effective Date, Rate Type, Rate (%) ...) | ['Effective Date', 'Rate Type', 'Rate (%)', '1st Percentile (%)', '25th Percentile (%)', '75th Percentile (%)', '99th Percentile (%)', 'Volume ($Billions)', 'Target Rate From (%)', 'Target Rate To (%)', 'Intra Day - Low (%)', 'Intra Day - High (%)', 'Standard Deviation (%)', '30-Day Average SOFR', '90-Day Average SOFR', '180-Day Average SOFR', 'SOFR Index', 'Revision Indicator (Y/N)', 'Footnote ID'] |
| PASS | Rate Type is EFFR on every row | ['EFFR'] |
| PASS | every numeric raw cell captured | 21,385 raw -> 21,385 |
| PASS | no duplicate (series_id, date) |  |
| PASS | EFFR_RATE: business days contiguous | 2016-03-01 .. 2026-10-20, 2673 days, 0 gaps > 4 days |
| PASS | EFFR_RATE: starts 2016-03-01 (NY Fed publication start) | 2016-03-01 |
| PASS | EFFR_RATE: in 0-10 % | min 0.04 max 5.33 |

### wu_xia

| status | check | detail |
|---|---|---|
| PASS | raw file present | WuXiaShadowRate.xlsx |
| PASS | header row names the two series | ['Effective federal funds rate (% p.a.), last business day of month', 'Wu-Xia shadow federal funds rate (last business day of month)'] |
| PASS | every numeric raw cell captured | 1,132 raw -> 1,132 |
| PASS | no duplicate (series_id, date) |  |
| PASS | months contiguous | 1960-01-01 .. 2022-02-01, 746 periods, 0 missing, 0 off-grid |
| PASS | shadow rate covers both ZLB episodes named in the tracker (2009-15, 2020-22) | 1990-01-01 .. 2022-02-01 |
| INFO | last month in the file (Atlanta Fed stopped updating) | 2022-02-01 |
| PASS | values finite and within -6 .. 25 % | min -2.9856426857299105 max 22.0 |

### bauer_swanson

| status | check | detail |
|---|---|---|
| PASS | raw file present | FOMC_Bauer_Swanson.xlsx |
| PASS | both data sheets present | ['Description', 'High-Freq FOMC Announcemt Surp', 'Monthly SVAR Data'] |
| PASS | announcements: every numeric raw cell captured | 5,761 raw -> 5,761 |
| PASS | announcements: no duplicate (date, time, series_id) |  |
| PASS | announcements: 1988-02 .. 2019-12 as documented | 1988-02-04 .. 2019-12-11, 323 announcements |
| PASS | announcements: MPS present on every announcement except the documented 2001-09-17 exclusion, |MPS| < 1 pp | 322 of 323 (missing: ['2001-09-17']), max \|MPS\| 0.301 |
| PASS | monthly: every numeric raw cell captured | 6,234 raw -> 6,234 |
| PASS | monthly: months contiguous | 1973-01-01 .. 2020-02-01, 566 periods, 0 missing, 0 off-grid |
| PASS | monthly: starts 1973-01 as documented | 1973-01-01 |
| PASS | monthly MPS = sum of announcement-level MPS in the month (monthly sheet is rounded to 4 dp: tolerance 2e-4) | 266 months compared, max \|diff\| 1.00e-04 |

### jarocinski_karadi

| status | check | detail |
|---|---|---|
| PASS | raw files present |  |
| PASS | monthly columns year, month + shock columns | ['year', 'month', 'pc1_hf', 'SP500_hf', 'MP_pm', 'CBI_pm', 'MP_median', 'CBI_median'] |
| PASS | announcement columns start + shock columns | ['start', 'pc1', 'SP500', 'MP_pm', 'CBI_pm', 'MP_median', 'CBI_median'] |
| PASS | every numeric raw cell captured | 4,635 raw -> 4,635 |
| PASS | no duplicate (table, series_id, date, time) |  |
| PASS | monthly: months contiguous | 1990-02-01 .. 2026-09-01, 440 periods, 0 missing, 0 off-grid |
| PASS | monthly: starts 1990-02 (first FOMC announcement in the series) | 1990-02-01 |
| PASS | ends within 4 months of today (updated after each FOMC meeting) | 2026-09-01 |
| PASS | monthly shocks = sum of announcement shocks in the month (pc1, MP_*, CBI_*; tolerance 1e-6) | max \|diff\| 2.78e-17 |
| INFO | months where the monthly SP500 surprise is 0 although an announcement-level SP500 move exists (source choice) | 2008-01, 2008-10, 2020-03 |
| PASS | values finite and |value| < 5 | max \|value\| 4.510 |

### bls_cpi

| status | check | detail |
|---|---|---|
| PASS | raw files present | 8 window files |
| PASS | every raw observation captured (monthly) or counted (M13 annual averages excluded) | 4,425 raw -> 4,425 monthly rows + 0 annual averages |
| PASS | no duplicate (series_id, date) across the 10-year windows |  |
| PASS | all 5 requested series present | ['CUSR0000SA0', 'CUSR0000SA0E', 'CUSR0000SA0L1E', 'CUUR0000SA0', 'CUUR0000SA0L1E'] |
| PASS | CUSR0000SA0: months contiguous | 1947-01-01 .. 2026-09-01, 957 periods, 0 missing, 0 off-grid |
| PASS | CUSR0000SA0: positive and month-on-month change < 10 % | 1947-01-01 .. 2026-09-01, max m/m change 1.96 % |
| PASS | CUSR0000SA0E: months contiguous | 1957-01-01 .. 2026-09-01, 837 periods, 0 missing, 0 off-grid |
| PASS | CUSR0000SA0E: positive and month-on-month change < 25 % | 1957-01-01 .. 2026-09-01, max m/m change 18.02 % |
| PASS | CUSR0000SA0L1E: months contiguous | 1957-01-01 .. 2026-09-01, 837 periods, 0 missing, 0 off-grid |
| PASS | CUSR0000SA0L1E: positive and month-on-month change < 10 % | 1957-01-01 .. 2026-09-01, max m/m change 1.42 % |
| PASS | CUUR0000SA0: months contiguous | 1947-01-01 .. 2026-09-01, 957 periods, 0 missing, 0 off-grid |
| PASS | CUUR0000SA0: positive and month-on-month change < 10 % | 1947-01-01 .. 2026-09-01, max m/m change 2.22 % |
| PASS | CUUR0000SA0L1E: months contiguous | 1957-01-01 .. 2026-09-01, 837 periods, 0 missing, 0 off-grid |
| PASS | CUUR0000SA0L1E: positive and month-on-month change < 10 % | 1957-01-01 .. 2026-09-01, max m/m change 1.35 % |
| PASS | CUSR0000SA0 starts 1947-01 (tracker coverage from 1947) |  |
| PASS | latest month within 2 months of today | 2026-09-01 |
| PASS | annual mean of SA all-items = annual mean of NSA all-items (within 0.5 %) | 78 full years, max rel diff 0.078 % |
| INFO | cells with a footnote code | 5 |

### world_bank_inflation

| status | check | detail |
|---|---|---|
| PASS | raw file present | Inflation-data.xlsx |
| PASS | all 18 data sheets present | ok |
| PASS | hcpi_m: period columns and text columns found | 663 periods, 7 text cols |
| PASS | hcpi_m: every numeric cell captured | 58,627 numeric cells -> 58,627 rows |
| PASS | hcpi_m: no duplicate (raw_row, period) |  |
| PASS | hcpi_q: period columns and text columns found | 220 periods, 7 text cols |
| PASS | hcpi_q: every numeric cell captured | 21,450 numeric cells -> 21,450 rows |
| PASS | hcpi_q: no duplicate (raw_row, period) |  |
| PASS | hcpi_a: period columns and text columns found | 55 periods, 6 text cols |
| PASS | hcpi_a: every numeric cell captured | 9,912 numeric cells -> 9,912 rows |
| PASS | hcpi_a: no duplicate (raw_row, period) |  |
| PASS | fcpi_m: period columns and text columns found | 663 periods, 8 text cols |
| PASS | fcpi_m: every numeric cell captured | 45,592 numeric cells -> 45,592 rows |
| PASS | fcpi_m: no duplicate (raw_row, period) |  |
| INFO | fcpi_m: country codes appearing on more than one row (kept apart by raw_row) | SGP, THA |
| PASS | fcpi_q: period columns and text columns found | 221 periods, 8 text cols |
| PASS | fcpi_q: every numeric cell captured | 18,002 numeric cells -> 18,002 rows |
| PASS | fcpi_q: no duplicate (raw_row, period) |  |
| INFO | fcpi_q: country codes appearing on more than one row (kept apart by raw_row) | BGD, COL, SAU |
| PASS | fcpi_a: period columns and text columns found | 55 periods, 6 text cols |
| PASS | fcpi_a: every numeric cell captured | 8,279 numeric cells -> 8,279 rows |
| PASS | fcpi_a: no duplicate (raw_row, period) |  |
| INFO | fcpi_a: country codes appearing on more than one row (kept apart by raw_row) | NCL, VGB |
| PASS | ecpi_m: period columns and text columns found | 663 periods, 7 text cols |
| PASS | ecpi_m: every numeric cell captured | 53,247 numeric cells -> 53,247 rows |
| PASS | ecpi_m: no duplicate (raw_row, period) |  |
| INFO | ecpi_m: country codes appearing on more than one row (kept apart by raw_row) | BHR, BOL, BRA, BWA, CMR, DOM, ECU, EGY, GAB, IRQ, JOR, KWT, LBN, LSO, MOZ, MYS, NAM, OMN, PHL, PRY, QAT, SEN, SGP, TCD, TGO, THA, TUN, UGA, URY |
| PASS | ecpi_q: period columns and text columns found | 221 periods, 7 text cols |
| PASS | ecpi_q: every numeric cell captured | 13,519 numeric cells -> 13,519 rows |
| PASS | ecpi_q: no duplicate (raw_row, period) |  |
| PASS | ecpi_a: period columns and text columns found | 55 periods, 6 text cols |
| PASS | ecpi_a: every numeric cell captured | 6,738 numeric cells -> 6,738 rows |
| PASS | ecpi_a: no duplicate (raw_row, period) |  |
| INFO | ecpi_a: country codes appearing on more than one row (kept apart by raw_row) | VGB |
| PASS | ccpi_m: period columns and text columns found | 663 periods, 7 text cols |
| PASS | ccpi_m: every numeric cell captured | 30,098 numeric cells -> 30,098 rows |
| PASS | ccpi_m: no duplicate (raw_row, period) |  |
| PASS | ccpi_q: period columns and text columns found | 221 periods, 6 text cols |
| PASS | ccpi_q: every numeric cell captured | 10,294 numeric cells -> 10,294 rows |
| PASS | ccpi_q: no duplicate (raw_row, period) |  |
| PASS | ccpi_a: period columns and text columns found | 55 periods, 6 text cols |
| PASS | ccpi_a: every numeric cell captured | 3,136 numeric cells -> 3,136 rows |
| PASS | ccpi_a: no duplicate (raw_row, period) |  |
| PASS | ppi_m: period columns and text columns found | 663 periods, 8 text cols |
| PASS | ppi_m: every numeric cell captured | 36,027 numeric cells -> 36,027 rows |
| PASS | ppi_m: no duplicate (raw_row, period) |  |
| INFO | ppi_m: country codes appearing on more than one row (kept apart by raw_row) | AUT, NLD, PRT, ZAF |
| PASS | ppi_q: period columns and text columns found | 220 periods, 7 text cols |
| PASS | ppi_q: every numeric cell captured | 11,954 numeric cells -> 11,954 rows |
| PASS | ppi_q: no duplicate (raw_row, period) |  |
| INFO | ppi_q: country codes appearing on more than one row (kept apart by raw_row) | MYS |
| PASS | ppi_a: period columns and text columns found | 55 periods, 6 text cols |
| PASS | ppi_a: every numeric cell captured | 3,422 numeric cells -> 3,422 rows |
| PASS | ppi_a: no duplicate (raw_row, period) |  |
| PASS | def_q: period columns and text columns found | 220 periods, 8 text cols |
| PASS | def_q: every numeric cell captured | 11,282 numeric cells -> 11,282 rows |
| PASS | def_q: no duplicate (raw_row, period) |  |
| PASS | def_a: period columns and text columns found | 55 periods, 5 text cols |
| PASS | def_a: every numeric cell captured | 9,520 numeric cells -> 9,520 rows |
| PASS | def_a: no duplicate (raw_row, period) |  |
| PASS | Aggregate: period columns and text columns found | 55 periods, 5 text cols |
| PASS | Aggregate: every numeric cell captured | 4,015 numeric cells -> 4,015 rows |
| PASS | Aggregate: no duplicate (raw_row, period) |  |
| PASS | headline CPI index values (hcpi_m, hcpi_q) are positive | min 1.26994585738447e-13 |
| INFO | non-positive index cells in the other monthly/quarterly sheets (kept as published) | ecpi_m: 78, fcpi_m: 51, fcpi_q: 17 |
| PASS | monthly/quarterly values finite |  |
| PASS | annual inflation rates finite and >= -100 % (hyperinflation episodes reach 1e5 %) | min -100.0 max 169202 |
| PASS | monthly headline CPI starts 1970-01 (tracker coverage from 1970) | 1970-01-01 |
| PASS | headline monthly CPI covers at least 150 countries (tracker: ~200) | 184 country codes |
| INFO | last monthly period in the release | 2025-03-01 |
| PASS | headline CPI quarterly index = mean of monthly index for >= 85 % of country-quarters (within 1 %; the q and m sheets draw on different sources for some countries) | 19,022 country-quarters compared, 91.1 % within 1 %; most off: {'COL': 220, 'ISR': 220, 'JPN': 206, 'USA': 162, 'CHN': 128, 'BGR': 120} |

### baumeister

| status | check | detail |
|---|---|---|
| PASS | raw files present | ['OECD_plus6_industrial_production.xlsx', 'WIP_vintages.xlsx', 'GECON_indicator.xlsx'] |
| PASS | world_IP header names the OECD+6 index | OECD+6NME industrial production |
| PASS | WIP: every numeric raw cell captured | 823 -> 823 |
| PASS | WIP: months contiguous | 1958-01-01 .. 2026-07-01, 823 periods, 0 missing, 0 off-grid |
| PASS | WIP: starts 1958-01 (tracker coverage from 1958) | 1958-01-01 |
| PASS | WIP: positive |  |
| PASS | WIP: ends within 5 months of today (series lags a few months) | 2026-07-01 |
| PASS | GECON header has the 4 indicator columns | ['Global Economic Conditions Indicator', 'Standardized GECON', 'Smoothed GECON3', 'Standardized GECON3'] |
| PASS | GECON: every numeric raw cell captured | 2,572 -> 2,572 |
| PASS | GECON: months contiguous | 1973-02-01 .. 2026-09-01, 644 periods, 0 missing, 0 off-grid |
| PASS | GECON: starts 1973-02 | 1973-02-01 |
| PASS | GECON_STD looks standardised (|mean| < 0.2, sd within 0.8-1.2) | mean 0.000 sd 1.000 |
| PASS | no duplicate (series_id, date) |  |
| PASS | WIP_vintages: header row = index label + vintage dates | 'index (2021 = 100)', 175 vintages |
| PASS | WIP_vintages: every numeric cell captured | 97,300 -> 97,300 |
| PASS | WIP_vintages: no duplicate (vintage, date) |  |
| PASS | WIP_vintages: vintages monthly contiguous from 2012-03 | 2012-03-01 .. 2026-09-01, 175 vintages |
| PASS | latest vintage column = current world IP file on the overlap (tolerance 1e-6) | 643 months, max \|diff\| 0.00e+00 |

### dallasfed_igrea

| status | check | detail |
|---|---|---|
| PASS | raw file present | igrea.xlsx |
| PASS | every numeric raw cell captured | 705 -> 705 |
| PASS | no duplicate month after normalising the day |  |
| PASS | months contiguous | 1968-01-01 .. 2026-09-01, 705 periods, 0 missing, 0 off-grid |
| PASS | starts 1968-01 (tracker coverage from 1968) | 1968-01-01 |
| PASS | ends within 2 months of today | 2026-09-01 |
| PASS | values finite and within -250 .. 250 | min -162.5 max 188.6 |
| INFO | rows whose source date is not the 1st of the month (normalised to month start, original kept in source_date) | 19 rows from 2025-02-25 |

### epu

| status | check | detail |
|---|---|---|
| PASS | raw files present | ['Global_Policy_Uncertainty_Data.xlsx', 'All_Country_Data.xlsx', 'US_Policy_Uncertainty_Data.xlsx', 'All_Daily_Policy_Data.csv', 'China_Policy_Uncertainty_Data.xlsx', 'China_Mainland_Paper_EPU.xlsx'] |
| PASS | daily file columns day, month, year, daily_policy_index | ['day', 'month', 'year', 'daily_policy_index'] |
| PASS | every numeric raw cell captured | 30,938 -> 30,938 |
| PASS | no duplicate (table, series_id, date) |  |
| PASS | all_country/Australia: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Brazil: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Canada: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Chile: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/China: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/France: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/GEPU_current: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/GEPU_ppp: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Germany: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Greece: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/India: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Ireland: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Italy: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Japan: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Korea: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Mainland China: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Mexico: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Pakistan: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Russia: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/SCMP China: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Singapore: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/Spain: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/UK: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | all_country/US: months contiguous | 1985-01-01 .. 2026-07-01, 499 periods, 0 missing, 0 off-grid |
| PASS | china_mainland/EPU: months contiguous | 1949-10-01 .. 2026-08-01, 923 periods, 0 missing, 0 off-grid |
| PASS | china_mainland/TPU: months contiguous | 2000-01-01 .. 2026-08-01, 320 periods, 0 missing, 0 off-grid |
| PASS | china_scmp/China News-Based EPU: months contiguous | 1995-01-01 .. 2019-04-01, 292 periods, 0 missing, 0 off-grid |
| PASS | global/GEPU_current: months contiguous | 1997-01-01 .. 2026-07-01, 355 periods, 0 missing, 0 off-grid |
| PASS | global/GEPU_ppp: months contiguous | 1997-01-01 .. 2026-07-01, 355 periods, 0 missing, 0 off-grid |
| PASS | us_legacy/CPI_disagreement: months contiguous | 1985-01-01 .. 2026-09-01, 501 periods, 0 missing, 0 off-grid |
| PASS | us_legacy/FedStateLocal_Ex_disagreement: months contiguous | 1985-01-01 .. 2026-09-01, 501 periods, 0 missing, 0 off-grid |
| PASS | us_legacy/News_Based_Policy_Uncert_Index: months contiguous | 1985-01-01 .. 2026-09-01, 501 periods, 0 missing, 0 off-grid |
| PASS | us_legacy/Tax_expiration: months contiguous | 1985-01-01 .. 2026-09-01, 501 periods, 0 missing, 0 off-grid |
| PASS | us_legacy/Three_Component_Index: months contiguous | 1985-01-01 .. 2026-09-01, 501 periods, 0 missing, 0 off-grid |
| PASS | us_news/News_Based_Policy_Uncert_Index: months contiguous | 1900-01-01 .. 2026-09-01, 1521 periods, 0 missing, 0 off-grid |
| PASS | us_daily: every calendar day present | 1985-01-01 .. 2026-10-20, 15268 periods, 0 missing, 0 off-grid |
| PASS | us_daily: starts 1985-01-01 | 1985-01-01 |
| PASS | values non-negative and finite | min 0.0 max 1635.4 |
| PASS | global GEPU starts 1997-01 (tracker coverage 1997) |  |
| PASS | US legacy index starts 1985-01 (tracker coverage 1985) |  |
| PASS | latest monthly observation within 3 months of today | 2026-09-01 |
| PASS | all_country GEPU_current = global file GEPU_current | 355 months overlap, 100.0 % identical, max \|diff\| 0.00e+00 |
| PASS | all_country GEPU_ppp = global file GEPU_ppp | 355 months overlap, 100.0 % identical, max \|diff\| 0.00e+00 |
| PASS | all_country US = US legacy news-based index for >= 99 % of months (the all-country file is an older vintage for the last month) | 499 months overlap, 99.8 % identical, max \|diff\| 3.29e+00; differing months: ['2026-07-01'] |
| PASS | all_country 'Mainland China' = China mainland-paper file | 318 months overlap, 100.0 % identical, max \|diff\| 0.00e+00 |
| INFO | all_country 'SCMP China' vs the China (SCMP) file: differently normalised series (not an identity) | 292 months overlap, correlation 0.898, mean ratio 0.917 |

### wui

| status | check | detail |
|---|---|---|
| PASS | raw file present | WUI_Data.xlsx |
| INFO | tab descriptions (T0) | F1: This tab contains the figure for the World Uncertainty Index (WUI). This index measures overall uncertainty across the globe. The index is unbalanced GDP weighted average for 142 countries. \| F2: This tab contains the figure for the World Trade Uncertainty Index (WTUI). This index measures trade uncertainty across the globe. The index is an equally weighted average for 143 countries. \| T1: This tab contains the time series of the World Uncertainty Index (WUI) at the global level (simple average and GDP weighted average), income level (advanced, emerging, and low-income economies), and regional level (Africa, Asia and the Pacific, Europe, Middle East and Central Asia, and Western Hemisphere). The series by income and regional level are unbalanced and use a GDP weighted average. All indices are computed by counting the percent of word “uncertain” (or its variant) in the Economist Intelligence Unit country reports. The WUI is then rescaled by multiplying by 1,000,000. A higher number means higher uncertainty and vice versa \| T2: This tab contains the time series of the World Uncertainty Index (WUI) for 143 countries from 1950s onwards. All indices have been computed by counting the frequency of the world uncertainty (or its variant) in EIU country reports. The indices are normalized by total number of words and rescaled by multiplying by 1,000. A higher number means higher uncertainty and vice versa. \| T3: This tab contains the time series of the total count of the word "uncertainty" (or its variant) in the EIU country reports for 143 countries and from the 1950s onwards. A higher number means higher uncertainty and vice versa. \| T4: This tab contains the time series of the count of the total number of words in the EIU reports for 143 countries and from the 1950s onwards. \| T5: This tab contains the time series of the count of the total number of pages in the EIU countries reports for 143 countries from the 1950s onwards. \| T6: This tab contains the three-quarter weighted moving average of the World Uncertainty Index (WUI) for 143 countries from the 1950s onwards. The 3-quarter weighted moving average is computed as follows: 1996Q4= (1996Q4*0.6) + (1996Q3*0.3) + (1996Q2*0.1)/3. This smoothed version of the index is our preferred measure for country-level data. \| T7: This tab contains the list of country names and the respective ISO codes, WEO codes, and country classifications. Under the regions column, AFR = Africa, APD = Asia and the Pacific, EUR = Europe, MCD = Middle East and Central Asia, and WHD = Western Hemisphere. Under the IMF_income column, 1 = advanced economies, 2 = emerging economies, and 3 = low-income economies. \| T8: This tab contains the aggregate World Trade Uncertainty (WTU) index as well as the index by country. The WTU index is constructed by counting the number of times uncertainty is mentioned within a proximity to a word related to trade in the EIU country reports. The index is equally weighted average and scalled by total number of words in the Economist Intelligence Unit country reports, and multiplied by 100,000. \| T9: This tab contains GDP weights for 142 countries. The GDP values are based on current GDP in US$ from the World Bank. The weights are calculated as centered moving average of +/-5 years. |
| PASS | quarterly tables T1-T6, T8 and country table T7 present | ['T0', 'F1', 'F2', 'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9'] |
| PASS | every numeric raw cell captured | 200,037 -> 200,037 |
| PASS | no duplicate (table, series_id, date) |  |
| PASS | T1: quarters contiguous | 1990-01-01 .. 2026-07-01, 147 periods, 0 missing, 0 off-grid |
| PASS | T2: quarters contiguous | 1952-01-01 .. 2026-07-01, 299 periods, 0 missing, 0 off-grid |
| PASS | T3: quarters contiguous | 1952-01-01 .. 2026-07-01, 299 periods, 0 missing, 0 off-grid |
| PASS | T4: quarters contiguous | 1952-01-01 .. 2026-07-01, 299 periods, 0 missing, 0 off-grid |
| PASS | T5: quarters contiguous | 1952-01-01 .. 2026-07-01, 299 periods, 0 missing, 0 off-grid |
| PASS | T6: quarters contiguous | 1952-07-01 .. 2026-07-01, 297 periods, 0 missing, 0 off-grid |
| PASS | T8: quarters contiguous | 1996-01-01 .. 2026-07-01, 123 periods, 0 missing, 0 off-grid |
| PASS | T1 (regions) starts 1990Q1 | 1990-01-01 |
| PASS | latest quarter within 6 months of today | 2026-07-01 |
| PASS | country columns in T2 all resolve to T7 country codes | [] |
| PASS | values non-negative and finite | min 0.0 max 178882.2 |
| PASS | T2 WUI = T3 count / T4 total words x 1000 (tolerance 1e-3) | 36,204 cells, max \|diff\| 5.61e-07 |
| PASS | F1 chart series = T1 'Global (GDP weighted average)' (tolerance 1e-3) | 147 quarters, max \|diff\| 0.00e+00 |

### cross-source

| status | check | detail |
|---|---|---|
| PASS | H.15 business-daily EFFR = NY Fed EFFR on every overlapping day (tolerance 0.005) | 2,673 days overlap, max \|diff\| 0.0000 |
| PASS | Wu-Xia EFFR column = end-of-month H.15 daily EFFR on every month (tolerance 0.05 pp) | 746 months overlap, max \|diff\| 0.000 |
| INFO | World Bank USA monthly headline CPI vs BLS CPI-U NSA: 12-month inflation differs (use bls_cpi.csv for the US) | since 2000: 303 months, max \|diff\| 4.42 pp, median 0.68 pp, 9 % within 0.1 pp; levels correlate 0.9971 |
| INFO | correlation of world IP 12-month log growth with IGREA (both are demand proxies; positive expected) | 0.20 over 703 months |

### fred

| status | check | detail |
|---|---|---|
| INFO | FRED cross-checks skipped | skipped: FRED_API_KEY not set in ./.env (primary publishers H.15 / BLS / Dallas Fed are used instead) |
