"""Clean the raw *Macro controls* downloads (tracker rows D30-D36) in ./raw into tidy CSVs in ./clean, and run
sanity checks that must all pass before anything is written.

Outputs (data/macro_controls/clean/)
  fed_h15.csv                    D30  effective federal funds rate from the Board's H.15 release: daily (= FRED DFF),
                                      business-daily, weekly (Wednesday-ending) and monthly (= FRED FEDFUNDS), 1954-07 ->
  nyfed_effr.csv                 D30  NY Fed EFFR publication: rate, percentiles, volume, target range, 2016-03 ->
  wu_xia.csv                     D30  Wu-Xia shadow rate + the EFFR column of the Atlanta Fed file, monthly 1960-01 .. 2022-02
  bauer_swanson.csv              D31  Bauer-Swanson FOMC announcement surprises (per announcement) + monthly SVAR data
  jarocinski_karadi.csv          D31  Jarocinski-Karadi shocks, monthly sums and per announcement, 1990-02 ->
  bls_cpi.csv                    D32  CPI-U all items / core / energy, SA and NSA (index 1982-84=100), monthly 1947-01 ->
  world_bank_inflation.csv       D33  World Bank Global Database of Inflation, monthly + quarterly sheets (indices)
  world_bank_inflation_annual.csv D33 ... annual inflation-rate sheets + the Aggregate sheet (integer `year`)
  baumeister_wip.csv             D34  Baumeister-Hamilton world IP index (OECD+6) and the GECON indicator, monthly
  baumeister_wip_vintages.csv    D34  real-time vintages of the world IP index (one column per vintage, long)
  dallasfed_igrea.csv            D35  Kilian index of global real economic activity (= FRED IGREA), monthly 1968-01 ->
  epu.csv                        D36  policyuncertainty.com indices: global, all-country, US (news, legacy, daily), China
  wui.csv                        D36  World Uncertainty Index tables (regions, by country, word counts, trade), quarterly
  series_catalog.csv                  one row per series in every file: coverage and observation counts
  tracker_status.csv                  suggested Status / Date retrieved / Saved file values for the tracker workbook
  CHECKS.md                           every check with PASS / WARN / FAIL / INFO and details

Any FAIL aborts the write of the data files (CHECKS.md is still written) and exits 1.
Run `python data/macro_controls/download_macro_controls.py` first.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent          # data/macro_controls
RAW = HERE / "raw"
CLEAN = HERE / "clean"
ROOT = HERE.parents[1]
CATEGORY = "Macro controls"
TODAY = date.today().isoformat()

# --------------------------------------------------------------------------------------
# check registry (same semantics as data/fundamentals/clean_fundamentals.py)
# --------------------------------------------------------------------------------------
CHECKS: list[tuple[str, str, str, str]] = []   # (source, name, status, detail)


def check(source: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((source, name, "PASS" if bool(ok) else "FAIL", str(detail)))
    return bool(ok)


def warn(source: str, name: str, ok: bool, detail: str = "") -> bool:
    """A failure is a WARN: shown prominently, does not block writing. Only for coverage gaps caused by the
    source's access limits, where every file that IS present passed its own checks."""
    CHECKS.append((source, name, "PASS" if bool(ok) else "WARN", str(detail)))
    return bool(ok)


def info(source: str, name: str, detail: str = "") -> None:
    CHECKS.append((source, name, "INFO", str(detail)))


def to_float(v):
    """(float or NaN, flag): flags are the source's non-numeric tokens, kept verbatim."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan, ""
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        return float(v), ""
    s = str(v).strip()
    if s == "":
        return np.nan, ""
    try:
        return float(s.replace(",", "")), ""
    except ValueError:
        return np.nan, s


def contiguous(dates, freq: str) -> tuple[bool, str]:
    """freq: 'D' (every calendar day), 'B' (business days, gaps <= 4 days allowed), 'W', 'MS', 'QS'."""
    d = pd.to_datetime(pd.Series(dates).drop_duplicates()).sort_values()
    if d.empty:
        return False, "no dates"
    if freq == "B":
        gaps = d.diff().dt.days.dropna()
        bad = gaps[gaps > 4]
        return bad.empty, f"{d.iloc[0].date()} .. {d.iloc[-1].date()}, {len(d)} days, {len(bad)} gaps > 4 days"
    expected = pd.date_range(d.iloc[0], d.iloc[-1], freq=freq)
    missing = expected.difference(d)
    extra = d[~d.isin(expected)]
    return missing.empty and extra.empty, (f"{d.iloc[0].date()} .. {d.iloc[-1].date()}, {len(d)} periods, "
                                           f"{len(missing)} missing, {len(extra)} off-grid")


def manifest() -> dict:
    p = RAW / "manifest.json"
    if not p.exists():
        sys.exit(f"{p.relative_to(ROOT).as_posix()} not found: run download_macro_controls.py first")
    return json.loads(p.read_text(encoding="utf-8"))


def raw_ok(m: dict, source: str, name_part: str) -> bool:
    files = m["sources"].get(source, {}).get("files", [])
    return any(name_part in f.get("file", "") and str(f.get("status", "")).startswith(("ok", "skipped")) for f in files)


def vintage_of(m: dict, source: str, name_part: str) -> str:
    """Date stamp for a revised file: the publisher's Last-Modified when given, else the download day."""
    for f in m["sources"].get(source, {}).get("files", []):
        if name_part in f.get("file", "") and "vintages/" not in f["file"]:
            lm = f.get("last_modified")
            if lm:
                try:
                    return datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S %Z").date().isoformat()
                except ValueError:
                    pass
            dl = f.get("downloaded_at")
            if dl:
                return dl[:10]
    return TODAY


def month_start(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s)
    return d.dt.to_period("M").dt.to_timestamp()


def iso(d) -> pd.Series:
    return pd.to_datetime(d).dt.strftime("%Y-%m-%d")


def numeric_cells(block: pd.DataFrame) -> int:
    return int(block.apply(pd.to_numeric, errors="coerce").notna().sum().sum())


def melt_wide(df: pd.DataFrame, id_vars: list[str], value_vars: list, var_name: str = "series_id") -> pd.DataFrame:
    """Wide -> long keeping every cell (value NaN + flag for non-numeric tokens)."""
    long = df.melt(id_vars=id_vars, value_vars=value_vars, var_name=var_name, value_name="raw")
    vf = long["raw"].map(to_float)
    long["value"] = [v for v, _ in vf]
    long["flag"] = [f for _, f in vf]
    return long.drop(columns="raw")


# --------------------------------------------------------------------------------------
# D30  Federal Reserve H.15 (effective federal funds rate)
# --------------------------------------------------------------------------------------
H15_KEEP = {   # series suffix -> (freq label, FRED alias)
    "RIFSPFF_N.D": ("D", "DFF"),
    "RIFSPFF_N.B": ("B", ""),
    "RIFSPFF_N.WW": ("W", "FF"),
    "RIFSPFF_N.M": ("M", "FEDFUNDS"),
}


def clean_fed_h15(m: dict, src: str = "fed_h15") -> pd.DataFrame | None:
    path = RAW / src / "H15_data.zip"
    if not check(src, "raw file present", raw_ok(m, src, "H15_data.zip") and path.exists(), str(path.name)):
        return None
    rows, skipped, names = [], {}, {}
    with zipfile.ZipFile(path) as z, z.open("H15_data.xml") as fh:
        for _event, el in ET.iterparse(fh, events=("end",)):
            if not el.tag.endswith("}Series"):
                continue
            sid = el.get("SERIES_NAME", "")
            if sid.startswith("RIFSPFF_N."):
                long_desc = ""
                for ann in el.iter():
                    if ann.tag.endswith("}AnnotationText") and ann.text and "effective" in ann.text.lower():
                        long_desc = ann.text.strip()
                if sid in H15_KEEP:
                    freq, alias = H15_KEEP[sid]
                    names[sid] = long_desc or "Federal funds effective rate"
                    for obs in el.iter():
                        if obs.tag.endswith("}Obs"):
                            value, flag = to_float(obs.get("OBS_VALUE"))
                            status = obs.get("OBS_STATUS", "")
                            if status != "A":            # "ND" = no data; the Board fills OBS_VALUE with -9999
                                value, flag = np.nan, status
                            rows.append({"series_id": sid, "freq": freq, "fred_alias": alias, "unit": el.get("UNIT", "percent"),
                                         "time_period": obs.get("TIME_PERIOD"), "value": value, "flag": flag})
                else:
                    skipped[sid] = sum(1 for o in el.iter() if o.tag.endswith("}Obs"))
            el.clear()
    df = pd.DataFrame(rows)
    if not check(src, "RIFSPFF_N.{D,B,WW,M} series found in the XML", set(df["series_id"]) == set(H15_KEEP), sorted(set(df["series_id"]))):
        return None
    df["series_name"] = df["series_id"].map(names)
    df["source_date"] = df["time_period"]
    monthly = df["freq"] == "M"
    df.loc[monthly, "time_period"] = month_start(df.loc[monthly, "time_period"]).dt.strftime("%Y-%m-%d")
    df["date"] = iso(df["time_period"])
    df.insert(0, "tracker_ids", "D30")
    df.insert(1, "source", src)
    df["unit"] = df["unit"].str.replace("Percent:_Per_Year", "percent per year")
    info(src, "series skipped (not in output)", ", ".join(f"{k} ({v} obs)" for k, v in sorted(skipped.items())))
    check(src, "no duplicate (series_id, date)", not df.duplicated(["series_id", "date"]).any())
    for sid, g in df.groupby("series_id"):
        freq = {"D": "D", "B": "B", "W": "W-WED", "M": "MS"}[g["freq"].iloc[0]]
        ok, detail = contiguous(g["date"], freq)
        check(src, f"{sid}: dates contiguous ({freq})", ok, detail)
        vals = g["value"].dropna()
        check(src, f"{sid}: values in a plausible range (0-25 %)", vals.between(0, 25).all(), f"min {vals.min()} max {vals.max()}")
        check(src, f"{sid}: starts 1954-07 (tracker coverage from 1954)", g["date"].min() <= "1954-07-31", g["date"].min())
    check(src, "RIFSPFF_N.D ends within 10 days of today", (pd.Timestamp.today() - pd.Timestamp(df.loc[df.freq == "D", "date"].max())).days <= 10,
          df.loc[df.freq == "D", "date"].max())
    # identity: the monthly figure is the average of the calendar-daily series
    d = df[df.freq == "D"].dropna(subset=["value"]).assign(month=lambda x: x["date"].str[:7])
    mm = df[df.freq == "M"].dropna(subset=["value"]).assign(month=lambda x: x["date"].str[:7]).set_index("month")["value"]
    avg = d.groupby("month")["value"].mean()
    both = pd.concat([avg.rename("daily_avg"), mm.rename("monthly")], axis=1).dropna()
    diff = (both["daily_avg"] - both["monthly"]).abs()
    check(src, "monthly RIFSPFF_N.M = mean of daily RIFSPFF_N.D (tolerance 0.01 pp, all full months)",
          (diff.iloc[:-1] <= 0.011).all(), f"{len(both)} months, max |diff| {diff.iloc[:-1].max():.4f} (last month {diff.iloc[-1]:.4f})")
    info(src, "cells with a status flag instead of a number (ND = no data, -9999 in the XML)", int((df["flag"] != "").sum()))
    cols = ["tracker_ids", "source", "series_id", "series_name", "freq", "fred_alias", "unit", "date", "source_date", "value", "flag"]
    return df[cols].sort_values(["series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D30  NY Fed EFFR (cross-check)
# --------------------------------------------------------------------------------------
def clean_nyfed_effr(m: dict, src: str = "nyfed_effr") -> pd.DataFrame | None:
    path = RAW / src / "effr.csv"
    if not check(src, "raw file present", raw_ok(m, src, "effr.csv") and path.exists(), path.name):
        return None
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    check(src, "columns as expected (Effective Date, Rate Type, Rate (%) ...)", {"Effective Date", "Rate Type", "Rate (%)"} <= set(raw.columns), list(raw.columns))
    check(src, "Rate Type is EFFR on every row", (raw["Rate Type"] == "EFFR").all(), raw["Rate Type"].unique().tolist())
    value_cols = [c for c in raw.columns if c not in ("Effective Date", "Rate Type")]
    n_raw = numeric_cells(raw[value_cols])
    raw["date"] = iso(pd.to_datetime(raw["Effective Date"]))
    long = melt_wide(raw, ["date"], value_cols, var_name="series_name")
    long = long[long["flag"].ne("") | long["value"].notna()]     # blanks in optional columns are not observations
    long["series_id"] = long["series_name"].str.replace(r"\s*\(.*?\)", "", regex=True).str.strip().str.upper().str.replace(r"[^A-Z0-9]+", "_", regex=True).str.strip("_")
    long["series_id"] = "EFFR_" + long["series_id"].replace({"RATE": "RATE"})
    long["unit"] = np.where(long["series_name"].str.contains(r"\$"), "USD billions", "percent")
    check(src, "every numeric raw cell captured", int(long["value"].notna().sum()) == n_raw, f"{n_raw:,} raw -> {int(long['value'].notna().sum()):,}")
    check(src, "no duplicate (series_id, date)", not long.duplicated(["series_id", "date"]).any())
    r = long[long.series_id == "EFFR_RATE"]
    ok, detail = contiguous(r["date"], "B")
    check(src, "EFFR_RATE: business days contiguous", ok, detail)
    check(src, "EFFR_RATE: starts 2016-03-01 (NY Fed publication start)", r["date"].min() == "2016-03-01", r["date"].min())
    check(src, "EFFR_RATE: in 0-10 %", r["value"].between(0, 10).all(), f"min {r['value'].min()} max {r['value'].max()}")
    long.insert(0, "tracker_ids", "D30")
    long.insert(1, "source", src)
    cols = ["tracker_ids", "source", "series_id", "series_name", "unit", "date", "value", "flag"]
    return long[cols].sort_values(["series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D30  Wu-Xia shadow rate
# --------------------------------------------------------------------------------------
def clean_wu_xia(m: dict, src: str = "wu_xia") -> pd.DataFrame | None:
    path = RAW / src / "WuXiaShadowRate.xlsx"
    if not check(src, "raw file present", raw_ok(m, src, "WuXiaShadowRate.xlsx") and path.exists(), path.name):
        return None
    raw = pd.read_excel(path, sheet_name="Data", header=None)
    hdr = raw.iloc[0].tolist()
    check(src, "header row names the two series", isinstance(hdr[1], str) and "federal funds" in hdr[1].lower()
          and isinstance(hdr[2], str) and "shadow" in hdr[2].lower(), [hdr[1], hdr[2]])
    body = raw.iloc[1:, :3].copy()
    body.columns = ["date", "EFFR", "SHADOW_RATE"]
    body = body[pd.to_datetime(body["date"], errors="coerce").notna()]
    n_raw = numeric_cells(body[["EFFR", "SHADOW_RATE"]])
    body["date"] = iso(month_start(body["date"]))
    long = melt_wide(body, ["date"], ["EFFR", "SHADOW_RATE"])
    long["series_name"] = long["series_id"].map({"EFFR": str(hdr[1]).strip(), "SHADOW_RATE": str(hdr[2]).strip()})
    long["unit"] = "percent"
    check(src, "every numeric raw cell captured", int(long["value"].notna().sum()) == n_raw, f"{n_raw:,} raw -> {int(long['value'].notna().sum()):,}")
    check(src, "no duplicate (series_id, date)", not long.duplicated(["series_id", "date"]).any())
    ok, detail = contiguous(long["date"], "MS")
    check(src, "months contiguous", ok, detail)
    sh = long[(long.series_id == "SHADOW_RATE") & long.value.notna()]
    check(src, "shadow rate covers both ZLB episodes named in the tracker (2009-15, 2020-22)",
          sh["date"].min() <= "2009-01-01" and sh["date"].max() >= "2022-01-01", f"{sh['date'].min()} .. {sh['date'].max()}")
    info(src, "last month in the file (Atlanta Fed stopped updating)", long["date"].max())
    check(src, "values finite and within -6 .. 25 %", long["value"].dropna().between(-6, 25).all(), f"min {long['value'].min()} max {long['value'].max()}")
    long.insert(0, "tracker_ids", "D30")
    long.insert(1, "source", src)
    cols = ["tracker_ids", "source", "series_id", "series_name", "unit", "date", "value", "flag"]
    return long[cols].sort_values(["series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D31  Bauer & Swanson
# --------------------------------------------------------------------------------------
def clean_bauer_swanson(m: dict, src: str = "bauer_swanson") -> pd.DataFrame | None:
    path = RAW / src / "FOMC_Bauer_Swanson.xlsx"
    if not check(src, "raw file present", raw_ok(m, src, "FOMC_Bauer_Swanson.xlsx") and path.exists(), path.name):
        return None
    vintage = vintage_of(m, src, "FOMC_Bauer_Swanson.xlsx")
    x = pd.ExcelFile(path)
    check(src, "both data sheets present", {"High-Freq FOMC Announcemt Surp", "Monthly SVAR Data"} <= set(x.sheet_names), x.sheet_names)
    out = []
    # per-announcement sheet
    a = x.parse("High-Freq FOMC Announcemt Surp", header=0)
    a = a[pd.to_datetime(a["Date"], errors="coerce").notna()].copy()
    vcols = [c for c in a.columns if c not in ("Date", "Time", "Unscheduled")]
    n_raw_a = numeric_cells(a[vcols])
    a["date"] = iso(a["Date"])
    a["time"] = a["Time"].astype(str)
    a["unscheduled"] = pd.to_numeric(a["Unscheduled"], errors="coerce").astype("Int64")
    la = melt_wide(a, ["date", "time", "unscheduled"], vcols)
    la["table"] = "fomc_announcements"
    check(src, "announcements: every numeric raw cell captured", int(la["value"].notna().sum()) == n_raw_a, f"{n_raw_a:,} raw -> {int(la['value'].notna().sum()):,}")
    check(src, "announcements: no duplicate (date, time, series_id)", not la.duplicated(["date", "time", "series_id"]).any())
    check(src, "announcements: 1988-02 .. 2019-12 as documented", a["date"].min().startswith("1988-02") and a["date"].max().startswith("2019-12"),
          f"{a['date'].min()} .. {a['date'].max()}, {len(a)} announcements")
    mps = la[(la.series_id == "MPS") & la.value.notna()]
    missing = sorted(set(a["date"]) - set(mps["date"]))
    check(src, "announcements: MPS present on every announcement except the documented 2001-09-17 exclusion, |MPS| < 1 pp",
          missing in ([], ["2001-09-17"]) and mps["value"].abs().lt(1).all(),
          f"{len(mps)} of {len(a)} (missing: {missing}), max |MPS| {mps['value'].abs().max():.3f}")
    out.append(la)
    # monthly sheet
    s = x.parse("Monthly SVAR Data", header=0)
    s = s.rename(columns={s.columns[0]: "Date"})
    s = s[pd.to_datetime(s["Date"], errors="coerce").notna()].copy()
    vcols_s = [c for c in s.columns if c != "Date"]
    n_raw_s = numeric_cells(s[vcols_s])
    s["date"] = iso(month_start(s["Date"]))
    s["time"] = ""
    s["unscheduled"] = pd.array([pd.NA] * len(s), dtype="Int64")
    ls = melt_wide(s, ["date", "time", "unscheduled"], vcols_s)
    ls["table"] = "monthly_svar"
    check(src, "monthly: every numeric raw cell captured", int(ls["value"].notna().sum()) == n_raw_s, f"{n_raw_s:,} raw -> {int(ls['value'].notna().sum()):,}")
    ok, detail = contiguous(s["date"], "MS")
    check(src, "monthly: months contiguous", ok, detail)
    check(src, "monthly: starts 1973-01 as documented", s["date"].min() == "1973-01-01", s["date"].min())
    # identity: monthly MPS = sum of announcement MPS within the month (documented construction)
    am = mps.assign(month=mps["date"].str[:7]).groupby("month")["value"].sum()
    sm = ls[(ls.series_id == "MPS") & ls.value.notna()].assign(month=lambda d: d["date"].str[:7]).set_index("month")["value"]
    both = pd.concat([am.rename("announcements"), sm.rename("monthly")], axis=1).dropna()
    diff = (both["announcements"] - both["monthly"]).abs()
    check(src, "monthly MPS = sum of announcement-level MPS in the month (monthly sheet is rounded to 4 dp: tolerance 2e-4)",
          (diff <= 2e-4).all(), f"{len(both)} months compared, max |diff| {diff.max():.2e}")
    out.append(ls)
    df = pd.concat(out, ignore_index=True)
    df["series_id"] = df["series_id"].astype(str)
    df["unit"] = np.where(df["table"] == "fomc_announcements", "pp / 100*log change (see source Description sheet)", "see source Description sheet")
    df["vintage"] = vintage
    df.insert(0, "tracker_ids", "D31")
    df.insert(1, "source", src)
    cols = ["tracker_ids", "source", "table", "series_id", "unit", "date", "time", "unscheduled", "value", "flag", "vintage"]
    return df[cols].sort_values(["table", "series_id", "date", "time"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D31  Jarocinski-Karadi
# --------------------------------------------------------------------------------------
def clean_jarocinski_karadi(m: dict, src: str = "jarocinski_karadi") -> pd.DataFrame | None:
    pm, pt = RAW / src / "shocks_fed_jk_m.csv", RAW / src / "shocks_fed_jk_t.csv"
    if not check(src, "raw files present", raw_ok(m, src, "shocks_fed_jk_m.csv") and raw_ok(m, src, "shocks_fed_jk_t.csv") and pm.exists() and pt.exists()):
        return None
    vintage = vintage_of(m, src, "shocks_fed_jk_m.csv")
    mo = pd.read_csv(pm)
    an = pd.read_csv(pt)
    check(src, "monthly columns year, month + shock columns", {"year", "month"} <= set(mo.columns), list(mo.columns))
    check(src, "announcement columns start + shock columns", "start" in an.columns, list(an.columns))
    mcols = [c for c in mo.columns if c not in ("year", "month")]
    acols = [c for c in an.columns if c != "start"]
    n_raw = numeric_cells(mo[mcols]) + numeric_cells(an[acols])
    mo["date"] = iso(pd.to_datetime(dict(year=mo["year"], month=mo["month"], day=1)))
    mo["time"] = ""
    lm = melt_wide(mo, ["date", "time"], mcols)
    lm["table"] = "monthly"
    lm["series_id"] = lm["series_id"].str.replace("_hf", "", regex=False)      # pc1_hf -> pc1, SP500_hf -> SP500 (same series as the announcement file)
    st = pd.to_datetime(an["start"])
    an["date"] = iso(st)
    an["time"] = st.dt.strftime("%H:%M")
    la = melt_wide(an, ["date", "time"], acols)
    la["table"] = "announcements"
    df = pd.concat([lm, la], ignore_index=True)
    check(src, "every numeric raw cell captured", int(df["value"].notna().sum()) == n_raw, f"{n_raw:,} raw -> {int(df['value'].notna().sum()):,}")
    check(src, "no duplicate (table, series_id, date, time)", not df.duplicated(["table", "series_id", "date", "time"]).any())
    ok, detail = contiguous(mo["date"], "MS")
    check(src, "monthly: months contiguous", ok, detail)
    check(src, "monthly: starts 1990-02 (first FOMC announcement in the series)", mo["date"].min() == "1990-02-01", mo["date"].min())
    check(src, "ends within 4 months of today (updated after each FOMC meeting)", (pd.Timestamp.today() - pd.Timestamp(mo["date"].max())).days <= 125, mo["date"].max())
    # identity: monthly file = sum of announcement-level shocks in the month
    worst, sp_months = 0.0, []
    for sid in ("MP_pm", "CBI_pm", "MP_median", "CBI_median", "pc1", "SP500"):
        a = la[la.series_id == sid].assign(month=lambda d: d["date"].str[:7]).groupby("month")["value"].sum()
        mm = lm[lm.series_id == sid].assign(month=lambda d: d["date"].str[:7]).set_index("month")["value"]
        both = pd.concat([a.rename("a"), mm.rename("m")], axis=1).fillna(0)
        bad = (both["a"] - both["m"]).abs()
        if sid == "SP500":
            sp_months = bad[bad > 1e-6].index.tolist()
        else:
            worst = max(worst, float(bad.max()))
    check(src, "monthly shocks = sum of announcement shocks in the month (pc1, MP_*, CBI_*; tolerance 1e-6)", worst <= 1e-6, f"max |diff| {worst:.2e}")
    info(src, "months where the monthly SP500 surprise is 0 although an announcement-level SP500 move exists (source choice)", ", ".join(sp_months) or "none")
    check(src, "values finite and |value| < 5", df["value"].dropna().abs().lt(5).all(), f"max |value| {df['value'].abs().max():.3f}")
    df["unit"] = "see github.com/marekjarocinski/jkshocks_update_fed (pp / per cent)"
    df["vintage"] = vintage
    df.insert(0, "tracker_ids", "D31")
    df.insert(1, "source", src)
    cols = ["tracker_ids", "source", "table", "series_id", "unit", "date", "time", "value", "flag", "vintage"]
    return df[cols].sort_values(["table", "series_id", "date", "time"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D32  BLS CPI
# --------------------------------------------------------------------------------------
BLS_NAMES = {
    "CUSR0000SA0": ("All items in U.S. city average, all urban consumers, seasonally adjusted", "SA", "CPIAUCSL"),
    "CUSR0000SA0L1E": ("All items less food and energy in U.S. city average, all urban consumers, seasonally adjusted", "SA", "CPILFESL"),
    "CUSR0000SA0E": ("Energy in U.S. city average, all urban consumers, seasonally adjusted", "SA", "CPIENGSL"),
    "CUUR0000SA0": ("All items in U.S. city average, all urban consumers, not seasonally adjusted", "NSA", "CPIAUCNS"),
    "CUUR0000SA0L1E": ("All items less food and energy in U.S. city average, all urban consumers, not seasonally adjusted", "NSA", "CPILFENS"),
}


def clean_bls_cpi(m: dict, src: str = "bls_cpi") -> pd.DataFrame | None:
    files = sorted((RAW / src).glob("cpi_*.json"))
    if not check(src, "raw files present", bool(files) and raw_ok(m, src, "cpi_"), f"{len(files)} window files"):
        return None
    rows, n_raw, annual = [], 0, 0
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        if payload.get("status") != "REQUEST_SUCCEEDED":
            check(src, f"{f.name}: REQUEST_SUCCEEDED", False, payload.get("status"))
            continue
        for s in payload["Results"]["series"]:
            sid = s["seriesID"]
            for obs in s["data"]:
                n_raw += 1
                if not obs["period"].startswith("M") or obs["period"] == "M13":
                    annual += 1
                    continue
                value, flag = to_float(obs["value"])
                codes = ";".join(fn.get("code", "") for fn in obs.get("footnotes", []) if fn.get("code"))
                rows.append({"series_id": sid, "date": f"{obs['year']}-{obs['period'][1:]}-01", "value": value, "flag": flag or codes})
    df = pd.DataFrame(rows)
    check(src, "every raw observation captured (monthly) or counted (M13 annual averages excluded)", len(df) + annual == n_raw,
          f"{n_raw:,} raw -> {len(df):,} monthly rows + {annual} annual averages")
    check(src, "no duplicate (series_id, date) across the 10-year windows", not df.duplicated(["series_id", "date"]).any())
    check(src, "all 5 requested series present", set(df["series_id"]) == set(BLS_NAMES), sorted(set(df["series_id"])))
    for sid, g in df.groupby("series_id"):
        ok, detail = contiguous(g["date"], "MS")
        check(src, f"{sid}: months contiguous", ok, detail)
        pct = g.sort_values("date")["value"].pct_change().abs().dropna()
        lim = 0.25 if sid.endswith("SA0E") else 0.10          # energy CPI moved 18 % in 2008-11
        check(src, f"{sid}: positive and month-on-month change < {lim * 100:.0f} %", g["value"].dropna().gt(0).all() and pct.lt(lim).all(),
              f"{g['date'].min()} .. {g['date'].max()}, max m/m change {pct.max() * 100:.2f} %")
    check(src, "CUSR0000SA0 starts 1947-01 (tracker coverage from 1947)", df.loc[df.series_id == "CUSR0000SA0", "date"].min() == "1947-01-01")
    check(src, "latest month within 2 months of today", (pd.Timestamp.today() - pd.Timestamp(df["date"].max())).days <= 62, df["date"].max())
    sa = df[df.series_id == "CUSR0000SA0"].set_index("date")["value"]
    nsa = df[df.series_id == "CUUR0000SA0"].set_index("date")["value"]
    yr = pd.concat([sa.rename("sa"), nsa.rename("nsa")], axis=1).dropna()
    yr["year"] = yr.index.str[:4]
    ann = yr.groupby("year").agg(sa=("sa", "mean"), nsa=("nsa", "mean"), n=("sa", "size"))
    ann = ann[ann["n"] == 12]
    rel = ((ann["sa"] - ann["nsa"]).abs() / ann["nsa"])
    check(src, "annual mean of SA all-items = annual mean of NSA all-items (within 0.5 %)", rel.lt(0.005).all(), f"{len(ann)} full years, max rel diff {rel.max() * 100:.3f} %")
    df["series_name"] = df["series_id"].map(lambda s: BLS_NAMES[s][0])
    df["seasonal"] = df["series_id"].map(lambda s: BLS_NAMES[s][1])
    df["fred_alias"] = df["series_id"].map(lambda s: BLS_NAMES[s][2])
    df["unit"] = "index 1982-84=100"
    df.insert(0, "tracker_ids", "D32")
    df.insert(1, "source", src)
    info(src, "cells with a footnote code", int((df["flag"] != "").sum()))
    cols = ["tracker_ids", "source", "series_id", "series_name", "seasonal", "fred_alias", "unit", "date", "value", "flag"]
    return df[cols].sort_values(["series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D33  World Bank Global Database of Inflation
# --------------------------------------------------------------------------------------
WB_INDICATORS = {"hcpi": "Headline consumer price index", "fcpi": "Food price index", "ecpi": "Energy price index",
                 "ccpi": "Official core consumer price index", "ppi": "Producer price index", "def": "GDP deflator"}


def wb_period_to_date(p, freq: str):
    v = int(round(float(p)))
    if freq == "m":
        return f"{v // 100:04d}-{v % 100:02d}-01"
    q = v % 10
    return f"{v // 10:04d}-{3 * (q - 1) + 1:02d}-01"


def clean_world_bank_inflation(m: dict, src: str = "world_bank_inflation") -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    path = RAW / src / "Inflation-data.xlsx"
    if not check(src, "raw file present", raw_ok(m, src, "Inflation-data.xlsx") and path.exists(), path.name):
        return None, None
    vintage = vintage_of(m, src, "Inflation-data.xlsx")
    x = pd.ExcelFile(path)
    expected = [f"{i}_{f}" for i in ("hcpi", "fcpi", "ecpi", "ccpi", "ppi") for f in ("m", "q", "a")] + ["def_q", "def_a", "Aggregate"]
    check(src, "all 18 data sheets present", set(expected) <= set(x.sheet_names), sorted(set(expected) - set(x.sheet_names)) or "ok")
    periodic, annual = [], []
    for sheet in expected:
        if sheet not in x.sheet_names:
            continue
        raw = x.parse(sheet, header=None)
        hdr = raw.iloc[0].tolist()
        body = raw.iloc[1:].reset_index(drop=True).copy()
        body.insert(0, "raw_row", range(2, len(body) + 2))          # Excel row number
        period_idx = [i for i, h in enumerate(hdr) if isinstance(h, (int, float, np.integer, np.floating)) and not pd.isna(h)]
        text_idx = [i for i, h in enumerate(hdr) if isinstance(h, str)]
        if not check(src, f"{sheet}: period columns and text columns found", bool(period_idx) and bool(text_idx), f"{len(period_idx)} periods, {len(text_idx)} text cols"):
            continue
        block = body.iloc[:, [i + 1 for i in period_idx]]
        n_raw = numeric_cells(block)
        dims = {}
        for i in text_idx:
            key = re.sub(r"[^a-z0-9]+", "_", str(hdr[i]).strip().lower()).strip("_")
            if key in dims:
                key += "_2"
            dims[key] = body.iloc[:, i + 1]
        tidy = pd.DataFrame(dims)
        tidy.insert(0, "raw_row", body["raw_row"])
        tidy.insert(0, "sheet", sheet)
        vals = block.copy()
        vals.columns = [hdr[i] for i in period_idx]
        long = pd.concat([tidy, vals], axis=1).melt(id_vars=list(tidy.columns), var_name="period", value_name="raw")
        vf = long["raw"].map(to_float)
        long["value"] = [v for v, _ in vf]
        long["flag"] = [f for _, f in vf]
        long = long[long["value"].notna() | long["flag"].ne("")].drop(columns="raw")
        check(src, f"{sheet}: every numeric cell captured", int(long["value"].notna().sum()) == n_raw, f"{n_raw:,} numeric cells -> {int(long['value'].notna().sum()):,} rows")
        check(src, f"{sheet}: no duplicate (raw_row, period)", not long.duplicated(["raw_row", "period"]).any())
        if sheet == "Aggregate":
            long["indicator"] = "aggregate"
            long["freq"] = "a"
            long["year"] = long["period"].map(lambda p: int(round(float(p))))
            long["country_code"] = long.get("series_name", "")
            if "country" not in long.columns:
                long["country"] = ""
            long["series_name"] = long.get("description", long.get("series_name", ""))
            if "inflation_measures" in long.columns:
                long["indicator_type"] = long["inflation_measures"].ffill()
            annual.append(long)
            continue
        ind, freq = sheet.split("_")
        long["indicator"] = ind
        long["freq"] = freq
        if freq == "a":
            long["year"] = long["period"].map(lambda p: int(round(float(p))))
            annual.append(long)
        else:
            long["date"] = long["period"].map(lambda p, f=freq: wb_period_to_date(p, f))
            periodic.append(long)
        dup_cc = long.drop_duplicates(["raw_row"]).groupby("country_code").size()
        dup_cc = dup_cc[dup_cc > 1]
        if len(dup_cc):
            info(src, f"{sheet}: country codes appearing on more than one row (kept apart by raw_row)", ", ".join(dup_cc.index.astype(str)))
    if not periodic or not annual:
        return None, None
    per = pd.concat(periodic, ignore_index=True)
    ann = pd.concat(annual, ignore_index=True)
    # plausibility
    idx = per[per["value"].notna()]
    check(src, "headline CPI index values (hcpi_m, hcpi_q) are positive", idx.loc[idx.sheet.str.startswith("hcpi"), "value"].gt(0).all(),
          f"min {idx.loc[idx.sheet.str.startswith('hcpi'), 'value'].min()}")
    nonpos = idx[idx["value"] <= 0]
    info(src, "non-positive index cells in the other monthly/quarterly sheets (kept as published)",
         ", ".join(f"{k}: {v}" for k, v in nonpos.groupby("sheet").size().items()) or "none")
    check(src, "monthly/quarterly values finite", np.isfinite(idx["value"]).all())
    check(src, "annual inflation rates finite and >= -100 % (hyperinflation episodes reach 1e5 %)", np.isfinite(ann["value"].dropna()).all() and ann["value"].dropna().ge(-100).all(),
          f"min {ann['value'].min()} max {ann['value'].max():.0f}")
    check(src, "monthly headline CPI starts 1970-01 (tracker coverage from 1970)", per.loc[per.sheet == "hcpi_m", "date"].min() == "1970-01-01",
          per.loc[per.sheet == "hcpi_m", "date"].min())
    n_countries = per.loc[per.sheet == "hcpi_m", "country_code"].nunique()
    check(src, "headline monthly CPI covers at least 150 countries (tracker: ~200)", n_countries >= 150, f"{n_countries} country codes")
    info(src, "last monthly period in the release", per["date"].max())
    # cross-check: quarterly index = mean of the three monthly index values (WB builds q from m) for headline CPI
    hm = per[(per.sheet == "hcpi_m") & per.value.notna()].assign(q=lambda d: pd.to_datetime(d["date"]).dt.to_period("Q").astype(str))
    hq = per[(per.sheet == "hcpi_q") & per.value.notna()].assign(q=lambda d: pd.to_datetime(d["date"]).dt.to_period("Q").astype(str))
    mq = hm.groupby(["country_code", "q"]).agg(mean=("value", "mean"), n=("value", "size")).reset_index()
    mq = mq[mq["n"] == 3]
    cmp = mq.merge(hq[["country_code", "q", "value"]], on=["country_code", "q"]).drop_duplicates(["country_code", "q"])
    rel = ((cmp["mean"] - cmp["value"]).abs() / cmp["value"].abs()).replace([np.inf], np.nan).dropna()
    share = float((rel < 0.01).mean()) if len(rel) else 0.0
    off = cmp[rel >= 0.01].groupby("country_code").size().sort_values(ascending=False)
    check(src, "headline CPI quarterly index = mean of monthly index for >= 85 % of country-quarters (within 1 %; the q and m sheets draw on different sources for some countries)",
          share >= 0.85, f"{len(rel):,} country-quarters compared, {share * 100:.1f} % within 1 %; most off: {off.head(6).to_dict()}")
    for d in (per, ann):
        d["unit"] = np.where(d["freq"] == "a", "percent (annual inflation rate)", "index (base per country, see source)")
        d["vintage"] = vintage
        d.insert(0, "tracker_ids", "D33")
        d.insert(1, "source", src)
    pcols = ["tracker_ids", "source", "sheet", "indicator", "freq", "raw_row", "country_code", "imf_country_code", "country",
             "indicator_type", "series_name", "data_source", "note", "unit", "period", "date", "value", "flag", "vintage"]
    acols = ["tracker_ids", "source", "sheet", "indicator", "freq", "raw_row", "country_code", "imf_country_code", "country",
             "indicator_type", "series_name", "aggregation", "sample_country", "data_source", "note", "unit", "year", "value", "flag", "vintage"]
    for d, cols in ((per, pcols), (ann, acols)):
        for c in cols:
            if c not in d.columns:
                d[c] = ""
    per = per[pcols].sort_values(["sheet", "raw_row", "date"]).reset_index(drop=True)
    ann = ann[acols].sort_values(["sheet", "raw_row", "year"]).reset_index(drop=True)
    return per, ann


# --------------------------------------------------------------------------------------
# D34  Baumeister world IP + GECON
# --------------------------------------------------------------------------------------
def clean_baumeister(m: dict, src: str = "baumeister") -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    pw, pv, pg = RAW / src / "OECD_plus6_industrial_production.xlsx", RAW / src / "WIP_vintages.xlsx", RAW / src / "GECON_indicator.xlsx"
    if not check(src, "raw files present", all(p.exists() for p in (pw, pv, pg)) and raw_ok(m, src, "OECD_plus6"), [p.name for p in (pw, pv, pg)]):
        return None, None
    vintage = vintage_of(m, src, "OECD_plus6_industrial_production.xlsx")
    # world IP (current)
    w = pd.read_excel(pw, sheet_name="world_IP", header=None)
    name = str(w.iloc[0, 1]).strip()
    check(src, "world_IP header names the OECD+6 index", "industrial production" in name.lower(), name)
    wb = w.iloc[1:, :2].copy()
    wb.columns = ["date", "value"]
    wb = wb[pd.to_datetime(wb["date"], errors="coerce").notna()]
    n_raw_w = numeric_cells(wb[["value"]])
    wb["date"] = iso(month_start(wb["date"]))
    vf = wb["value"].map(to_float)
    wb["value"] = [v for v, _ in vf]
    wb["flag"] = [f for _, f in vf]
    wb["series_id"] = "WIP"
    wb["series_name"] = name
    wb["unit"] = "index (2021 = 100)"
    check(src, "WIP: every numeric raw cell captured", int(wb["value"].notna().sum()) == n_raw_w, f"{n_raw_w:,} -> {int(wb['value'].notna().sum()):,}")
    ok, detail = contiguous(wb["date"], "MS")
    check(src, "WIP: months contiguous", ok, detail)
    check(src, "WIP: starts 1958-01 (tracker coverage from 1958)", wb["date"].min() == "1958-01-01", wb["date"].min())
    check(src, "WIP: positive", wb["value"].dropna().gt(0).all())
    check(src, "WIP: ends within 5 months of today (series lags a few months)", (pd.Timestamp.today() - pd.Timestamp(wb["date"].max())).days <= 155, wb["date"].max())
    # GECON
    g = pd.read_excel(pg, sheet_name="GECON", header=None)
    ghdr = [str(h).strip() for h in g.iloc[0, 1:5].tolist()]
    check(src, "GECON header has the 4 indicator columns", ghdr[0].startswith("Global Economic Conditions") and len(ghdr) == 4, ghdr)
    gb = g.iloc[1:, :5].copy()
    gb.columns = ["period"] + ghdr
    gb = gb[gb["period"].astype(str).str.match(r"^\d{4}M\d{1,2}$")]
    n_raw_g = numeric_cells(gb[ghdr])
    gb["date"] = pd.to_datetime(gb["period"].astype(str), format="%YM%m").dt.strftime("%Y-%m-%d")
    lg = melt_wide(gb, ["date"], ghdr, var_name="series_name")
    lg["series_id"] = lg["series_name"].map({ghdr[0]: "GECON", ghdr[1]: "GECON_STD", ghdr[2]: "GECON3_SMOOTH", ghdr[3]: "GECON3_STD"})
    lg["unit"] = "index (standardised = z-score)"
    check(src, "GECON: every numeric raw cell captured", int(lg["value"].notna().sum()) == n_raw_g, f"{n_raw_g:,} -> {int(lg['value'].notna().sum()):,}")
    ok, detail = contiguous(gb["date"], "MS")
    check(src, "GECON: months contiguous", ok, detail)
    check(src, "GECON: starts 1973-02", gb["date"].min() == "1973-02-01", gb["date"].min())
    z = lg[(lg.series_id == "GECON_STD") & lg.value.notna()]["value"]
    check(src, "GECON_STD looks standardised (|mean| < 0.2, sd within 0.8-1.2)", abs(z.mean()) < 0.2 and 0.8 < z.std() < 1.2, f"mean {z.mean():.3f} sd {z.std():.3f}")
    cur = pd.concat([wb[["series_id", "series_name", "unit", "date", "value", "flag"]], lg[["series_id", "series_name", "unit", "date", "value", "flag"]]], ignore_index=True)
    check(src, "no duplicate (series_id, date)", not cur.duplicated(["series_id", "date"]).any())
    cur["vintage"] = vintage
    cur.insert(0, "tracker_ids", "D34")
    cur.insert(1, "source", src)
    # vintages
    v = pd.read_excel(pv, sheet_name="WIP", header=None)
    vhdr = v.iloc[0].tolist()
    vint_dates = pd.to_datetime(pd.Series(vhdr[1:]), errors="coerce")
    check(src, "WIP_vintages: header row = index label + vintage dates", str(vhdr[0]).startswith("index") and vint_dates.notna().all(), f"{vhdr[0]!r}, {vint_dates.notna().sum()} vintages")
    vb = v.iloc[1:].copy()
    vb.columns = ["date"] + vint_dates.dt.strftime("%Y-%m-%d").tolist()
    vb = vb[pd.to_datetime(vb["date"], errors="coerce").notna()]
    n_raw_v = numeric_cells(vb.iloc[:, 1:])
    vb["date"] = iso(month_start(vb["date"]))
    lv = melt_wide(vb, ["date"], list(vb.columns[1:]), var_name="vintage")
    lv = lv[lv["value"].notna() | lv["flag"].ne("")]
    check(src, "WIP_vintages: every numeric cell captured", int(lv["value"].notna().sum()) == n_raw_v, f"{n_raw_v:,} -> {int(lv['value'].notna().sum()):,}")
    check(src, "WIP_vintages: no duplicate (vintage, date)", not lv.duplicated(["vintage", "date"]).any())
    check(src, "WIP_vintages: vintages monthly contiguous from 2012-03", contiguous(lv["vintage"], "MS")[0] and lv["vintage"].min() == "2012-03-01",
          f"{lv['vintage'].min()} .. {lv['vintage'].max()}, {lv['vintage'].nunique()} vintages")
    latest = lv[lv.vintage == lv["vintage"].max()].set_index("date")["value"]
    both = pd.concat([latest.rename("latest_vintage"), wb.set_index("date")["value"].rename("current")], axis=1).dropna()
    diff = (both["latest_vintage"] - both["current"]).abs()
    check(src, "latest vintage column = current world IP file on the overlap (tolerance 1e-6)", (diff <= 1e-6).all() and len(both) > 100,
          f"{len(both)} months, max |diff| {diff.max():.2e}")
    lv["series_id"] = "WIP"
    lv["unit"] = str(vhdr[0]).strip()
    lv.insert(0, "tracker_ids", "D34")
    lv.insert(1, "source", src)
    cols = ["tracker_ids", "source", "series_id", "series_name", "unit", "date", "value", "flag", "vintage"]
    vcols = ["tracker_ids", "source", "series_id", "unit", "vintage", "date", "value", "flag"]
    return (cur[cols].sort_values(["series_id", "date"]).reset_index(drop=True),
            lv[vcols].sort_values(["vintage", "date"]).reset_index(drop=True))


# --------------------------------------------------------------------------------------
# D35  Dallas Fed IGREA
# --------------------------------------------------------------------------------------
def clean_dallasfed_igrea(m: dict, src: str = "dallasfed_igrea") -> pd.DataFrame | None:
    path = RAW / src / "igrea.xlsx"
    if not check(src, "raw file present", raw_ok(m, src, "igrea.xlsx") and path.exists(), path.name):
        return None
    vintage = vintage_of(m, src, "igrea.xlsx")
    raw = pd.read_excel(path, header=None)
    body = raw.iloc[1:, :2].copy()
    body.columns = ["source_date", "value"]
    body = body[pd.to_datetime(body["source_date"], errors="coerce").notna()]
    n_raw = numeric_cells(body[["value"]])
    body["source_date"] = pd.to_datetime(body["source_date"])
    body["date"] = iso(month_start(body["source_date"]))
    body["source_date"] = iso(body["source_date"])
    vf = body["value"].map(to_float)
    body["value"] = [v for v, _ in vf]
    body["flag"] = [f for _, f in vf]
    check(src, "every numeric raw cell captured", int(body["value"].notna().sum()) == n_raw, f"{n_raw:,} -> {int(body['value'].notna().sum()):,}")
    check(src, "no duplicate month after normalising the day", not body.duplicated("date").any())
    ok, detail = contiguous(body["date"], "MS")
    check(src, "months contiguous", ok, detail)
    check(src, "starts 1968-01 (tracker coverage from 1968)", body["date"].min() == "1968-01-01", body["date"].min())
    check(src, "ends within 2 months of today", (pd.Timestamp.today() - pd.Timestamp(body["date"].max())).days <= 62, body["date"].max())
    check(src, "values finite and within -250 .. 250", body["value"].dropna().between(-250, 250).all(), f"min {body['value'].min():.1f} max {body['value'].max():.1f}")
    odd = body[~body["source_date"].str.endswith("-01")]
    info(src, "rows whose source date is not the 1st of the month (normalised to month start, original kept in source_date)",
         f"{len(odd)} rows from {odd['source_date'].min() if len(odd) else '-'}")
    body["series_id"] = "IGREA"
    body["series_name"] = "Index of global real economic activity (Kilian 2009, Dallas Fed update)"
    body["unit"] = "index (percent deviation from trend)"
    body["vintage"] = vintage
    body.insert(0, "tracker_ids", "D35")
    body.insert(1, "source", src)
    cols = ["tracker_ids", "source", "series_id", "series_name", "unit", "date", "source_date", "value", "flag", "vintage"]
    return body[cols].sort_values("date").reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D36  policyuncertainty.com EPU
# --------------------------------------------------------------------------------------
def epu_ym_table(raw: pd.DataFrame, table: str, year_col="Year", month_col="Month") -> tuple[pd.DataFrame, int]:
    """Year/Month wide sheet (header row 0, text footer rows) -> long."""
    hdr = [str(h).strip() for h in raw.iloc[0].tolist()]
    body = raw.iloc[1:].copy()
    body.columns = hdr
    body = body[pd.to_numeric(body[year_col], errors="coerce").notna() & pd.to_numeric(body[month_col], errors="coerce").notna()]
    vcols = [c for c in hdr if c not in (year_col, month_col) and c != "nan"]
    n_raw = numeric_cells(body[vcols])
    body["date"] = iso(pd.to_datetime(dict(year=body[year_col].astype(int), month=body[month_col].astype(int), day=1)))
    long = melt_wide(body, ["date"], vcols)
    long["table"] = table
    return long, n_raw


def clean_epu(m: dict, src: str = "epu") -> pd.DataFrame | None:
    folder = RAW / src
    names = ["Global_Policy_Uncertainty_Data.xlsx", "All_Country_Data.xlsx", "US_Policy_Uncertainty_Data.xlsx",
             "All_Daily_Policy_Data.csv", "China_Policy_Uncertainty_Data.xlsx", "China_Mainland_Paper_EPU.xlsx"]
    if not check(src, "raw files present", all((folder / n).exists() and raw_ok(m, src, n) for n in names), names):
        return None
    parts, n_raw = [], 0
    t, n = epu_ym_table(pd.read_excel(folder / names[0], header=None), "global")
    parts.append(t); n_raw += n
    t, n = epu_ym_table(pd.read_excel(folder / names[1], sheet_name="EPU", header=None), "all_country")
    parts.append(t); n_raw += n
    xu = pd.ExcelFile(folder / names[2])
    t, n = epu_ym_table(xu.parse("Main News Index", header=None), "us_news")
    parts.append(t); n_raw += n
    t, n = epu_ym_table(xu.parse("Legacy Three Component EPU", header=None), "us_legacy")
    parts.append(t); n_raw += n
    t, n = epu_ym_table(pd.read_excel(folder / names[4], header=None), "china_scmp", year_col="year", month_col="month")
    parts.append(t); n_raw += n
    xc = pd.ExcelFile(folder / names[5])
    for sheet in xc.sheet_names:
        raw = xc.parse(sheet, header=None).iloc[:, :3]
        t, n = epu_ym_table(raw, "china_mainland", year_col="year", month_col="month")
        parts.append(t); n_raw += n
    d = pd.read_csv(folder / names[3])
    check(src, "daily file columns day, month, year, daily_policy_index", list(d.columns) == ["day", "month", "year", "daily_policy_index"], list(d.columns))
    n_raw += numeric_cells(d[["daily_policy_index"]])
    d["date"] = iso(pd.to_datetime(dict(year=d["year"], month=d["month"], day=d["day"])))
    ld = melt_wide(d, ["date"], ["daily_policy_index"])
    ld["table"] = "us_daily"
    parts.append(ld)
    df = pd.concat(parts, ignore_index=True)
    df["series_id"] = df["series_id"].astype(str).str.strip()
    check(src, "every numeric raw cell captured", int(df["value"].notna().sum()) == n_raw, f"{n_raw:,} -> {int(df['value'].notna().sum()):,}")
    check(src, "no duplicate (table, series_id, date)", not df.duplicated(["table", "series_id", "date"]).any())
    for (table, sid), g in df[df.table != "us_daily"].groupby(["table", "series_id"]):
        ok, detail = contiguous(g["date"], "MS")
        check(src, f"{table}/{sid}: months contiguous", ok, detail)
    ok, detail = contiguous(ld["date"], "D")
    check(src, "us_daily: every calendar day present", ok, detail)
    check(src, "us_daily: starts 1985-01-01", ld["date"].min() == "1985-01-01", ld["date"].min())
    check(src, "values non-negative and finite", df["value"].dropna().ge(0).all() and np.isfinite(df["value"].dropna()).all(), f"min {df['value'].min()} max {df['value'].max():.1f}")
    check(src, "global GEPU starts 1997-01 (tracker coverage 1997)", df.loc[(df.table == "global") & (df.series_id == "GEPU_current"), "date"].min() == "1997-01-01")
    check(src, "US legacy index starts 1985-01 (tracker coverage 1985)", df.loc[(df.table == "us_legacy"), "date"].min() == "1985-01-01")
    check(src, "latest monthly observation within 3 months of today", (pd.Timestamp.today() - pd.Timestamp(df.loc[df.table == "us_news", "date"].max())).days <= 93,
          df.loc[df.table == "us_news", "date"].max())

    def overlap(ta, sa, tb, sb, name, tol=1e-6, min_share=1.0):
        a = df[(df.table == ta) & (df.series_id == sa)].dropna(subset=["value"]).set_index("date")["value"]
        b = df[(df.table == tb) & (df.series_id == sb)].dropna(subset=["value"]).set_index("date")["value"]
        both = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        diff = (both["a"] - both["b"]).abs()
        share = float((diff <= tol).mean()) if len(both) else 0.0
        off = diff[diff > tol].index.tolist()
        check(src, name, len(both) > 0 and share >= min_share,
              f"{len(both)} months overlap, {share * 100:.1f} % identical, max |diff| {diff.max() if len(diff) else float('nan'):.2e}"
              + (f"; differing months: {off[:6]}" if off else ""))

    overlap("all_country", "GEPU_current", "global", "GEPU_current", "all_country GEPU_current = global file GEPU_current")
    overlap("all_country", "GEPU_ppp", "global", "GEPU_ppp", "all_country GEPU_ppp = global file GEPU_ppp")
    overlap("all_country", "US", "us_legacy", "News_Based_Policy_Uncert_Index",
            "all_country US = US legacy news-based index for >= 99 % of months (the all-country file is an older vintage for the last month)", min_share=0.99)
    overlap("all_country", "Mainland China", "china_mainland", "EPU", "all_country 'Mainland China' = China mainland-paper file")
    a = df[(df.table == "all_country") & (df.series_id == "SCMP China")].dropna(subset=["value"]).set_index("date")["value"]
    b = df[(df.table == "china_scmp")].dropna(subset=["value"]).set_index("date")["value"]
    both = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    info(src, "all_country 'SCMP China' vs the China (SCMP) file: differently normalised series (not an identity)",
         f"{len(both)} months overlap, correlation {both['a'].corr(both['b']):.3f}, mean ratio {(both['a'] / both['b']).mean():.3f}")
    df["unit"] = "index (mean 100 over the base period of each series)"
    df.insert(0, "tracker_ids", "D36")
    df.insert(1, "source", src)
    cols = ["tracker_ids", "source", "table", "series_id", "unit", "date", "value", "flag"]
    return df[cols].sort_values(["table", "series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D36  World Uncertainty Index
# --------------------------------------------------------------------------------------
WUI_TABLE_NAMES = {   # short labels for the T0 descriptions (full text: CHECKS.md, wui INFO)
    "T1": "WUI global, income-group and regional aggregates (GDP-weighted / simple averages)",
    "T2": "WUI by country",
    "T3": "count of the word 'uncertainty' in EIU country reports",
    "T4": "total number of words in EIU country reports",
    "T5": "total number of pages in EIU country reports",
    "T6": "WUI 3-quarter weighted moving average by country (authors' preferred country measure)",
    "T8": "World Trade Uncertainty index: aggregates and by country",
}
WUI_UNITS = {
    "T1": "share of words x 1,000,000", "T2": "share of words x 1,000", "T3": "count", "T4": "count", "T5": "count",
    "T6": "share of words x 1,000 (3-quarter weighted MA)", "T8": "share of words x 100,000",
}


def wui_quarter(s: pd.Series) -> pd.Series:
    q = s.astype(str).str.strip().str.lower().str.extract(r"^(\d{4})q([1-4])$")
    return q[0] + "-" + ((q[1].astype(float) - 1) * 3 + 1).map(lambda v: f"{int(v):02d}" if pd.notna(v) else "") + "-01"


def clean_wui(m: dict, src: str = "wui") -> pd.DataFrame | None:
    path = RAW / src / "WUI_Data.xlsx"
    if not check(src, "raw file present", raw_ok(m, src, "WUI_Data.xlsx") and path.exists(), path.name):
        return None
    x = pd.ExcelFile(path)
    t0 = x.parse("T0", header=None)
    desc = {}
    for _, r in t0.iterrows():
        if isinstance(r[0], str) and re.match(r"^[TF]\d+$", r[0].strip()):
            desc[r[0].strip()] = re.sub(r"\s+", " ", str(r[1])).strip()
    info(src, "tab descriptions (T0)", " | ".join(f"{k}: {v}" for k, v in desc.items()))
    t7 = x.parse("T7", header=0)
    meta = t7.set_index("iso_code")
    quarterly = [s for s in ("T1", "T2", "T3", "T4", "T5", "T6", "T8") if s in x.sheet_names]
    check(src, "quarterly tables T1-T6, T8 and country table T7 present", len(quarterly) == 7 and "T7" in x.sheet_names, x.sheet_names)
    parts, n_raw = [], 0
    for sheet in quarterly:
        raw = x.parse(sheet, header=None)
        hdr = [str(h).strip() for h in raw.iloc[0].tolist()]
        body = raw.iloc[1:].copy()
        body.columns = hdr
        ycol = hdr[0]
        body["date"] = wui_quarter(body[ycol])
        body = body[body["date"].str.match(r"^\d{4}-\d{2}-01$")]
        vcols = [c for c in hdr[1:] if c != "nan"]
        n_raw += numeric_cells(body[vcols])
        long = melt_wide(body, ["date"], vcols)
        long = long[long["value"].notna() | long["flag"].ne("")]
        long["table"] = sheet
        parts.append(long)
    df = pd.concat(parts, ignore_index=True)
    df["series_id"] = df["series_id"].astype(str).str.strip()
    df["table_name"] = df["table"].map(WUI_TABLE_NAMES).fillna("")      # full T0 text is in CHECKS.md (INFO)
    df["country_code"] = np.where(df["series_id"].isin(meta.index), df["series_id"], "")
    df["country_name"] = df["country_code"].map(meta["country_name"]).fillna("")
    df["region"] = df["country_code"].map(meta["region"]).fillna("")
    check(src, "every numeric raw cell captured", int(df["value"].notna().sum()) == n_raw, f"{n_raw:,} -> {int(df['value'].notna().sum()):,}")
    check(src, "no duplicate (table, series_id, date)", not df.duplicated(["table", "series_id", "date"]).any())
    for sheet in quarterly:
        ok, detail = contiguous(df.loc[df.table == sheet, "date"], "QS")
        check(src, f"{sheet}: quarters contiguous", ok, detail)
    check(src, "T1 (regions) starts 1990Q1", df.loc[df.table == "T1", "date"].min() == "1990-01-01", df.loc[df.table == "T1", "date"].min())
    check(src, "latest quarter within 6 months of today", (pd.Timestamp.today() - pd.Timestamp(df["date"].max())).days <= 190, df["date"].max())
    check(src, "country columns in T2 all resolve to T7 country codes", df.loc[df.table == "T2", "country_code"].ne("").all(),
          sorted(set(df.loc[(df.table == "T2") & (df.country_code == ""), "series_id"])))
    check(src, "values non-negative and finite", df["value"].dropna().ge(0).all() and np.isfinite(df["value"].dropna()).all(), f"min {df['value'].min()} max {df['value'].max():.1f}")
    # identities: T2 (WUI) = T3 (count of 'uncertain') / T4 (total words) * 1000; F1 = T1 GDP-weighted global
    key = ["series_id", "date"]
    t2 = df[df.table == "T2"].set_index(key)["value"]
    t3 = df[df.table == "T3"].set_index(key)["value"]
    t4 = df[df.table == "T4"].set_index(key)["value"]
    both = pd.concat([t2.rename("wui"), t3.rename("cnt"), t4.rename("tot")], axis=1).dropna()
    both = both[both["tot"] > 0]
    diff = (both["wui"] - both["cnt"] / both["tot"] * 1000).abs()
    check(src, "T2 WUI = T3 count / T4 total words x 1000 (tolerance 1e-3)", len(both) > 0 and (diff <= 1e-3).all(), f"{len(both):,} cells, max |diff| {diff.max():.2e}")
    if "F1" in x.sheet_names:
        f1 = x.parse("F1", header=None)
        f1 = f1[f1[0].astype(str).str.match(r"^\d{4}q[1-4]$", case=False)]
        f1s = pd.Series(pd.to_numeric(f1[2], errors="coerce").values, index=wui_quarter(f1[0]).values)
        g = df[(df.table == "T1") & (df.series_id.str.contains("GDP weighted"))].set_index("date")["value"]
        both = pd.concat([f1s.rename("f1"), g.rename("t1")], axis=1).dropna()
        d2 = (both["f1"] - both["t1"]).abs()
        check(src, "F1 chart series = T1 'Global (GDP weighted average)' (tolerance 1e-3)", len(both) > 0 and (d2 <= 1e-3).all(), f"{len(both)} quarters, max |diff| {d2.max():.2e}")
    df["unit"] = df["table"].map(WUI_UNITS).fillna("index")
    df.insert(0, "tracker_ids", "D36")
    df.insert(1, "source", src)
    cols = ["tracker_ids", "source", "table", "table_name", "series_id", "country_code", "country_name", "region", "unit", "date", "value", "flag"]
    return df[cols].sort_values(["table", "series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# optional FRED cross-checks
# --------------------------------------------------------------------------------------
def fred_cross_checks(m: dict, outputs: dict[str, pd.DataFrame]) -> None:
    src = "fred"
    files = [f for f in m["sources"].get("fred", {}).get("files", []) if f.get("file", "").endswith(".json") and "_meta" not in f["file"]]
    if not files:
        info(src, "FRED cross-checks skipped", m["sources"].get("fred", {}).get("note", "no FRED files"))
        return
    pairs = {"DFF": ("fed_h15.csv", "RIFSPFF_N.D"), "FEDFUNDS": ("fed_h15.csv", "RIFSPFF_N.M"), "CPIAUCSL": ("bls_cpi.csv", "CUSR0000SA0"),
             "CPILFESL": ("bls_cpi.csv", "CUSR0000SA0L1E"), "IGREA": ("dallasfed_igrea.csv", "IGREA")}
    for f in files:
        sid = Path(f["file"]).stem
        p = RAW / f["file"]
        if sid not in pairs or not p.exists() or pairs[sid][0] not in outputs:
            continue
        obs = pd.DataFrame(json.loads(p.read_text(encoding="utf-8"))["observations"])
        obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
        fred = obs.dropna(subset=["value"]).set_index("date")["value"]
        ours = outputs[pairs[sid][0]]
        ours = ours[ours.series_id == pairs[sid][1]].dropna(subset=["value"]).set_index("date")["value"]
        both = pd.concat([fred.rename("fred"), ours.rename("ours")], axis=1).dropna()
        diff = (both["fred"] - both["ours"]).abs()
        tol = 0.011 if sid in ("DFF", "FEDFUNDS") else 0.01
        check(src, f"FRED {sid} = {pairs[sid][0]} {pairs[sid][1]} (tolerance {tol})", len(both) > 0 and (diff <= tol).all(),
              f"{len(both):,} dates overlap, max |diff| {diff.max() if len(diff) else float('nan'):.4f}")


# --------------------------------------------------------------------------------------
# cross-source checks
# --------------------------------------------------------------------------------------
def cross_checks(outputs: dict[str, pd.DataFrame]) -> None:
    src = "cross-source"
    if "fed_h15.csv" in outputs and "nyfed_effr.csv" in outputs:
        h = outputs["fed_h15.csv"]
        h = h[h.series_id == "RIFSPFF_N.B"].dropna(subset=["value"]).set_index("date")["value"]
        n = outputs["nyfed_effr.csv"]
        n = n[n.series_id == "EFFR_RATE"].dropna(subset=["value"]).set_index("date")["value"]
        both = pd.concat([h.rename("h15"), n.rename("nyfed")], axis=1).dropna()
        diff = (both["h15"] - both["nyfed"]).abs()
        check(src, "H.15 business-daily EFFR = NY Fed EFFR on every overlapping day (tolerance 0.005)", len(both) > 1000 and (diff <= 0.005).all(),
              f"{len(both):,} days overlap, max |diff| {diff.max():.4f}")
    if "fed_h15.csv" in outputs and "wu_xia.csv" in outputs:
        h = outputs["fed_h15.csv"]
        h = h[h.series_id == "RIFSPFF_N.D"].dropna(subset=["value"]).set_index("date")["value"]
        h.index = pd.to_datetime(h.index)
        eom = h.groupby(h.index.to_period("M")).last()                      # the Wu-Xia file carries the end-of-month EFFR
        eom.index = eom.index.to_timestamp().strftime("%Y-%m-%d")
        w = outputs["wu_xia.csv"]
        w = w[w.series_id == "EFFR"].dropna(subset=["value"]).set_index("date")["value"]
        both = pd.concat([eom.rename("h15_eom"), w.rename("wuxia")], axis=1).dropna()
        diff = (both["h15_eom"] - both["wuxia"]).abs()
        check(src, "Wu-Xia EFFR column = end-of-month H.15 daily EFFR on every month (tolerance 0.05 pp)",
              len(both) > 700 and (diff <= 0.05).all(), f"{len(both)} months overlap, max |diff| {diff.max():.3f}")
    if "bls_cpi.csv" in outputs and "world_bank_inflation.csv" in outputs:
        b = outputs["bls_cpi.csv"]
        b = b[b.series_id == "CUUR0000SA0"].dropna(subset=["value"]).set_index("date")["value"]
        w = outputs["world_bank_inflation.csv"]
        w = w[(w.sheet == "hcpi_m") & (w.country_code == "USA")].dropna(subset=["value"]).set_index("date")["value"]
        both = pd.concat([b.rename("bls"), w.rename("wb")], axis=1).dropna()
        if len(both):
            # the WB index is rebased: compare 12-month inflation rates instead of levels
            infl = both.pct_change(12).dropna()
            diff = (infl["bls"] - infl["wb"]).abs()
            recent = diff[diff.index >= "2000-01-01"]
            # Finding, not a gate: the World Bank's monthly USA headline series (data_source OECDstat) does not track
            # CPI-U (e.g. it barely moves through the 2008 H2 price fall), so it is NOT a substitute for bls_cpi.csv.
            info(src, "World Bank USA monthly headline CPI vs BLS CPI-U NSA: 12-month inflation differs (use bls_cpi.csv for the US)",
                 f"since 2000: {len(recent)} months, max |diff| {recent.max() * 100:.2f} pp, median {recent.median() * 100:.2f} pp, "
                 f"{float((recent <= 0.001).mean()) * 100:.0f} % within 0.1 pp; levels correlate {both['bls'].corr(both['wb']):.4f}")
    if "baumeister_wip.csv" in outputs and "dallasfed_igrea.csv" in outputs:
        w = outputs["baumeister_wip.csv"]
        w = w[w.series_id == "WIP"].dropna(subset=["value"]).set_index("date")["value"]
        k = outputs["dallasfed_igrea.csv"].dropna(subset=["value"]).set_index("date")["value"]
        both = pd.concat([np.log(w).diff(12).rename("wip_yoy"), k.rename("igrea")], axis=1).dropna()
        corr = both.corr().iloc[0, 1]
        info(src, "correlation of world IP 12-month log growth with IGREA (both are demand proxies; positive expected)", f"{corr:.2f} over {len(both)} months")


# --------------------------------------------------------------------------------------
# catalog, tracker status, CHECKS.md
# --------------------------------------------------------------------------------------
def catalog_rows(name: str, df: pd.DataFrame, keys: list[str], datecol: str = "date") -> list[dict]:
    out = []
    for key, g in df.groupby(keys, dropna=False, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        out.append({"file": name, "tracker_ids": ";".join(sorted(set(g["tracker_ids"]))), "series_key": " | ".join(map(str, key)),
                    "first": g[datecol].min(), "last": g[datecol].max(), "n_obs": int(g["value"].notna().sum()),
                    "n_missing": int(g["value"].isna().sum())})
    return out


CATALOG_KEYS = {
    "fed_h15.csv": ["series_id"], "nyfed_effr.csv": ["series_id"], "wu_xia.csv": ["series_id"],
    "bauer_swanson.csv": ["table", "series_id"], "jarocinski_karadi.csv": ["table", "series_id"], "bls_cpi.csv": ["series_id"],
    "world_bank_inflation.csv": ["sheet", "country_code"], "world_bank_inflation_annual.csv": ["sheet", "country_code"],
    "baumeister_wip.csv": ["series_id"], "baumeister_wip_vintages.csv": ["vintage"], "dallasfed_igrea.csv": ["series_id"],
    "epu.csv": ["table", "series_id"], "wui.csv": ["table", "series_id"],
}


def tracker_status(outputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    have = set(outputs)
    loc = "data/macro_controls"
    rows = [
        ("D30", "Cleaned" if "fed_h15.csv" in have else "Downloaded", TODAY,
         f"{loc}/clean/fed_h15.csv (RIFSPFF_N.D = DFF, RIFSPFF_N.M = FEDFUNDS, from the Board's H.15 package; FRED blocked for scripts); "
         f"{loc}/clean/nyfed_effr.csv (cross-check); {loc}/clean/wu_xia.csv (shadow rate, ends 2022-02); raw {loc}/raw/fed_h15/, nyfed_effr/, wu_xia/"),
        ("D31", "Cleaned" if "bauer_swanson.csv" in have and "jarocinski_karadi.csv" in have else "Downloaded", TODAY,
         f"{loc}/clean/bauer_swanson.csv (FOMC surprises 1988-02..2019-12 + monthly SVAR data); {loc}/clean/jarocinski_karadi.csv (updated monthly); "
         f"raw {loc}/raw/bauer_swanson/, jarocinski_karadi/ (+ vintages/)"),
        ("D32", "Cleaned" if "bls_cpi.csv" in have else "Downloaded", TODAY,
         f"{loc}/clean/bls_cpi.csv (CUSR0000SA0 = CPIAUCSL, CUSR0000SA0L1E = CPILFESL, + NSA and energy; BLS public API v1, no key); raw {loc}/raw/bls_cpi/"),
        ("D33", "Cleaned" if "world_bank_inflation.csv" in have else "Downloaded", TODAY,
         f"{loc}/clean/world_bank_inflation.csv (monthly + quarterly indices) and world_bank_inflation_annual.csv (annual rates + Aggregate); "
         f"raw {loc}/raw/world_bank_inflation/Inflation-data.xlsx (+ vintages/)"),
        ("D34", "Cleaned" if "baumeister_wip.csv" in have else "Downloaded", TODAY,
         f"{loc}/clean/baumeister_wip.csv (WIP 1958-01.., GECON 1973-02..) and baumeister_wip_vintages.csv; raw {loc}/raw/baumeister/ (+ vintages/)"),
        ("D35", "Cleaned" if "dallasfed_igrea.csv" in have else "Downloaded", TODAY,
         f"{loc}/clean/dallasfed_igrea.csv (Dallas Fed igrea.xlsx = FRED IGREA); raw {loc}/raw/dallasfed_igrea/ (+ vintages/)"),
        ("D36", "Cleaned" if "epu.csv" in have else "Downloaded", TODAY,
         f"{loc}/clean/epu.csv (global, all-country, US news/legacy/daily, China SCMP + mainland) and wui.csv (World Uncertainty Index); raw {loc}/raw/epu/, wui/"),
    ]
    return pd.DataFrame(rows, columns=["ID", "Status", "Date retrieved", "Saved file / location"])


def write_checks_md(outputs: dict[str, pd.DataFrame], failed: bool) -> None:
    n = {s: sum(1 for c in CHECKS if c[2] == s) for s in ("FAIL", "WARN", "PASS", "INFO")}
    lines = [f"# {CATEGORY} clean-up checks", "", f"Run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ",
             f"Result: **{'FAILED - no data files written' if failed else 'ALL PASSED' + (' (with WARNs on coverage)' if n['WARN'] else '')}**  ",
             f"FAIL {n['FAIL']} · WARN {n['WARN']} · PASS {n['PASS']} · INFO {n['INFO']}", ""]
    bad = [c for c in CHECKS if c[2] in ("WARN", "FAIL")]
    if bad:
        lines += ["## Failures and warnings", ""] + [f"- **{s} [{src}] {name}** — {d}" for src, name, s, d in bad] + [""]
    lines += ["## Outputs", "", "| file | rows | columns |", "|---|---:|---|"]
    lines += [f"| {k} | {len(v):,} | {', '.join(v.columns)} |" for k, v in outputs.items()] + [""]
    lines += ["## Checks", ""]
    for src in dict.fromkeys(c[0] for c in CHECKS):
        lines += [f"### {src}", "", "| status | check | detail |", "|---|---|---|"]
        for s0, name, s, d in CHECKS:
            if s0 == src:
                d = d.replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {s} | {name} | {d} |")
        lines.append("")
    CLEAN.mkdir(exist_ok=True)
    (CLEAN / "CHECKS.md").write_text("\n".join(lines), encoding="utf-8")


CLEANERS = {
    "fed_h15": clean_fed_h15,
    "nyfed_effr": clean_nyfed_effr,
    "wu_xia": clean_wu_xia,
    "bauer_swanson": clean_bauer_swanson,
    "jarocinski_karadi": clean_jarocinski_karadi,
    "bls_cpi": clean_bls_cpi,
    "world_bank_inflation": clean_world_bank_inflation,
    "baumeister": clean_baumeister,
    "dallasfed_igrea": clean_dallasfed_igrea,
    "epu": clean_epu,
    "wui": clean_wui,
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=sorted(CLEANERS))
    a = ap.parse_args(argv)
    m = manifest()
    outputs: dict[str, pd.DataFrame] = {}
    for name, fn in CLEANERS.items():
        if a.only and name not in a.only:
            continue
        print(f"[{name}] ...", flush=True)
        res = fn(m)
        if name == "world_bank_inflation":
            per, ann = res
            if per is not None:
                outputs["world_bank_inflation.csv"] = per
            if ann is not None:
                outputs["world_bank_inflation_annual.csv"] = ann
        elif name == "baumeister":
            cur, vint = res
            if cur is not None:
                outputs["baumeister_wip.csv"] = cur
            if vint is not None:
                outputs["baumeister_wip_vintages.csv"] = vint
        elif res is not None:
            outputs[f"{name}.csv"] = res
    cross_checks(outputs)
    fred_cross_checks(m, outputs)
    failed = any(c[2] == "FAIL" for c in CHECKS)
    write_checks_md(outputs, failed)
    if failed:
        print("CHECKS FAILED - nothing written; see clean/CHECKS.md", file=sys.stderr)
        for src, name, s, d in CHECKS:
            if s == "FAIL":
                print(f"  FAIL [{src}] {name}: {d}", file=sys.stderr)
        return 1
    catalog = []
    for name, df in outputs.items():
        df.to_csv(CLEAN / name, index=False)
        catalog += catalog_rows(name, df, CATALOG_KEYS.get(name, ["source"]), "year" if "year" in df.columns else "date")
        print(f"wrote clean/{name}: {len(df):,} rows")
    pd.DataFrame(catalog).to_csv(CLEAN / "series_catalog.csv", index=False)
    tracker_status(outputs).to_csv(CLEAN / "tracker_status.csv", index=False)
    for src, name, s, d in CHECKS:
        if s == "WARN":
            print(f"  WARN [{src}] {name}: {d}")
    print("all checks passed; see clean/CHECKS.md and clean/tracker_status.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
