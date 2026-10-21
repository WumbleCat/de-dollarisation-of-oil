"""Clean the raw Currency-markets downloads (tracker rows D43-D50) in ./currency_markets/raw into tidy CSVs in
./currency_markets/clean, and run sanity checks that must all pass before anything is written.

Outputs (data/currency_markets/clean/)
  imf_invoicing_currency.csv      D43  Boz et al. invoicing shares: country x year x flow x currency, % (1990-2019)
  safe_crossborder_by_currency.csv D44 SAFE cross-border receipts/payments of non-banking sectors, monthly + annual,
                                       by transaction and by currency (RMB / USD / HKD / EUR / JPY / other), 2010-01 ->
  safe_rmb_share.csv              D44  derived: RMB share (%) of China's cross-border receipts, payments and total
  imf_cofer.csv                   D45  COFER: world / advanced / EMDE reserves by currency, shares (%) and USD, Q + A
  swift_rmb_tracker.csv           D46  only if a hand-collected raw/swift_rmb_tracker/swift_rmb_tracker.csv exists
  cips_volumes.csv                D47  CIPS transactions and value (bn CNY), monthly current year + annual history
  bis_fx_turnover.csv             D48  BIS Triennial: global FX turnover (daily avg, USD mn) by instrument x
                                       counterparty x currency pair, net-net basis, survey years 1989-2025
  bis_fx_turnover_by_currency.csv D48  derived: turnover and share (% of 200) per currency, all instruments
  tic_major_foreign_holders.csv   D49  TIC Major Foreign Holders of Treasury Securities, monthly, USD bn, 2000-02 ->
  imf_irfcl_gold_reserves.csv     D50  IMF IRFCL monetary gold: troy ounces, tonnes and USD, monthly, ~90 reporters
  wb_gold_reserves_annual.csv     D50  World Bank WDI: total reserves, reserves ex gold and the implied gold value, annual
  series_catalog.csv                   one row per series in every file: coverage and observation counts
  tracker_status.csv                   suggested Status / Date retrieved / Saved file values for the tracker
  CHECKS.md                            every check with PASS / FAIL / WARN / INFO and details

Any FAIL aborts the write of the data files (CHECKS.md is still written) and exits 1.
Run `python data/currency_markets/download_currency_markets.py` first.
"""
import argparse
import csv
import io
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
CLEAN = HERE / "clean"
TODAY = date.today().isoformat()
TROY_OZ_PER_TONNE = 32150.7466  # 1 tonne = 1e6 g / 31.1034768 g per troy ounce

# --------------------------------------------------------------------------------------
# check registry
# --------------------------------------------------------------------------------------
CHECKS = []  # (source, name, status, detail)


def check(source, name, ok, detail=""):
    CHECKS.append((source, name, "PASS" if ok else "FAIL", str(detail)))
    return bool(ok)


def warn(source, name, ok, detail=""):
    """Failure is reported as WARN and does not block writing: reserved for cross-source comparisons where the two
    sources are known to differ in definition or vintage."""
    CHECKS.append((source, name, "PASS" if ok else "WARN", str(detail)))
    return bool(ok)


def info(source, name, detail=""):
    CHECKS.append((source, name, "INFO", str(detail)))


def close(a, b, atol=0.0, rtol=0.0):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.abs(a - b) <= atol + rtol * np.abs(b)


def to_num(v):
    if v is None:
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "n.a.", "n/a", "NaN", "nan", "..", "*"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def contiguous_months(periods):
    """periods: iterable of 'YYYY-MM' -> (ok, missing list)."""
    p = sorted(set(periods))
    if not p:
        return False, ["<empty>"]
    full = pd.period_range(p[0], p[-1], freq="M").strftime("%Y-%m")
    missing = sorted(set(full) - set(p))
    return not missing, missing


def sdmx_codelists(structure_json):
    """{codelist id: {code: name}} from an SDMX-JSON 2.0 structure message."""
    out = {}
    for cl in structure_json["data"].get("codelists", []):
        out[cl["id"]] = {c["id"]: c.get("name", c["id"]) for c in cl.get("codes", [])}
    return out


def sdmx_data_to_long(data_json):
    """SDMX-JSON 2.0 data message -> long DataFrame with one column per series dimension, TIME_PERIOD, value, plus
    observation-level attributes (derivation / status) when present."""
    st = data_json["data"]["structures"][0]
    dims = st["dimensions"]["series"]
    dim_vals = [[v["id"] for v in d["values"]] for d in dims]
    dim_ids = [d["id"] for d in dims]
    obs_vals = [v.get("value", v.get("id")) for v in st["dimensions"]["observation"][0]["values"]]
    obs_attrs = st.get("attributes", {}).get("observation", [])
    rows = []
    for ds in data_json["data"]["dataSets"]:
        for key, ser in ds.get("series", {}).items():
            idx = [int(i) for i in key.split(":")]
            base = {dim_ids[k]: dim_vals[k][i] for k, i in enumerate(idx)}
            for oi, obs in ser.get("observations", {}).items():
                row = dict(base)
                row["TIME_PERIOD"] = obs_vals[int(oi)]
                row["value"] = to_num(obs[0])
                for a, (attr) in enumerate(obs_attrs):
                    ai = obs[a + 1] if a + 1 < len(obs) else None
                    vals = attr.get("values", [])
                    row[attr["id"]] = vals[ai]["id"] if isinstance(ai, int) and ai < len(vals) else None
                rows.append(row)
    return pd.DataFrame(rows)


def period_to_date(p):
    """'2024' | '2024-Q3' | '2024-M09' | '2024-09' -> first day of the period."""
    p = str(p)
    if re.fullmatch(r"\d{4}", p):
        return pd.Timestamp(int(p), 1, 1)
    m = re.fullmatch(r"(\d{4})-Q(\d)", p)
    if m:
        return pd.Timestamp(int(m.group(1)), 3 * (int(m.group(2)) - 1) + 1, 1)
    m = re.fullmatch(r"(\d{4})-M?(\d{1,2})", p)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
    raise ValueError(p)


def norm_period(p):
    p = str(p)
    m = re.fullmatch(r"(\d{4})-M(\d{2})", p)
    return f"{m.group(1)}-{m.group(2)}" if m else p


# --------------------------------------------------------------------------------------
# D43  IMF invoicing currency (Boz et al. 2022)
# --------------------------------------------------------------------------------------
def clean_invoicing():
    src = "D43 invoicing"
    path = RAW / "imf_invoicing" / "all_countries_update.dta"
    if not path.exists():
        check(src, "raw file present", False, f"{path} missing")
        return None
    raw = pd.read_stata(path)
    share_cols = [c for c in raw.columns if c.endswith(("Export", "Import"))]
    long = raw.melt(id_vars=["country", "ISO3C", "imfcode", "year"], value_vars=share_cols,
                    var_name="var", value_name="share_pct")
    long["flow"] = np.where(long["var"].str.endswith("Export"), "Export", "Import")
    long["currency"] = long["var"].str.replace(r"(Export|Import)$", "", regex=True)
    long = long.dropna(subset=["share_pct"]).copy()
    long["year"] = long["year"].astype(int)
    out = long.rename(columns={"ISO3C": "iso3", "imfcode": "imf_code"})[
        ["country", "iso3", "imf_code", "year", "flow", "currency", "share_pct"]].sort_values(
        ["iso3", "year", "flow", "currency"]).reset_index(drop=True)
    out["imf_code"] = out["imf_code"].astype(int)
    # checks
    n_raw = int(raw[share_cols].notna().sum().sum())
    check(src, "every non-missing share in the .dta lands in the output", n_raw == len(out), f"{n_raw} vs {len(out)}")
    reported = out[~out.currency.isin(["Other", "Other_Excl_USDEUR"])]
    check(src, "reported currency shares (USD, EUR, home, unclassified) within 0-100", reported["share_pct"].between(-1e-6, 100 + 1e-6).all(),
          f"min {reported.share_pct.min():.3f} max {reported.share_pct.max():.3f}")
    resid = out[out.currency.isin(["Other", "Other_Excl_USDEUR"])]
    check(src, "residual categories (other, other excl. USD/EUR) within -5 .. 100", resid["share_pct"].between(-5, 100 + 1e-6).all(),
          f"min {resid.share_pct.min():.3f} max {resid.share_pct.max():.3f}")
    neg = resid[resid.share_pct < -0.01]
    info(src, "negative residual shares kept as published (100 - USD - EUR computed by the authors)",
         "; ".join(f"{r.iso3} {r.year} {r.currency} {r.share_pct:.2f}" for r in neg.itertuples()) or "none")
    w = out.pivot_table(index=["iso3", "year", "flow"], columns="currency", values="share_pct")
    trio = w.dropna(subset=["USD", "EUR", "Other_Excl_USDEUR"])
    s = trio["USD"] + trio["EUR"] + trio["Other_Excl_USDEUR"]
    check(src, "USD + EUR + other (excl. USD/EUR) = 100 where all three reported (authors' own check)",
          close(s, 100, atol=0.011).all(), f"{len(trio)} rows; max |dev| {np.abs(s - 100).max():.4f}")
    part = w.dropna(subset=["USD", "EUR", "Home", "Other"])
    s4 = part[["USD", "EUR", "Home", "Other"]].sum(axis=1)
    check(src, "USD + EUR + home + other <= 100 (+0.5) where all four reported", (s4 <= 100.5).all(),
          f"{len(part)} rows; max {s4.max():.3f}")
    yrs = out.groupby("iso3")["year"].agg(["min", "max"])
    check(src, "coverage 1990-2019 and >= 100 countries", out.year.min() >= 1989 and out.year.max() == 2019 and out.iso3.nunique() >= 100,
          f"{out.year.min()}-{out.year.max()}, {out.iso3.nunique()} countries")
    info(src, "countries without any invoicing data", ", ".join(sorted(set(raw.ISO3C) - set(out.iso3))) or "none")
    info(src, "source", "Mendeley Data 6z6w78968m v1 (replication files of Boz et al. 2022, JIE) -> Data/all_countries_update.dta; "
                        "ends 2019; the imf.org attachment is the same dataset but refuses scripted downloads")
    return out


# --------------------------------------------------------------------------------------
# D44  SAFE cross-border receipts & payments by non-banking sectors (by currency)
# --------------------------------------------------------------------------------------
SAFE_ITEMS = {  # label (after stripping numbering) -> (item, parent, group)
    "Current Account": ("Current Account", "Total", "by_transaction"),
    "Goods": ("Goods", "Current Account", "by_transaction"),
    "Services": ("Services", "Current Account", "by_transaction"),
    "Primary and Secondary Income": ("Primary and Secondary Income", "Current Account", "by_transaction"),
    "Goods based on Customs Statistics": ("Goods based on Customs Statistics", "Current Account", "memo"),
    "Capital and Financial Account": ("Capital and Financial Account", "Total", "by_transaction"),
    "Direct Investment": ("Direct Investment", "Capital and Financial Account", "by_transaction"),
    "Portfolio Investment": ("Portfolio Investment", "Capital and Financial Account", "by_transaction"),
    "Other Investment": ("Other Investment", "Capital and Financial Account", "by_transaction"),
    "RMB": ("RMB", "Total", "by_currency"),
    "Foreign Currency": ("Foreign Currency", "Total", "by_currency"),
    "USD": ("USD", "Foreign Currency", "by_currency"),
    "HKD": ("HKD", "Foreign Currency", "by_currency"),
    "EUR": ("EUR", "Foreign Currency", "by_currency"),
    "JPY": ("JPY", "Foreign Currency", "by_currency"),
    "Other": ("Other", "Foreign Currency", "by_currency"),
}
SAFE_FLOWS = {"I. Receipts": "Receipts", "II. Payments": "Payments",
              "III. Balance between Receipts and Payments": "Balance"}


def _safe_label(s):
    s = re.sub(r"\s+", " ", str(s)).strip()
    s = re.sub(r"^(?:[IVX]+\.\s*|\d+(?:\.\d+)?\.?\s+|of which:\s*)", "", s).strip()
    return s


def clean_safe():
    src = "D44 SAFE"
    path = next(iter((RAW / "safe").glob("crossborder_receipts_payments_timeseries.xls*")), None)
    if path is None:
        check(src, "raw file present", False, "raw/safe/crossborder_receipts_payments_timeseries.xls missing")
        return None, None
    xl = pd.ExcelFile(path)
    frames, n_raw_cells = [], 0
    for sh in xl.sheet_names:
        m = re.search(r"in (RMB|USD).*?(Annual|Monthly)", sh)
        if not m:
            continue
        unit_ccy, freq = ("CNY" if m.group(1) == "RMB" else "USD"), ("A" if m.group(2) == "Annual" else "M")
        df = xl.parse(sh, header=None)
        hdr = df.index[df[0].astype(str).str.strip().str.match(r"^Item\d?$")][0]
        periods = []
        for v in df.iloc[hdr, 1:]:
            if pd.isna(v):
                periods.append(None)
            elif freq == "A":
                periods.append(f"{int(float(v))}")
            else:
                periods.append(pd.Timestamp(v).strftime("%Y-%m"))
        flow, group = None, None
        for i in range(hdr + 1, len(df)):
            raw_label = df.iat[i, 0]
            if pd.isna(raw_label):
                continue
            lab = re.sub(r"\s+", " ", str(raw_label)).strip()
            if lab.startswith("Notes"):
                break
            if lab in SAFE_FLOWS:
                flow, group = SAFE_FLOWS[lab], "total"
                item, parent, grp = "Total", "", "total"
            elif lab in ("By transaction:", "By currency:"):
                group = lab[3:-1].replace(" ", "_").lower()
                continue
            else:
                key = _safe_label(lab)
                if key not in SAFE_ITEMS:
                    check(src, f"known row label {lab!r} in sheet {sh!r}", False, "add it to SAFE_ITEMS")
                    continue
                item, parent, grp = SAFE_ITEMS[key]
            for j, per in enumerate(periods, start=1):
                if per is None:
                    continue
                v = df.iat[i, j]
                if pd.isna(v) or str(v).strip() == "":
                    continue
                n_raw_cells += 1
                frames.append((freq, per, flow, grp, item, parent, unit_ccy, to_num(v)))
    out = pd.DataFrame(frames, columns=["freq", "period", "flow", "group", "item", "parent", "unit_currency", "value"])
    out["date"] = out["period"].map(period_to_date)
    out["unit"] = out["unit_currency"] + " 100 million"
    out = out[["freq", "period", "date", "flow", "group", "item", "parent", "unit_currency", "unit", "value"]]
    out = out.sort_values(["unit_currency", "freq", "date", "flow", "group", "item"]).reset_index(drop=True)
    # checks
    check(src, "every numeric cell of the 4 sheets lands in the output", n_raw_cells == len(out) and out.value.notna().all(),
          f"{n_raw_cells} cells, {len(out)} rows")
    dup = out.duplicated(["freq", "period", "flow", "item", "unit_currency"]).sum()
    check(src, "no duplicate (freq, period, flow, item, unit) rows", dup == 0, f"{dup} duplicates")
    mon = out[out.freq == "M"]
    ok, missing = contiguous_months(mon.period)
    check(src, "monthly periods contiguous", ok, f"{mon.period.min()} -> {mon.period.max()}; missing {missing[:5]}")
    w = out.pivot_table(index=["unit_currency", "freq", "period", "flow"], columns="item", values="value")
    s = w["RMB"] + w["Foreign Currency"]
    check(src, "RMB + foreign currency = total (receipts, payments, balance)", close(s, w["Total"], atol=0.6).all(),
          f"max |dev| {np.abs(s - w['Total']).max():.3f} (100 million; source values are rounded)")
    s = w[["USD", "HKD", "EUR", "JPY", "Other"]].sum(axis=1)
    check(src, "USD + HKD + EUR + JPY + other = foreign currency", close(s, w["Foreign Currency"], atol=0.6).all(),
          f"max |dev| {np.abs(s - w['Foreign Currency']).max():.3f}")
    rp = w["Total"].unstack("flow")
    check(src, "receipts - payments = balance", close(rp["Receipts"] - rp["Payments"], rp["Balance"], atol=0.6).all(),
          f"max |dev| {np.abs(rp['Receipts'] - rp['Payments'] - rp['Balance']).max():.3f}")
    # annual == sum of months for complete years
    mt = mon[mon["group"].isin(["total", "by_currency"])].assign(year=lambda d: d.period.str[:4])
    cnt = mt.groupby(["unit_currency", "flow", "item", "year"]).value.agg(["sum", "count"]).reset_index()
    cnt = cnt[cnt["count"] == 12]
    ann = out[(out.freq == "A")].rename(columns={"period": "year"})[["unit_currency", "flow", "item", "year", "value"]]
    cmp = cnt.merge(ann, on=["unit_currency", "flow", "item", "year"])
    check(src, "annual value = sum of the 12 months (complete years)", close(cmp["sum"], cmp["value"], atol=1.0, rtol=1e-6).all(),
          f"{len(cmp)} comparisons; max |dev| {np.abs(cmp['sum'] - cmp['value']).max():.3f}")
    # RMB share identical whether measured in the CNY or the USD sheet
    sh = (w["RMB"] / w["Total"] * 100).unstack("unit_currency")
    sh = sh.loc[sh.index.get_level_values("flow") != "Balance"].dropna()
    check(src, "RMB share identical in the CNY- and USD-denominated sheets (±0.1 pp)", close(sh["CNY"], sh["USD"], atol=0.1).all(),
          f"{len(sh)} rows; max |dev| {np.abs(sh['CNY'] - sh['USD']).max():.4f} pp")
    latest = mon.period.max()
    v = w.loc[("USD", "M", latest, "Receipts")]
    info(src, f"latest month {latest}: RMB share of receipts / payments (USD sheet)",
         f"{v['RMB'] / v['Total'] * 100:.1f}% / {w.loc[('USD', 'M', latest, 'Payments'), 'RMB'] / w.loc[('USD', 'M', latest, 'Payments'), 'Total'] * 100:.1f}%")
    # derived RMB share table (USD sheet)
    u = w.xs("USD", level="unit_currency")
    rec, pay = u.xs("Receipts", level="flow"), u.xs("Payments", level="flow")
    share = pd.DataFrame({
        "receipts_total_usd_100mn": rec["Total"], "receipts_rmb_usd_100mn": rec["RMB"],
        "payments_total_usd_100mn": pay["Total"], "payments_rmb_usd_100mn": pay["RMB"],
        "goods_receipts_usd_100mn": rec["Goods"], "goods_payments_usd_100mn": pay["Goods"],
    })
    share["rmb_share_receipts_pct"] = share.receipts_rmb_usd_100mn / share.receipts_total_usd_100mn * 100
    share["rmb_share_payments_pct"] = share.payments_rmb_usd_100mn / share.payments_total_usd_100mn * 100
    share["rmb_share_total_pct"] = ((share.receipts_rmb_usd_100mn + share.payments_rmb_usd_100mn)
                                    / (share.receipts_total_usd_100mn + share.payments_total_usd_100mn) * 100)
    share = share.reset_index()
    share["date"] = share["period"].map(period_to_date)
    share = share[["freq", "period", "date"] + [c for c in share.columns if c not in ("freq", "period", "date")]]
    share = share.sort_values(["freq", "date"]).reset_index(drop=True)
    check(src, "derived RMB shares within 0-100", share.filter(like="_pct").stack().between(0, 100).all())
    regions = sorted(p.name for p in (RAW / "safe" / "by_region").glob("*.xls*"))
    info(src, "by-region workbooks kept raw only", ", ".join(regions) or "none")
    return out, share


# --------------------------------------------------------------------------------------
# D45  IMF COFER
# --------------------------------------------------------------------------------------
def clean_cofer():
    src = "D45 COFER"
    dpath, spath = RAW / "imf_cofer" / "cofer_data.json", RAW / "imf_cofer" / "cofer_structure.json"
    if not dpath.exists():
        check(src, "raw file present", False, f"{dpath} missing")
        return None
    data = json.loads(dpath.read_text(encoding="utf-8"))
    cls = sdmx_codelists(json.loads(spath.read_text(encoding="utf-8"))) if spath.exists() else {}
    long = sdmx_data_to_long(data)
    n_obs = sum(len(s["observations"]) for ds in data["data"]["dataSets"] for s in ds["series"].values())
    out = pd.DataFrame({
        "country_code": long["COUNTRY"],
        "country": long["COUNTRY"].map(cls.get("CL_COUNTRY", {})).fillna(long["COUNTRY"]),
        "indicator_code": long["INDICATOR"],
        "indicator": long["INDICATOR"].map(cls.get("CL_COFER_INDICATOR", {})).fillna(long["INDICATOR"]),
        "currency_code": long["FXR_CURRENCY"].str.replace("CI_", "", regex=False),
        "currency": long["FXR_CURRENCY"].map(cls.get("CL_COFER_FXR_CURRENCY", {})).fillna(long["FXR_CURRENCY"]).str.replace("Claims in ", "", regex=False),
        "transformation": long["TYPE_OF_TRANSFORMATION"].map({"SHRO_PT": "share_pct", "NV_USD": "usd"}).fillna(long["TYPE_OF_TRANSFORMATION"]),
        "freq": long["FREQUENCY"],
        "period": long["TIME_PERIOD"].map(norm_period),
        "value": long["value"],
        "derivation": long.get("DERIVATION_TYPE"),
        "status": long.get("STATUS"),
    })
    out["date"] = out["period"].map(period_to_date)
    out["unit"] = out["transformation"].map({"share_pct": "percent of allocated reserves", "usd": "US dollars"})
    out = out[["country_code", "country", "indicator_code", "indicator", "currency_code", "currency", "transformation",
               "unit", "freq", "period", "date", "value", "derivation", "status"]]
    out = out.sort_values(["country_code", "indicator_code", "transformation", "currency_code", "freq", "date"]).reset_index(drop=True)
    # checks
    check(src, "every observation in the SDMX message lands in the output", n_obs == len(out), f"{n_obs} vs {len(out)}")
    dup = out.duplicated(["country_code", "indicator_code", "currency_code", "transformation", "freq", "period"]).sum()
    check(src, "no duplicate series x period", dup == 0, f"{dup}")
    v = out.dropna(subset=["value"])
    sh = v[(v.transformation == "share_pct") & (v.indicator_code == "AFXRA") & (v.currency_code != "T")]
    s = sh.groupby(["country_code", "freq", "period"]).value.sum()
    check(src, "allocated-reserve currency shares sum to 100 (±0.15)", close(s, 100, atol=0.15).all(),
          f"{len(s)} groups; min {s.min():.3f} max {s.max():.3f}")
    nv = v[(v.transformation == "usd") & (v.indicator_code == "AFXRA")]
    tot = nv[nv.currency_code == "T"].set_index(["country_code", "freq", "period"]).value
    parts = nv[nv.currency_code != "T"].groupby(["country_code", "freq", "period"]).value.sum()
    cmp = pd.concat([tot.rename("total"), parts.rename("parts")], axis=1).dropna()
    check(src, "USD sum of currency claims = allocated total (±0.01%)", close(cmp.parts, cmp.total, rtol=1e-4).all(),
          f"{len(cmp)} groups; max rel dev {((cmp.parts - cmp.total).abs() / cmp.total).max():.2e}")
    t = v[(v.transformation == "usd") & (v.currency_code == "T")].pivot_table(index=["country_code", "freq", "period"], columns="indicator_code", values="value")
    t2 = t.dropna(subset=["AFXRA", "UFXRA", "TFXRA"])
    check(src, "allocated + unallocated = total reserves (±0.01%)", close(t2.AFXRA + t2.UFXRA, t2.TFXRA, rtol=1e-4).all(),
          f"{len(t2)} groups; max rel dev {((t2.AFXRA + t2.UFXRA - t2.TFXRA).abs() / t2.TFXRA).max():.2e}")
    q = v[(v.freq == "Q") & (v.country_code == "G001") & (v.currency_code == "USD") & (v.transformation == "share_pct") & (v.indicator_code == "AFXRA")]
    qp = sorted(q.period)
    full = pd.period_range(qp[0].replace("-", ""), qp[-1].replace("-", ""), freq="Q").strftime("%Y-Q%q")
    missing = sorted(set(full) - set(qp))
    check(src, "world quarterly USD-share series contiguous", not missing, f"{qp[0]} -> {qp[-1]}; missing {missing[:5]}")
    last = q.sort_values("date").iloc[-1]
    check(src, "latest world USD share plausible (50-65%)", 50 <= last.value <= 65, f"{last.period}: {last.value:.2f}%")
    cny = v[(v.freq == "Q") & (v.country_code == "G001") & (v.currency_code == "CNY") & (v.transformation == "share_pct") & (v.indicator_code == "AFXRA")]
    info(src, "CNY first reported quarter (series break when CNY added)", f"{cny.period.min()} ({cny.sort_values('date').iloc[0].value:.2f}%); latest {cny.period.max()} {cny.sort_values('date').iloc[-1].value:.2f}%")
    info(src, "country groups", ", ".join(f"{k}={vv}" for k, vv in out.drop_duplicates('country_code')[['country_code', 'country']].values))
    return out


# --------------------------------------------------------------------------------------
# D46  SWIFT RMB tracker (manual CSV only)
# --------------------------------------------------------------------------------------
def clean_swift():
    src = "D46 SWIFT"
    path = RAW / "swift_rmb_tracker" / "swift_rmb_tracker.csv"
    if not path.exists():
        info(src, "status", "blocked for scripts (swift.com 403 + login wall); hand-collected CSV not present - see raw/swift_rmb_tracker/README.md")
        return None
    df = pd.read_csv(path)
    need = {"month", "currency", "share_pct", "rank", "basis", "source_pdf"}
    check(src, "hand-collected CSV has the expected columns", need <= set(df.columns), f"{sorted(df.columns)}")
    df["date"] = pd.to_datetime(df["month"].astype(str) + "-01")
    check(src, "shares within 0-100", df.share_pct.between(0, 100).all())
    return df.sort_values(["basis", "currency", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D47  CIPS volumes (PDF tables)
# --------------------------------------------------------------------------------------
CN_MONTHS = {f"{i}月": i for i in range(1, 13)}
EN_MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _pdf_text(path):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def _parse_cips_table(text, lang):
    """Return (kind, rows). kind 'monthly' -> [(month, tx, amount, days, avg_tx, avg_amt)]; 'annual' -> [(year, tx, amount)].
    Amounts converted to billion CNY (English files are already bn yuan; Chinese 亿元 / 10)."""
    rows, kind = [], None
    for line in text.splitlines():
        toks = line.replace("　", " ").split()
        if not toks:
            continue
        head = toks[0].rstrip(".")
        nums = [to_num(t) for t in toks[1:]]
        if lang == "cn" and head in CN_MONTHS and len(nums) >= 5:
            kind = "monthly"
            rows.append((CN_MONTHS[head], nums[0], nums[1] / 10, nums[2], nums[3], nums[4] / 10))
        elif lang == "en" and head in EN_MONTHS and len(nums) >= 5:
            kind = "monthly"
            rows.append((EN_MONTHS[head], nums[0], nums[1], nums[2], nums[3], nums[4]))
        elif re.fullmatch(r"(19|20)\d\d年?", head) and len(nums) >= 2:
            kind = "annual"
            yr = int(head.rstrip("年"))
            rows.append((yr, nums[0], nums[1] / 10 if lang == "cn" else nums[1]))
    return kind, rows


def clean_cips():
    src = "D47 CIPS"
    pdfs = sorted((RAW / "cips").glob("*.pdf"))
    if not pdfs:
        check(src, "raw PDFs present", False, "raw/cips/*.pdf missing")
        return None
    tables = {}  # (lang, kind) -> rows
    for p in pdfs:
        lang = p.name.split("_")[0]
        kind, rows = _parse_cips_table(_pdf_text(p), lang)
        if kind:
            tables[(lang, kind)] = (rows, p.name)
    check(src, "English monthly + annual tables parsed", ("en", "monthly") in tables and ("en", "annual") in tables, f"{sorted(tables)}")
    # overview sentence on the English statistics page gives the current year, latest month and YTD totals
    page = (RAW / "cips" / "statistics_page_en.html").read_text(encoding="utf-8", errors="replace")
    txt = re.sub(r"<[^>]+>", " ", page)
    txt = re.sub(r"\s+", " ", txt)
    m1 = re.search(r"In (\w+) (\d{4}), the CIPS system processed a total of ([\d.,]+)\s*(million|thousand)?\s*RMB payment transactions, with a total amount of ([\d.,]+) trillion yuan", txt)
    m2 = re.search(r"From January to (\w+) (\d{4}), the CIPS system processed a total of ([\d.,]+)\s*(million|thousand)?\s*RMB payment transactions, with a total amount of ([\d.,]+) trillion yuan", txt)
    check(src, "overview sentences found on the statistics page", bool(m1 and m2), (m1.group(0)[:120] if m1 else "not found"))
    cur_year = int(m1.group(2)) if m1 else date.today().year
    mult = {"million": 1e6, "thousand": 1e3, None: 1}
    en_m, en_m_file = tables.get(("en", "monthly"), ([], ""))
    en_a, en_a_file = tables.get(("en", "annual"), ([], ""))
    rows = []
    for (mo, tx, amt, days, avg_tx, avg_amt) in en_m:
        rows.append(("M", f"{cur_year}-{mo:02d}", cur_year, mo, tx, amt, days, avg_tx, avg_amt, en_m_file))
    for (yr, tx, amt) in en_a:
        rows.append(("A", f"{yr}", yr, np.nan, tx, amt, np.nan, np.nan, np.nan, en_a_file))
    out = pd.DataFrame(rows, columns=["freq", "period", "year", "month", "transactions", "amount_bn_cny", "working_days",
                                      "daily_avg_transactions", "daily_avg_amount_bn_cny", "source_file"])
    out["date"] = out["period"].map(period_to_date)
    out = out[["freq", "period", "date", "year", "month", "transactions", "amount_bn_cny", "working_days",
               "daily_avg_transactions", "daily_avg_amount_bn_cny", "source_file"]].sort_values(["freq", "date"]).reset_index(drop=True)
    # checks
    if ("cn", "monthly") in tables:
        cn = pd.DataFrame(tables[("cn", "monthly")][0], columns=["month", "tx", "amt", "days", "avg_tx", "avg_amt"])
        en = pd.DataFrame(en_m, columns=cn.columns)
        same = len(cn) == len(en) and close(cn.tx, en.tx).all() and close(cn.amt, en.amt, atol=0.06).all() and close(cn.days, en.days).all()
        check(src, "Chinese and English monthly tables agree (亿元/10 = bn yuan)", same, f"{len(cn)} vs {len(en)} rows")
    if ("cn", "annual") in tables:
        cn = pd.DataFrame(tables[("cn", "annual")][0], columns=["year", "tx", "amt"])
        en = pd.DataFrame(en_a, columns=cn.columns)
        same = len(cn) == len(en) and close(cn.tx, en.tx).all() and close(cn.amt, en.amt, atol=0.06).all()
        check(src, "Chinese and English annual tables agree", same, f"{len(cn)} vs {len(en)} rows")
    mo = out[out.freq == "M"]
    check(src, "monthly rows: daily average x working days = total (±1%)",
          close(mo.daily_avg_transactions * mo.working_days, mo.transactions, rtol=0.01).all()
          and close(mo.daily_avg_amount_bn_cny * mo.working_days, mo.amount_bn_cny, rtol=0.01).all(), f"{len(mo)} months")
    check(src, "months of the current year contiguous from January", list(mo.month) == list(range(1, len(mo) + 1)), f"{list(mo.month)}")
    if m1 and m2:
        last = mo.iloc[-1]
        tx_last = to_num(m1.group(3)) * mult[m1.group(4)]
        check(src, f"latest month ({m1.group(1)} {m1.group(2)}) matches the page overview",
              EN_MONTHS[m1.group(1)[:3]] == last.month and close(tx_last, last.transactions, rtol=0.01) and close(to_num(m1.group(5)) * 1000, last.amount_bn_cny, rtol=0.01),
              f"page {tx_last:,.0f} tx / {m1.group(5)} tn vs table {last.transactions:,.0f} / {last.amount_bn_cny / 1000:.3f} tn")
        tx_ytd = to_num(m2.group(3)) * mult[m2.group(4)]
        check(src, "year-to-date sum of months matches the page overview (±0.5%)",
              close(tx_ytd, mo.transactions.sum(), rtol=0.005) and close(to_num(m2.group(5)) * 1000, mo.amount_bn_cny.sum(), rtol=0.005),
              f"page {tx_ytd:,.0f} / {m2.group(5)} tn vs sum {mo.transactions.sum():,.0f} / {mo.amount_bn_cny.sum() / 1000:.3f} tn")
    an = out[out.freq == "A"]
    check(src, "annual history starts 2015 and is contiguous", list(an.year) == list(range(2015, int(an.year.max()) + 1)), f"{list(an.year)}")
    check(src, "annual values increase every year (CIPS has grown each year since launch)", an.amount_bn_cny.is_monotonic_increasing)
    return out


# --------------------------------------------------------------------------------------
# D48  BIS Triennial FX turnover
# --------------------------------------------------------------------------------------
BIS_KEEP = {  # fixed dimensions of the clean table
    "FREQ": "A", "DER_TYPE": "U", "DER_RISK": "B", "DER_REP_CTY": "5J", "DER_CPC": "5J", "DER_SECTOR_UDL": "A",
    "DER_ISSUE_MAT": "A", "DER_RATING": "A", "DER_EX_METHOD": "3", "DER_BASIS": "C",
}


def clean_bis():
    src = "D48 BIS"
    zpath = RAW / "bis_triennial" / "WS_DER_OTC_TOV_csv_flat.zip"
    if not zpath.exists():
        check(src, "raw file present", False, f"{zpath} missing")
        return None, None
    keep = []
    n_total = 0
    with zipfile.ZipFile(zpath) as z:
        member = z.namelist()[0]
        with z.open(member) as f:
            for ch in pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"), chunksize=500_000, dtype=str, keep_default_na=False):
                n_total += len(ch)
                codes = {c.split(":")[0]: ch[c].str.split(":", n=1).str[0] for c in ch.columns if ":" in c}
                mask = np.ones(len(ch), bool)
                for dim, val in BIS_KEEP.items():
                    mask &= (codes[dim] == val).values
                keep.append(ch[mask])
    df = pd.concat(keep, ignore_index=True)
    info(src, "bulk file", f"{member}: {n_total:,} rows scanned; {len(df):,} rows match the FX / all-countries / net-net key")

    def split(col):
        s = df[col].str.split(":", n=1, expand=True)
        return s[0].str.strip(), s[1].str.strip()

    out = pd.DataFrame({"year": df["TIME_PERIOD:Time period or range"].astype(int)})
    out["instrument_code"], out["instrument"] = split("DER_INSTR:Instrument")
    out["counterparty_code"], out["counterparty"] = split("DER_SECTOR_CPY:Counterparty sector")
    out["currency_1"], out["currency_1_name"] = split("DER_CURR_LEG1:Currency leg 1")
    out["currency_2"], out["currency_2_name"] = split("DER_CURR_LEG2:Currency leg 2")
    out["value_usd_mn"] = df["OBS_VALUE:Observation Value"].map(to_num)
    out["obs_status"] = df["OBS_STATUS:Observation Status"].str.split(":", n=1).str[0]
    out["unit"] = "USD million, daily average in April, net-net basis"
    n_values = int(out.value_usd_mn.notna().sum())
    out = out.dropna(subset=["value_usd_mn"]).sort_values(["year", "instrument_code", "counterparty_code", "currency_1", "currency_2"]).reset_index(drop=True)
    check(src, "every non-missing value of the key subset lands in the output", n_values == len(out), f"{n_values}")
    check(src, "units are USD millions", (df["UNIT_MEASURE:Unit of measure"].str.startswith("USD").all() and df["UNIT_MULT:Unit Multiplier"].str.startswith("6").all()))
    yrs = sorted(out.year.unique())
    check(src, "survey years are triennial (1989, 1992, ... )", all((y - 1989) % 3 == 0 for y in yrs), f"{yrs}")
    dup = out.duplicated(["year", "instrument_code", "counterparty_code", "currency_1", "currency_2"]).sum()
    check(src, "no duplicate keys", dup == 0, f"{dup}")
    # by-currency table: all instruments, all counterparties, leg2 = all currencies
    bc = out[(out.instrument_code == "A") & (out.counterparty_code == "A") & (out.currency_2 == "TO1")].copy()
    tot = bc[bc.currency_1 == "TO1"].set_index("year").value_usd_mn
    cur = bc[bc.currency_1 != "TO1"].copy()
    cur["share_pct_of_200"] = cur.value_usd_mn / cur.year.map(tot) * 100
    s = cur.groupby("year").share_pct_of_200.sum()
    check(src, "listed currencies sum to <= 200% (each trade has two legs) and >= 175%", ((s <= 200.05) & (s >= 175)).all(),
          "; ".join(f"{y}: {v:.2f}" for y, v in s.items()))
    # BIS does not publish a residual row: add "other currencies" = 2 x total - listed currencies
    resid = pd.DataFrame({"year": s.index, "currency_1": "OTH", "currency_1_name": "Other currencies (residual: 2 x total - listed)",
                          "value_usd_mn": (2 * tot.loc[s.index] - cur.groupby("year").value_usd_mn.sum()).values,
                          "share_pct_of_200": (200 - s).values, "unit": bc.unit.iloc[0]})
    check(src, "residual 'other currencies' non-negative", (resid.share_pct_of_200 >= -0.05).all(), f"min {resid.share_pct_of_200.min():.2f}")
    cur = pd.concat([cur[resid.columns], resid], ignore_index=True)
    usd = cur[cur.currency_1 == "USD"].set_index("year").share_pct_of_200
    check(src, "USD share in 2022 and 2025 within 85-92%", all(85 <= usd.get(y, 0) <= 92 for y in (2022, 2025)),
          "; ".join(f"{y}: {v:.1f}%" for y, v in usd.items()))
    cny = cur[cur.currency_1 == "CNY"].set_index("year").share_pct_of_200
    info(src, "CNY share of global FX turnover", "; ".join(f"{y}: {v:.2f}%" for y, v in cny.items()))
    info(src, "global FX turnover, USD bn per day", "; ".join(f"{y}: {v / 1000:,.0f}" for y, v in tot.items()))
    by_cur = pd.concat([bc[bc.currency_1 == "TO1"].assign(share_pct_of_200=200.0), cur])[
        ["year", "currency_1", "currency_1_name", "value_usd_mn", "share_pct_of_200", "unit"]].rename(
        columns={"currency_1": "currency", "currency_1_name": "currency_name", "value_usd_mn": "turnover_usd_mn"})
    by_cur = by_cur.sort_values(["year", "turnover_usd_mn"], ascending=[True, False]).reset_index(drop=True)
    return out, by_cur


# --------------------------------------------------------------------------------------
# D49  TIC major foreign holders
# --------------------------------------------------------------------------------------
MONTH_ABBR = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


TIC_MEMO_NAMES = {  # slt_table5 spelling -> mfhhis01 spelling
    "Of Which: Foreign Official": "For. Official",
    "Of Which: Foreign Official Treasury Bills": "Treasury Bills",
    "Of Which: Foreign Official T-Bonds & Notes": "T-Bonds & Notes",
}


def _tic_cell(c):
    return html_unescape(c).replace(" ", " ").strip()


def html_unescape(s):
    import html as _h
    return _h.unescape(s)


def _parse_tic(path, stats):
    """Parse a TIC Major-Foreign-Holders text file (tab separated) into long rows.

    mfhhis01.txt has one block per year (columns Dec -> Jan). Two quirks are handled:
      * series-break months appear twice (e.g. two "Jun" columns, or two "Mar" in 2000): the LEFT one is the new
        series, the right one "is shown for comparison only" (file footnotes) and is dropped (counted in stats);
      * for 2002-2011 the January column is mis-aligned: its header sits one row higher ("Jan" above the month row,
        the year at the end of the month row, "------" at the end of the Country row) and every value is one row
        higher than its country. It is re-aligned here.
    slt_table5.txt has a single block with "YYYY-MM" headers and the "Of Which: Foreign Official ..." memo rows.
    """
    lines = [[_tic_cell(c) for c in r] for r in csv.reader(io.StringIO(path.read_text(encoding="utf-8", errors="replace")), delimiter="\t")]
    rows, i = [], 0
    while i < len(lines):
        row = lines[i]
        if not (row and row[0] == "Country"):
            i += 1
            continue
        above = lines[i - 1] if i >= 1 else []
        above2 = lines[i - 2] if i >= 2 else []
        cols, shifted, seen = [], None, set()
        for j in range(1, len(row)):
            yr, mth = row[j], (above[j] if j < len(above) else "")
            per = None
            if re.fullmatch(r"\d{4}-\d{2}", yr):
                per = yr
            elif mth[:3] in MONTH_ABBR and re.fullmatch(r"\d{4}", yr):
                per = f"{int(yr)}-{MONTH_ABBR[mth[:3]]:02d}"
            elif yr.startswith("---") and re.fullmatch(r"\d{4}", mth) and j < len(above2) and above2[j][:3] in MONTH_ABBR:
                per, shifted = f"{int(mth)}-{MONTH_ABBR[above2[j][:3]]:02d}", j
            if per in seen:                      # series-break duplicate column -> keep the newer (left) one
                stats["prebreak_columns"] += 1
                per = None
            if per:
                seen.add(per)
            cols.append(per)
        # collect the block's lines: dashed row, country rows, blank, "Of which" memo rows, blank
        block, k, blanks = [], i + 1, 0
        while k < len(lines):
            r = lines[k]
            if not any(r):
                blanks += 1
                nxt = lines[k + 1] if k + 1 < len(lines) else [""]
                if blanks == 1 and nxt and nxt[0].startswith("Of which"):
                    block.append(r)
                    k += 1
                    continue
                break
            block.append(r)
            k += 1
        section = "country"
        for n, r in enumerate(block):
            name = r[0] if r else ""
            if name.startswith("Of which"):
                section = "memo"
                continue
            if name == "" or name.startswith("---"):
                continue
            clean_name = TIC_MEMO_NAMES.get(name, re.sub(r"\s*\d+/\s*$", "", name).strip())
            rtype = "grand_total" if clean_name == "Grand Total" else "all_other" if clean_name == "All Other" else section
            if clean_name.startswith("Of Which") or clean_name in ("For. Official", "Treasury Bills", "T-Bonds & Notes"):
                rtype = "memo"
            for j, per in enumerate(cols, start=1):
                if per is None:
                    continue
                if j == shifted:
                    prev = block[n - 1] if n >= 1 else []
                    v = prev[j] if j < len(prev) else ""
                else:
                    v = r[j] if j < len(r) else ""
                val = to_num(v)
                if not np.isnan(val):
                    rows.append((path.name, clean_name, rtype, per, val))
        i = k + 1
    return pd.DataFrame(rows, columns=["source_file", "country", "row_type", "period", "holdings_usd_bn"])


def clean_tic():
    src = "D49 TIC"
    files = [RAW / "tic" / "slt_table5.txt", RAW / "tic" / "mfhhis01.txt"]
    if not all(p.exists() for p in files):
        check(src, "raw files present", False, "raw/tic/slt_table5.txt or mfhhis01.txt missing")
        return None
    stats = {"prebreak_columns": 0}
    cur, his = _parse_tic(files[0], stats), _parse_tic(files[1], stats)
    check(src, "both files parsed", len(cur) > 0 and len(his) > 0, f"slt_table5.txt {len(cur)} cells, mfhhis01.txt {len(his)} cells")
    info(src, "series-break comparison columns dropped (older series 'shown for comparison only')", stats["prebreak_columns"])
    # overlap: the current table carries the latest revisions - use it where both exist
    key = ["country", "row_type", "period"]
    ov = cur.merge(his, on=key, suffixes=("_cur", "_his"))
    nd = int((~close(ov.holdings_usd_bn_cur, ov.holdings_usd_bn_his, atol=0.051)).sum())
    check(src, "the two files overlap on at least 3 months", ov.period.nunique() >= 3, f"{sorted(ov.period.unique())}")
    warn(src, "overlapping months agree between slt_table5.txt and mfhhis01.txt (±0.05 bn; revisions expected after benchmark surveys)",
         nd == 0, f"{len(ov)} overlapping cells, {nd} differ")
    # the history file lists ~45 holders per month, the current 13-month table only the top ~20 (the rest are inside
    # its "All Other"): months covered by the history file come from it alone, the current table adds the newer months
    hisp = set(his.period)
    names_cur = set(cur[cur.row_type == "country"].country)
    names_his = set(his[(his.row_type == "country") & his.period.isin(set(cur.period))].country)
    info(src, "holders listed in mfhhis01.txt but folded into 'All Other' in slt_table5.txt (so absent after its last month)",
         ", ".join(sorted(names_his - names_cur)) or "none")
    check(src, "every holder of the current table also appears in the history file", not (names_cur - names_his), f"{sorted(names_cur - names_his)}")
    out = pd.concat([his, cur[~cur.period.isin(hisp)]], ignore_index=True)
    out["date"] = out["period"].map(period_to_date)
    aggs = sorted(c for c in out[out.row_type == "country"].country.unique() if re.search(r"Exporters|Ctrs|Centers|Caribbean|Carib", c))
    info(src, "aggregate rows typed as 'country' (older vintages)", ", ".join(aggs) or "none")
    out = out[["country", "row_type", "period", "date", "holdings_usd_bn", "source_file"]].sort_values(["row_type", "country", "date"]).reset_index(drop=True)
    dup = out.duplicated(["country", "row_type", "period"]).sum()
    check(src, "no duplicate country x month", dup == 0, f"{dup}")
    gt = out[out.row_type == "grand_total"].set_index("period").holdings_usd_bn
    ok, missing = contiguous_months(gt.index)
    check(src, "Grand Total months contiguous", ok, f"{gt.index.min()} -> {gt.index.max()}; missing {missing[:6]}")
    parts = out[out.row_type.isin(["country", "all_other"])].groupby("period").holdings_usd_bn.sum()
    cmp = pd.concat([parts.rename("parts"), gt.rename("total")], axis=1).dropna()
    bad = cmp[~close(cmp.parts, cmp.total, atol=0.55)]
    check(src, "countries + All Other = Grand Total (±0.55 bn: ~45 rows rounded to 0.1)", bad.empty,
          f"{len(cmp)} months; worst {((cmp.parts - cmp.total).abs()).max():.2f} bn" + (f"; e.g. {bad.index[:3].tolist()}" if not bad.empty else ""))
    memo = out[out.row_type == "memo"].pivot_table(index="period", columns="country", values="holdings_usd_bn")
    if {"For. Official", "Treasury Bills", "T-Bonds & Notes"} <= set(memo.columns):
        mm = memo.dropna(subset=["For. Official", "Treasury Bills", "T-Bonds & Notes"])
        check(src, "memo: foreign-official Treasury Bills + T-Bonds & Notes = For. Official (±0.35 bn)",
              close(mm["Treasury Bills"] + mm["T-Bonds & Notes"], mm["For. Official"], atol=0.35).all(),
              f"{len(mm)} months; worst {(mm['Treasury Bills'] + mm['T-Bonds & Notes'] - mm['For. Official']).abs().max():.2f}")
        mo = memo.dropna(subset=["For. Official"]).join(gt.rename("total"), how="inner")
        check(src, "memo: foreign official holdings below Grand Total", (mo["For. Official"] <= mo.total + 0.05).all(), f"{len(mo)} months")
    for c in ("Japan", "China, Mainland"):
        s = out[(out.country == c) & (out.row_type == "country")]
        ok, missing = contiguous_months(s.period)
        check(src, f"{c}: months contiguous", ok, f"{s.period.min()} -> {s.period.max()}; missing {missing[:4]}")
    latest = gt.index.max()
    top = out[(out.period == latest) & (out.row_type == "country")].nlargest(5, "holdings_usd_bn")
    info(src, f"top holders {latest} (USD bn)", "; ".join(f"{r.country} {r.holdings_usd_bn:,.1f}" for r in top.itertuples()))
    info(src, "series breaks", "holdings are benchmark-survey based; footnoted series breaks every June (see raw/tic/mfhhis01.txt notes). "
                               "The new series is kept at each break; the old-series comparison column is dropped")
    info(src, "legacy raw/tic/mfh.txt", "not parsed: the file stopped updating in January 2023 and is fully covered by mfhhis01.txt")
    return out


# --------------------------------------------------------------------------------------
# D50  Gold reserves: IMF IRFCL (monthly) + World Bank WDI (annual)
# --------------------------------------------------------------------------------------
def clean_irfcl():
    src = "D50 IRFCL gold"
    files = {k: RAW / "imf_irfcl" / f"{k}.json" for k in ("gold_troy_oz", "gold_usd", "official_reserve_assets_usd")}
    if not files["gold_troy_oz"].exists():
        check(src, "raw file present", False, f"{files['gold_troy_oz']} missing")
        return None
    spath = RAW / "imf_irfcl" / "irfcl_structure.json"
    cls = sdmx_codelists(json.loads(spath.read_text(encoding="utf-8"))) if spath.exists() else {}
    countries = cls.get("CL_IRFCL_COUNTRY_PUB", {}) or cls.get("CL_COUNTRY", {})
    sectors = cls.get("CL_SECTOR", {})
    parts, n_obs = [], 0
    for name, p in files.items():
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        n_obs += sum(len(s["observations"]) for ds in data["data"]["dataSets"] for s in ds["series"].values())
        d = sdmx_data_to_long(data)
        d["measure"] = name
        parts.append(d)
    long = pd.concat(parts, ignore_index=True)
    out = pd.DataFrame({
        "iso3": long["COUNTRY"],
        "country": long["COUNTRY"].map(countries).fillna(long["COUNTRY"]),
        "sector_code": long["SECTOR"],
        "sector": long["SECTOR"].map(sectors).fillna(long["SECTOR"]),
        "measure": long["measure"],
        "indicator_code": long["INDICATOR"],
        "period": long["TIME_PERIOD"].map(norm_period),
        "value": long["value"],
        "status": long.get("STATUS"),
    })
    out["date"] = out["period"].map(period_to_date)
    out["unit"] = out["measure"].map({"gold_troy_oz": "fine troy ounces", "gold_usd": "US dollars", "official_reserve_assets_usd": "US dollars"})
    out = out.sort_values(["iso3", "sector_code", "measure", "date"]).reset_index(drop=True)
    check(src, "every observation in the SDMX messages lands in the output", n_obs == len(out), f"{n_obs} vs {len(out)}")
    dup = out.duplicated(["iso3", "sector_code", "measure", "period"]).sum()
    check(src, "no duplicate country x sector x measure x month", dup == 0, f"{dup}")
    v = out.dropna(subset=["value"])
    w = v.pivot_table(index=["iso3", "country", "sector_code", "sector", "period", "date"], columns="measure", values="value").reset_index()
    # a few reporters publish the ounce figure 1,000x too large (e.g. Brazil from 2026-03, Angola throughout): keep the
    # reported number, blank the derived volume and flag the row. Aggregates (euro area G163, ECB) legitimately exceed 9,000 t.
    w["gold_troy_oz_reported"] = w["gold_troy_oz"]
    aggregate = w.iso3.str.match(r"^(G\d+|EZB|U\d+)$")
    bad = (w.gold_troy_oz / TROY_OZ_PER_TONNE > 9000) & ~aggregate
    w["flag"] = np.where(bad, "implausible_volume_in_source", "")
    w.loc[bad, "gold_troy_oz"] = np.nan
    w["gold_tonnes"] = w["gold_troy_oz"] / TROY_OZ_PER_TONNE
    info(src, "rows flagged implausible_volume_in_source (reported ounces imply > 9,000 t; volume blanked, reported value kept)",
         "; ".join(f"{k[0]}/{k[1]}: {len(g)} months {g.period.min()}..{g.period.max()}" for k, g in w[bad].groupby(["iso3", "sector_code"])) or "none")
    usa = w[(w.iso3 == "USA") & w.gold_tonnes.notna()].sort_values("date").iloc[-1]
    check(src, "USA holds ~8,133 tonnes (±1%)", close(usa.gold_tonnes, 8133.5, rtol=0.01), f"{usa.period}: {usa.gold_tonnes:,.1f} t")
    check(src, "no single reporter above 9,000 tonnes after flagging; euro-area aggregate 10,000-13,000 t",
          (w.loc[~aggregate, "gold_tonnes"].fillna(0) <= 9000).all() and w.loc[w.iso3 == "G163", "gold_tonnes"].between(10000, 13000).all(),
          f"max country {w.loc[~aggregate, 'gold_tonnes'].max():,.0f} t; G163 {w.loc[w.iso3 == 'G163', 'gold_tonnes'].min():,.0f}-{w.loc[w.iso3 == 'G163', 'gold_tonnes'].max():,.0f} t")
    check(src, "ounces and USD values non-negative", (w[["gold_troy_oz", "gold_usd"]].fillna(0) >= 0).all().all())
    both = w.dropna(subset=["gold_troy_oz", "gold_usd"])
    both = both[both.gold_troy_oz > 1000].copy()
    both["px"] = both.gold_usd / both.gold_troy_oz
    latest = both.sort_values("date").groupby("iso3").tail(1)
    book = latest[latest.px < 500]
    check(src, "implied price (USD value / ounces) at market for most reporters: median of latest month within 1,000-10,000 USD/oz",
          1000 <= latest.px.median() <= 10000, f"median {latest.px.median():,.0f} USD/oz over {len(latest)} reporters")
    info(src, "reporters valuing gold at book / statutory value (implied price < 500 USD/oz in the latest month) - use ounces, not USD, for these",
         "; ".join(f"{r.iso3} {r.px:,.0f}" for r in book.sort_values('px').itertuples()) or "none")
    for iso in ("CHN", "RUS", "IND", "SAU", "TUR", "POL"):
        s = w[(w.iso3 == iso) & w.gold_tonnes.notna()].sort_values("date")
        if len(s):
            info(src, f"{iso} gold, tonnes", f"{s.iloc[0].period} {s.iloc[0].gold_tonnes:,.0f} -> {s.iloc[-1].period} {s.iloc[-1].gold_tonnes:,.0f} ({len(s)} months)")
        else:
            info(src, f"{iso} gold", "not in IRFCL")
    info(src, "coverage", f"{w.iso3.nunique()} reporters, {w.period.min()} -> {w.period.max()}; sectors {sorted(w.sector_code.unique())}")
    cols = ["iso3", "country", "sector_code", "sector", "period", "date", "gold_troy_oz", "gold_tonnes", "gold_usd",
            "official_reserve_assets_usd", "gold_troy_oz_reported", "flag"]
    for c in cols:
        if c not in w.columns:
            w[c] = np.nan
    return w[cols].sort_values(["iso3", "sector_code", "date"]).reset_index(drop=True)


def clean_worldbank():
    src = "D50 WDI reserves"
    files = sorted((RAW / "worldbank").glob("FI.RES.*.json"))
    if not files:
        check(src, "raw files present", False, "raw/worldbank/FI.RES.*.json missing")
        return None
    rows = []
    for p in files:
        meta, data = json.loads(p.read_text(encoding="utf-8"))
        for r in data or []:
            rows.append((r["countryiso3code"] or r["country"]["id"], r["country"]["value"], int(r["date"]), r["indicator"]["id"], r["value"]))
    df = pd.DataFrame(rows, columns=["iso3", "country", "year", "indicator", "value"])
    n_raw = int(df.value.notna().sum())
    w = df.pivot_table(index=["iso3", "country", "year"], columns="indicator", values="value").reset_index()
    w = w.rename(columns={"FI.RES.TOTL.CD": "total_reserves_usd", "FI.RES.XGLD.CD": "reserves_ex_gold_usd"})
    w["gold_usd"] = w["total_reserves_usd"] - w["reserves_ex_gold_usd"]
    w = w.dropna(subset=["total_reserves_usd", "reserves_ex_gold_usd"], how="all").sort_values(["iso3", "year"]).reset_index(drop=True)
    check(src, "every WDI observation lands in the output", n_raw == int(w[["total_reserves_usd", "reserves_ex_gold_usd"]].notna().sum().sum()), f"{n_raw}")
    neg = w[w.gold_usd < -1]
    check(src, "implied gold value never negative", neg.empty, f"{len(neg)} rows" + (f" e.g. {neg[['iso3', 'year']].head(3).values.tolist()}" if len(neg) else ""))
    info(src, "coverage", f"{w.iso3.nunique()} economies (incl. aggregates), {w.year.min()}-{w.year.max()}")
    return w


def cross_checks(irfcl, wdi):
    src = "D50 cross-check"
    if irfcl is None or wdi is None:
        return
    dec = irfcl[(irfcl.sector_code == "S1XS1311") & irfcl.period.str.endswith("-12")].dropna(subset=["gold_usd"]).copy()
    dec["year"] = dec.period.str[:4].astype(int)
    cmp = dec.merge(wdi.dropna(subset=["gold_usd"]), on=["iso3", "year"], suffixes=("_irfcl", "_wdi"))
    cmp = cmp[cmp.gold_usd_wdi > 1e8]
    rel = ((cmp.gold_usd_irfcl - cmp.gold_usd_wdi).abs() / cmp.gold_usd_wdi)
    warn(src, "IRFCL December gold value vs WDI annual implied gold value: median rel. diff < 10%", rel.median() < 0.10,
         f"{len(cmp)} country-years; median {rel.median():.1%}, 90th pct {rel.quantile(0.9):.1%} (WDI gold is at London PM fix, IRFCL at national valuation)")


# --------------------------------------------------------------------------------------
# catalog / tracker status / CHECKS.md
# --------------------------------------------------------------------------------------
def catalog_rows(name, df, keys, datecol, valcol):
    if df is None or df.empty:
        return []
    g = df.dropna(subset=[valcol]).groupby(keys, dropna=False)
    rows = []
    for k, s in g:
        k = k if isinstance(k, tuple) else (k,)
        rows.append({"file": name, "series": " | ".join(str(x) for x in k), "first": str(s[datecol].min())[:10],
                     "last": str(s[datecol].max())[:10], "n_obs": int(len(s))})
    return rows


def tracker_status(outputs):
    base = "data/currency_markets"
    rows = [
        ("D43", "Cleaned" if outputs.get("imf_invoicing_currency.csv") is not None else "Blocked / unavailable",
         f"{base}/clean/imf_invoicing_currency.csv (Boz et al. dataset via Mendeley Data mirror; raw {base}/raw/imf_invoicing/all_countries_update.dta). imf.org blocks scripted download of the same file. Annual 1990-2019 only."),
        ("D44", "Cleaned" if outputs.get("safe_crossborder_by_currency.csv") is not None else "Blocked / unavailable",
         f"{base}/clean/safe_crossborder_by_currency.csv + safe_rmb_share.csv (SAFE monthly cross-border receipts/payments by currency, 2010-01 onwards; raw {base}/raw/safe/). PBoC RMB Internationalization Report PDFs in {base}/raw/pboc_rmb_report/ (not parsed)."),
        ("D45", "Cleaned" if outputs.get("imf_cofer.csv") is not None else "Blocked / unavailable",
         f"{base}/clean/imf_cofer.csv (IMF SDMX 3.0 API api.imf.org, dataflow IMF.STA/COFER; raw {base}/raw/imf_cofer/cofer_data.json)"),
        ("D46", "Cleaned" if outputs.get("swift_rmb_tracker.csv") is not None else "Blocked / unavailable",
         f"swift.com returns 403 to scripts and the monthly PDFs need a login: hand-collect per {base}/raw/swift_rmb_tracker/README.md"),
        ("D47", "Cleaned" if outputs.get("cips_volumes.csv") is not None else "Blocked / unavailable",
         f"{base}/clean/cips_volumes.csv (CIPS statistics PDFs, English + Chinese; raw {base}/raw/cips/). Monthly for the current year, annual 2015 onwards."),
        ("D48", "Cleaned" if outputs.get("bis_fx_turnover.csv") is not None else "Blocked / unavailable",
         f"{base}/clean/bis_fx_turnover.csv + bis_fx_turnover_by_currency.csv (BIS bulk WS_DER_OTC_TOV; raw {base}/raw/bis_triennial/). Triennial 1989-2025."),
        ("D49", "Cleaned" if outputs.get("tic_major_foreign_holders.csv") is not None else "Blocked / unavailable",
         f"{base}/clean/tic_major_foreign_holders.csv (ticdata.treasury.gov slt_table5.txt + mfhhis01.txt; raw {base}/raw/tic/). Monthly 2000 onwards; ~45 holders to the last complete year, top ~20 after."),
        ("D50", "Cleaned" if outputs.get("imf_irfcl_gold_reserves.csv") is not None else "Blocked / unavailable",
         f"{base}/clean/imf_irfcl_gold_reserves.csv (IMF IRFCL monthly gold, backup source) + wb_gold_reserves_annual.csv (WDI). gold.org Excel needs a free Goldhub login: see {base}/raw/wgc_gold/README.md"),
    ]
    return pd.DataFrame(rows, columns=["ID", "Status", "Saved file / location"]).assign(**{"Date retrieved": TODAY})[
        ["ID", "Status", "Date retrieved", "Saved file / location"]]


def write_checks_md(outputs, failed):
    lines = [f"# Currency markets (D43-D50) - clean checks, {TODAY}", "",
             "Result: **" + ("FAILED - data files not written" if failed else "ALL PASSED") + "**", "",
             "| source | check | status | detail |", "|---|---|---|---|"]
    for s, n, st, d in CHECKS:
        lines.append(f"| {s} | {n} | {st} | {d.replace('|', '/')} |")
    lines += ["", "## Output files", "", "| file | rows | columns |", "|---|---|---|"]
    for name, df in outputs.items():
        if df is not None:
            lines.append(f"| {name} | {len(df):,} | {', '.join(df.columns)} |")
    CLEAN.mkdir(parents=True, exist_ok=True)
    (CLEAN / "CHECKS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    outputs = {}
    outputs["imf_invoicing_currency.csv"] = clean_invoicing()
    outputs["safe_crossborder_by_currency.csv"], outputs["safe_rmb_share.csv"] = clean_safe()
    outputs["imf_cofer.csv"] = clean_cofer()
    outputs["swift_rmb_tracker.csv"] = clean_swift()
    outputs["cips_volumes.csv"] = clean_cips()
    outputs["bis_fx_turnover.csv"], outputs["bis_fx_turnover_by_currency.csv"] = clean_bis()
    outputs["tic_major_foreign_holders.csv"] = clean_tic()
    outputs["imf_irfcl_gold_reserves.csv"] = clean_irfcl()
    outputs["wb_gold_reserves_annual.csv"] = clean_worldbank()
    cross_checks(outputs["imf_irfcl_gold_reserves.csv"], outputs["wb_gold_reserves_annual.csv"])

    cat = []
    cat += catalog_rows("imf_invoicing_currency.csv", outputs["imf_invoicing_currency.csv"], ["iso3", "flow", "currency"], "year", "share_pct")
    cat += catalog_rows("safe_crossborder_by_currency.csv", outputs["safe_crossborder_by_currency.csv"], ["unit_currency", "freq", "flow", "item"], "period", "value")
    cat += catalog_rows("imf_cofer.csv", outputs["imf_cofer.csv"], ["country_code", "indicator_code", "transformation", "currency_code", "freq"], "period", "value")
    cat += catalog_rows("cips_volumes.csv", outputs["cips_volumes.csv"], ["freq"], "period", "amount_bn_cny")
    cat += catalog_rows("bis_fx_turnover_by_currency.csv", outputs["bis_fx_turnover_by_currency.csv"], ["currency"], "year", "turnover_usd_mn")
    cat += catalog_rows("tic_major_foreign_holders.csv", outputs["tic_major_foreign_holders.csv"], ["row_type", "country"], "period", "holdings_usd_bn")
    cat += catalog_rows("imf_irfcl_gold_reserves.csv", outputs["imf_irfcl_gold_reserves.csv"], ["iso3", "sector_code"], "period", "gold_troy_oz")
    cat += catalog_rows("wb_gold_reserves_annual.csv", outputs["wb_gold_reserves_annual.csv"], ["iso3"], "year", "gold_usd")
    outputs["series_catalog.csv"] = pd.DataFrame(cat)
    outputs["tracker_status.csv"] = tracker_status(outputs)

    failed = [c for c in CHECKS if c[2] == "FAIL"]
    write_checks_md(outputs, failed)
    for s, n, st, d in CHECKS:
        if st != "PASS":
            print(f"{st:4} [{s}] {n}: {d}")
    print(f"\n{len(CHECKS)} checks: {sum(c[2] == 'PASS' for c in CHECKS)} PASS, {sum(c[2] == 'WARN' for c in CHECKS)} WARN, "
          f"{sum(c[2] == 'INFO' for c in CHECKS)} INFO, {len(failed)} FAIL")
    if failed:
        print(f"FAILED: data files not written; see {CLEAN / 'CHECKS.md'}")
        return 1
    CLEAN.mkdir(parents=True, exist_ok=True)
    for name, df in outputs.items():
        if df is None:
            continue
        df.to_csv(CLEAN / name, index=False, date_format="%Y-%m-%d")
        print(f"  wrote {name:40} {len(df):>9,} rows")
    print(f"ALL PASSED; see {CLEAN / 'CHECKS.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
