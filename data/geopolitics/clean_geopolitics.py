"""Clean the raw *Geopolitics* downloads (tracker rows D37-D42) in ./raw into tidy CSVs in ./clean, and run
sanity checks that must all pass before anything is written.

Outputs (data/geopolitics/clean/)
  gpr.csv                    D37  Caldara & Iacoviello GPR: monthly (1900->) and daily (1985->) indexes, long format,
                                  one row per series x date (GPR, GPRT threats, GPRA acts, GPRH historical, country GPRC_*)
  ofac_recent_actions.csv    D39  one row per OFAC "recent action" (2010->): date, title, category, press-release link,
                                  sanctions programme tags found on the page, counts of SDN entries added/removed,
                                  Iran / Russia / Venezuela flags, narrative text
  ofac_sdn.csv               D39  the current SDN list snapshot (one row per entry: name, type, programme, remarks)
  baumeister_hamilton.csv    D40  BH (2019) structural shocks: oil supply, economic activity, oil consumption demand,
                                  oil inventory demand (monthly 1975-02->) + the world IP index input, with vintage
  kanzig.csv                 D41  Kaenzig (2021) oil supply surprises (daily, on OPEC announcement dates, by futures
                                  contract + first principal component) and monthly surprise / news-shock series,
                                  full and pre-Covid samples, latest vintage
  portwatch_chokepoints.csv  D42  IMF PortWatch daily transit counts and capacity by vessel type, 28 chokepoints
                                  (Strait of Hormuz, Bab el-Mandeb, Suez ...), 2019-01-01->
  portwatch_disruptions.csv  D42  PortWatch disruption events (type, dates, affected ports)
  series_catalog.csv              one row per series in every file: coverage and observation counts
  tracker_status.csv              suggested Status / Date retrieved / Saved file values for the tracker workbook
  CHECKS.md                       every check with PASS / WARN / FAIL / INFO and details

Any FAIL aborts the write of the data files (CHECKS.md is still written) and exits 1.
Run `python data/geopolitics/download_geopolitics.py` first.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent          # data/geopolitics
RAW = HERE / "raw"
CLEAN = HERE / "clean"
ROOT = HERE.parents[1]
CATEGORY = "Geopolitics"
TODAY = date.today().isoformat()

# --------------------------------------------------------------------------------------
# check registry (same semantics as data/fundamentals/clean_fundamentals.py)
# --------------------------------------------------------------------------------------
CHECKS: list[tuple[str, str, str, str]] = []   # (source, name, status, detail)


def check(source: str, name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((source, name, "PASS" if ok else "FAIL", str(detail)))
    return bool(ok)


def warn(source: str, name: str, ok: bool, detail: str = "") -> bool:
    """A failure is a WARN: shown prominently, does not block writing. Only for coverage gaps caused by the
    source's access limits, where every file that IS present passed its own checks."""
    CHECKS.append((source, name, "PASS" if ok else "WARN", str(detail)))
    return bool(ok)


def info(source: str, name: str, detail: str = "") -> None:
    CHECKS.append((source, name, "INFO", str(detail)))


def contiguous(dates: pd.Series, freq: str) -> tuple[bool, str]:
    """freq: 'D' (every calendar day), 'B' (business days, gaps <= 4 days allowed), 'MS', 'YS'."""
    d = pd.to_datetime(pd.Series(dates).drop_duplicates()).sort_values()
    if d.empty:
        return False, "no dates"
    if freq == "B":
        gaps = d.diff().dt.days.dropna()
        bad = gaps[gaps > 4]
        return bad.empty, f"{d.iloc[0].date()} .. {d.iloc[-1].date()}, {len(d)} days, {len(bad)} gaps > 4 days"
    expected = pd.date_range(d.iloc[0], d.iloc[-1], freq=freq)
    missing = expected.difference(d)
    detail = f"{d.iloc[0].date()} .. {d.iloc[-1].date()}, {len(d)} periods, {len(missing)} missing"
    if len(missing):
        detail += " (" + ", ".join(str(x.date()) for x in missing[:5]) + (" ..." if len(missing) > 5 else "") + ")"
    return missing.empty, detail


def manifest() -> dict:
    p = RAW / "manifest.json"
    if not p.exists():
        sys.exit(f"{p.relative_to(ROOT).as_posix()} not found: run download_geopolitics.py first")
    return json.loads(p.read_text(encoding="utf-8"))


def file_vintage(src: str, name: str, m: dict) -> str:
    """YYYY-MM-DD the raw file was downloaded (from the manifest), else today."""
    for f in m.get("sources", {}).get(src, {}).get("files", []):
        if f.get("file") == f"{src}/{name}" and f.get("downloaded_at"):
            return f["downloaded_at"][:10]
    return TODAY


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


# --------------------------------------------------------------------------------------
# D37  GPR
# --------------------------------------------------------------------------------------
def clean_gpr(m: dict, src: str = "gpr") -> pd.DataFrame | None:
    files = {"monthly": RAW / src / "data_gpr_export.xls", "daily": RAW / src / "data_gpr_daily_recent.xls"}
    if not check(src, "raw files present", all(p.exists() for p in files.values()),
                 ", ".join(p.name for p in files.values())):
        return None
    out, raw_cells = [], 0
    for freq, path in files.items():
        df = pd.read_excel(path, sheet_name=0)
        labels = (df[["var_name", "var_label"]].dropna(subset=["var_name"]).set_index("var_name")["var_label"]
                  .astype(str).to_dict()) if "var_name" in df.columns else {}
        datecol = "month" if freq == "monthly" else "date"
        drop = {datecol, "var_name", "var_label", "DAY", "event"}
        series = [c for c in df.columns if c not in drop]
        d = df[[datecol] + series + (["event"] if "event" in df.columns else [])].copy()
        d = d[d[datecol].notna()]
        d[datecol] = pd.to_datetime(d[datecol])
        num = d[series].apply(pd.to_numeric, errors="coerce")
        check(src, f"{freq}: every series column is numeric", num.notna().sum().sum() == d[series].notna().sum().sum(),
              f"{len(series)} series")
        raw_cells += int(num.notna().sum().sum())
        d[series] = num
        long = d.melt(id_vars=[datecol] + (["event"] if "event" in d.columns else []), value_vars=series,
                      var_name="series_id", value_name="value").dropna(subset=["value"])
        long = long.rename(columns={datecol: "date"})
        long["series_name"] = long["series_id"].map(labels).fillna(long["series_id"])
        long["freq"] = "M" if freq == "monthly" else "D"
        long["file"] = path.name
        if "event" not in long.columns:
            long["event"] = ""
        long["event"] = long["event"].fillna("").astype(str)
        out.append(long)
        ok, detail = contiguous(d[datecol], "MS" if freq == "monthly" else "D")
        check(src, f"{freq}: dates contiguous", ok, detail)
        first, last = d[datecol].min(), d[datecol].max()
        exp_first = pd.Timestamp("1900-01-01") if freq == "monthly" else pd.Timestamp("1985-01-01")
        check(src, f"{freq}: coverage starts {exp_first.date()} (tracker: 1900 hist / 1985)", first == exp_first, str(first.date()))
        lag_ok = (pd.Timestamp(TODAY) - last).days <= (75 if freq == "monthly" else 14)
        check(src, f"{freq}: last observation recent", lag_ok, f"last {last.date()}, today {TODAY}")
        # index normalisation: GPR (1985:2019 = 100), GPRH (1900:2019 = 100), GPRD (1985:2019 = 100)
        base = d.set_index(datecol)
        for sid, lo, hi in (("GPR", "1985-01-01", "2019-12-31"), ("GPRH", "1900-01-01", "2019-12-31"),
                            ("GPRT", "1985-01-01", "2019-12-31"), ("GPRA", "1985-01-01", "2019-12-31"),
                            ("GPRD", "1985-01-01", "2019-12-31"), ("GPRD_ACT", "1985-01-01", "2019-12-31"),
                            ("GPRD_THREAT", "1985-01-01", "2019-12-31")):
            if sid in base.columns:
                mean = base.loc[lo:hi, sid].mean()
                check(src, f"{freq}: {sid} averages 100 over its base period {lo[:4]}-{hi[:4]}", abs(mean - 100) < 2.5, f"mean {mean:.2f}")
        neg = (num < 0).sum().sum()
        check(src, f"{freq}: no negative values (indexes, shares, counts)", neg == 0, f"{neg} negative cells")
    df = pd.concat(out, ignore_index=True)
    df.insert(0, "tracker_ids", "D37")
    df.insert(1, "source", src)
    df["vintage"] = file_vintage(src, "data_gpr_export.xls", m)
    df = df[["tracker_ids", "source", "file", "freq", "series_id", "series_name", "date", "value", "event", "vintage"]]
    check(src, "every numeric raw cell captured", len(df) == raw_cells, f"{raw_cells:,} numeric cells -> {len(df):,} rows")
    check(src, "no duplicate (file, series_id, date)", not df.duplicated(["file", "series_id", "date"]).any())
    # monthly GPR vs monthly mean of daily GPRD: same construction (10 newspapers), should co-move strongly
    mon = df[(df.freq == "M") & (df.series_id == "GPR")].set_index("date")["value"]
    day = df[(df.freq == "D") & (df.series_id == "GPRD")].set_index("date")["value"].resample("MS").mean()
    both = pd.concat([mon, day], axis=1, keys=["GPR", "GPRD_mean"]).dropna()
    corr = both["GPR"].corr(both["GPRD_mean"])
    check(src, "monthly GPR vs monthly mean of daily GPRD: correlation > 0.9", corr > 0.9, f"corr {corr:.3f} over {len(both)} months")
    info(src, "country indexes", ", ".join(sorted(s[5:] for s in df.series_id.unique() if s.startswith("GPRC_"))))
    info(src, "daily rows carrying an event label", f"{(df[df.freq == 'D'].drop_duplicates('date')['event'] != '').sum()} dates")
    return df.sort_values(["freq", "series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D39  OFAC recent actions + SDN list
# --------------------------------------------------------------------------------------
RE_TITLE = re.compile(r'<span class="treas-page-title">(.*?)</span>', re.S)
RE_RELEASE = re.compile(r'field--name-field-release-date.*?<div class="field__item">\s*([\d/]+)\s*</div>', re.S)
RE_PRESS = re.compile(r'field--name-field-press-release-link.*?<div class="field__item"><a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
RE_BODY = re.compile(r'field--name-field-body.*?<div class="field__item">(.*?)</div>\s*</div>\s*(?:</article>|<div class="field)', re.S)
RE_BODY_FALLBACK = re.compile(r'field--name-field-body.*?<div class="field__item">(.*)</article>', re.S)
RE_PROGRAM = re.compile(r"\[([A-Z][A-Z0-9\-]{2,})\]")
RE_HEAD = re.compile(r"<h[2-5][^>]*>(.*?)</h[2-5]>", re.S)
RE_CHANGE = re.compile(r"the following[^<]*?(?:have been|has been|are being|is being)?\s*(added|removed|deleted|updated|changed|amended)", re.I)
KEYWORDS = {"iran": r"\biran", "russia": r"\brussia|\bukraine|\bbelarus", "venezuela": r"\bvenezuela",
            "oil_shipping": r"\boil\b|\bpetroleum|\btanker|\bshadow fleet|\bvessel|\bshipping|\bmaritime|\bcrude"}


def text_of(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|div|li|h[1-6])>", "\n", s)
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def parse_action(page: str) -> dict:
    title = RE_TITLE.search(page)
    rel = RE_RELEASE.search(page)
    press = RE_PRESS.search(page)
    body = RE_BODY.search(page) or RE_BODY_FALLBACK.search(page)
    body_html = body.group(1) if body else ""
    # narrative = everything before the first heading (the SDN entry lists follow the headings)
    first_head = RE_HEAD.search(body_html)
    narrative_html = body_html[:first_head.start()] if first_head else body_html
    narrative = re.sub(r"[ \t]+", " ", text_of(narrative_html))
    narrative = re.sub(r"\s*\n\s*", "\n", narrative).strip()
    # SDN change counts: entries listed under "The following ... have been added / removed / updated" headings
    counts = {"added": 0, "removed": 0, "updated": 0}
    heads = list(RE_HEAD.finditer(body_html))
    for i, h in enumerate(heads):
        head_text = text_of(h.group(1)).strip()
        kind = RE_CHANGE.search(head_text)
        if not kind:
            continue
        k = kind.group(1).lower()
        k = {"deleted": "removed", "changed": "updated", "amended": "updated"}.get(k, k)
        section = body_html[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(body_html)]
        entries = [e for e in re.split(r"(?:<br\s*/?>\s*){2,}|</p>|</li>", section) if text_of(e).strip()]
        counts[k] += len(entries)
    programs = sorted(set(RE_PROGRAM.findall(body_html)))
    press_url = press.group(1) if press else ""
    if press_url.startswith("/"):
        press_url = "https://ofac.treasury.gov" + press_url
    return {"page_title": html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title.group(1)))).strip() if title else "",
            "release_date": rel.group(1) if rel else "",
            "press_release_url": press_url,
            "press_release_title": html.unescape(re.sub(r"<[^>]+>", "", press.group(2))).strip() if press else "",
            "programs": ";".join(programs), "n_programs": len(programs),
            "n_sdn_added": counts["added"], "n_sdn_removed": counts["removed"], "n_sdn_updated": counts["updated"],
            "body_text": narrative, "body_chars": len(text_of(body_html))}


def clean_ofac(m: dict, src: str = "ofac") -> pd.DataFrame | None:
    idx_path = RAW / src / "index.json"
    if not check(src, "listing index present (raw/ofac/index.json)", idx_path.exists()):
        return None
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    actions = idx["actions"]
    info(src, "listing crawl", f"{idx.get('total_reported')} results reported by the site, {idx.get('pages')} pages, "
                               f"{len(actions)} unique actions indexed, crawled {idx.get('crawled_at', '')[:19]}")
    check(src, "listing complete: unique actions >= results reported - 10", len(actions) >= (idx.get("total_reported") or 0) - 10,
          f"{len(actions)} vs {idx.get('total_reported')}")
    rows, missing, unparsed = [], [], []
    for a in actions:
        p = RAW / src / "actions" / f"{a['slug']}.html"
        if not p.exists():
            missing.append(a["slug"])
            continue
        parsed = parse_action(p.read_text(encoding="utf-8", errors="replace"))
        if not parsed["release_date"] and not a["date_text"]:
            unparsed.append(a["slug"])
            continue
        rows.append({**a, **parsed})
    warn(src, "every indexed action has its page on disk", not missing,
         f"{len(missing)} missing of {len(actions)} (re-run download_geopolitics.py --only ofac)" + (f": {missing[:5]}" if missing else ""))
    check(src, "every page yields a release date", not unparsed, f"{len(unparsed)} pages without a date: {unparsed[:5]}")
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["release_date"], format="%m/%d/%Y", errors="coerce")
    df["listing_date"] = pd.to_datetime(df["date_text"], format="%B %d, %Y", errors="coerce")
    df["date"] = df["date"].fillna(df["listing_date"])
    check(src, "every action has a parseable date", df["date"].notna().all(), f"{df['date'].isna().sum()} unparsed")
    both = df.dropna(subset=["listing_date"])
    diff = (both["date"] != both["listing_date"]).sum()
    check(src, "page release date agrees with the listing date", diff == 0, f"{diff} differ of {len(both)}")
    has_pt = df["page_title"] != ""
    norm = lambda s: s.str.lower().str.replace(r"[^a-z0-9]+", "", regex=True)  # noqa: E731
    same = (norm(df.loc[has_pt, "page_title"]) == norm(df.loc[has_pt, "title"])).mean()
    check(src, "page title agrees with the listing title (>= 95%)", same >= 0.95, f"{same:.1%} of {int(has_pt.sum())} pages with a title")
    df["title"] = df["title"].where(df["title"] != "", df["page_title"])
    check(src, "no duplicate slug", not df["slug"].duplicated().any())
    check(src, "every page has body text", (df["body_chars"] > 0).all(), f"{(df['body_chars'] == 0).sum()} empty bodies")
    check(src, "coverage: actions from 2010 or earlier to this month", df["date"].min().year <= 2010 and
          (pd.Timestamp(TODAY) - df["date"].max()).days <= 45, f"{df['date'].min().date()} .. {df['date'].max().date()}")
    cats = sorted(df["category"].unique())
    check(src, "categories are the site's five sections", set(cats) <= {"Sanctions List Updates", "General Licenses",
          "Enforcement Actions", "Regulations and Guidance", "Miscellaneous", ""}, ", ".join(cats))
    for k, pat in KEYWORDS.items():
        hay = (df["title"] + " " + df["programs"].str.replace(";", " ") + " " + df["body_text"].str[:600])
        df[f"is_{k}"] = hay.str.contains(pat, case=False, regex=True).astype(int)
    df["year"] = df["date"].dt.year
    info(src, "actions per year", ", ".join(f"{y}: {n}" for y, n in df.groupby("year").size().items()))
    info(src, "Iran / Russia / Venezuela / oil-shipping flagged actions",
         f"{df.is_iran.sum()} / {df.is_russia.sum()} / {df.is_venezuela.sum()} / {df.is_oil_shipping.sum()} of {len(df)}")
    info(src, "SDN entries counted on the pages", f"added {df.n_sdn_added.sum():,}, removed {df.n_sdn_removed.sum():,}, updated {df.n_sdn_updated.sum():,}")
    top = df["programs"].str.split(";").explode()
    top = top[top != ""].value_counts().head(12)
    info(src, "most frequent programme tags", ", ".join(f"{k} ({v})" for k, v in top.items()))
    check(src, "programme tags found on most Sanctions List Updates pages",
          (df.loc[df.category == "Sanctions List Updates", "n_programs"] > 0).mean() > 0.8,
          f"{(df.loc[df.category == 'Sanctions List Updates', 'n_programs'] > 0).mean():.1%}")
    out = df[["slug", "url", "date", "title", "category", "press_release_url", "press_release_title", "programs", "n_programs",
              "n_sdn_added", "n_sdn_removed", "n_sdn_updated", "is_iran", "is_russia", "is_venezuela", "is_oil_shipping",
              "body_text", "body_chars"]].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.insert(0, "tracker_ids", "D39")
    out.insert(1, "source", src)
    out["body_text"] = out["body_text"].str.replace("\r", "", regex=False)
    return out.sort_values(["date", "slug"]).reset_index(drop=True)


SDN_COLS = ["ent_num", "sdn_name", "sdn_type", "program", "title", "call_sign", "vess_type", "tonnage", "grt",
            "vess_flag", "vess_owner", "remarks"]


def clean_ofac_sdn(m: dict, src: str = "ofac") -> pd.DataFrame | None:
    p = RAW / src / "sdn" / "sdn.csv"
    if not check(src + "_sdn", "raw sdn.csv present", p.exists()):
        return None
    df = pd.read_csv(p, header=None, names=SDN_COLS, dtype=str, keep_default_na=False, encoding="utf-8", encoding_errors="replace")
    check(src + "_sdn", "12 columns as documented (sdn.csv layout)", df.shape[1] == 12, f"{df.shape}")
    df = df.apply(lambda s: s.str.strip())
    num = pd.to_numeric(df["ent_num"], errors="coerce")
    blank = num.isna() & (df.drop(columns="ent_num") == "").all(axis=1)   # trailing terminator row(s)
    info(src + "_sdn", "blank trailing rows dropped", f"{int(blank.sum())} (first column {df.loc[blank, 'ent_num'].map(repr).tolist()[:3]})")
    df = df[~blank].replace({"-0-": ""})       # "-0-" is OFAC's null token
    df["ent_num"] = num[~blank]
    check(src + "_sdn", "ent_num numeric and unique", df["ent_num"].notna().all() and not df["ent_num"].duplicated().any(),
          f"{df['ent_num'].isna().sum()} non-numeric, {df['ent_num'].duplicated().sum()} duplicates")
    check(src + "_sdn", "plausible size (> 10,000 entries)", len(df) > 10_000, f"{len(df):,} entries")
    check(src + "_sdn", "every entry has a programme", (df["program"] != "").all(), f"{(df['program'] == '').sum()} blank")
    df["ent_num"] = df["ent_num"].astype(int)
    df.insert(0, "tracker_ids", "D39")
    df.insert(1, "source", src)
    df["snapshot"] = file_vintage(src, "sdn/sdn.csv", m)
    prog = df["program"].str.split(r"\]\s*\[|;|\s{2,}").explode().str.strip("[] ")
    info(src + "_sdn", "entries by type", ", ".join(f"{k}: {v}" for k, v in df["sdn_type"].value_counts().items()))
    info(src + "_sdn", "largest programmes", ", ".join(f"{k} ({v})" for k, v in prog.value_counts().head(10).items()))
    return df.sort_values("ent_num").reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D40  Baumeister & Hamilton
# --------------------------------------------------------------------------------------
BH_FILES = {   # file -> sheet index, what the columns are
    "BH2_supply_shocks.xlsx": "structural shocks",
    "BH2_demand_shocks.xlsx": "structural shocks",
    "OECD_plus6_industrial_production.xlsx": "VAR input",
}


def sheet_to_long(path: Path, sheet=0) -> tuple[pd.DataFrame, int]:
    """Author-formatted sheet: a header row of series names above a block whose first column is a date.
    Returns (long df with series_name/date/value, number of numeric cells)."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    dates = pd.to_datetime(raw.iloc[:, 0], errors="coerce")
    first = int(dates.notna().idxmax())
    header = raw.iloc[first - 1]
    cols = [c for c in raw.columns[1:] if pd.notna(header[c]) and pd.to_numeric(raw.iloc[first:, c], errors="coerce").notna().any()]
    block = raw.loc[dates.notna(), [raw.columns[0]] + cols].copy()
    block.columns = ["date"] + [str(header[c]).strip() for c in cols]
    block["date"] = pd.to_datetime(block["date"])
    num = block.drop(columns="date").apply(pd.to_numeric, errors="coerce")
    n_cells = int(num.notna().sum().sum())
    long = pd.concat([block[["date"]], num], axis=1).melt(id_vars="date", var_name="series_name", value_name="value").dropna(subset=["value"])
    return long, n_cells


def clean_baumeister_hamilton(m: dict, src: str = "baumeister_hamilton") -> pd.DataFrame | None:
    paths = {n: RAW / src / n for n in BH_FILES}
    if not check(src, "raw files present", all(p.exists() for p in paths.values()), ", ".join(BH_FILES)):
        return None
    out, cells = [], 0
    for name, kind in BH_FILES.items():
        long, n = sheet_to_long(paths[name])
        cells += n
        long["file"] = name
        long["kind"] = kind
        long["vintage"] = file_vintage(src, name, m)
        out.append(long)
        info(src, f"{name}: series", ", ".join(long["series_name"].unique()))
    df = pd.concat(out, ignore_index=True)
    df["series_id"] = df["series_name"].map(slug)
    df["unit"] = np.where(df["kind"] == "structural shocks", "standard deviations (posterior median)", "index")
    df.insert(0, "tracker_ids", "D40")
    df.insert(1, "source", src)
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df = df[["tracker_ids", "source", "file", "kind", "series_id", "series_name", "unit", "date", "value", "vintage"]]
    check(src, "every numeric raw cell captured", len(df) == cells, f"{cells:,} cells -> {len(df):,} rows")
    check(src, "no duplicate (series_id, date)", not df.duplicated(["series_id", "date"]).any())
    shocks = df[df.kind == "structural shocks"]
    spans = shocks.groupby("series_id")["date"].agg(["min", "max", "count"])
    check(src, "four structural shock series", len(spans) == 4, ", ".join(spans.index))
    check(src, "shock series share one sample", spans["min"].nunique() == 1 and spans["max"].nunique() == 1,
          f"{spans['min'].min().date()} .. {spans['max'].max().date()}")
    for sid, g in df.groupby("series_id"):
        ok, detail = contiguous(g["date"], "MS")
        check(src, f"{sid}: months contiguous", ok, detail)
    check(src, "coverage: shocks start 1975 (tracker: 1975)", spans["min"].min().year == 1975, str(spans["min"].min().date()))
    check(src, "shocks updated within the last 12 months", (pd.Timestamp(TODAY) - spans["max"].max()).days < 366, str(spans["max"].max().date()))
    for sid, g in shocks.groupby("series_id"):
        mu, sd = g["value"].mean(), g["value"].std()
        # posterior-median shocks are centred but not unit-variance (consumption demand shock sd ~ 3)
        check(src, f"{sid}: shock centred and finite (|mean| < 0.3, 0.3 < sd < 5)", abs(mu) < 0.3 and 0.3 < sd < 5, f"mean {mu:.3f}, sd {sd:.3f}")
    ip = df[df.kind == "VAR input"]
    check(src, "world IP index positive", (ip["value"] > 0).all(), f"{ip['value'].min():.2f} .. {ip['value'].max():.2f}")
    # cross-vintage comparison with the 2023 vintage shipped in market-based_oil_price_shocks.xlsx
    mb = RAW / src / "market-based_oil_price_shocks.xlsx"
    if mb.exists():
        try:
            old, _ = sheet_to_long(mb, sheet="fundamental oil market shocks")
            old["series_id"] = old["series_name"].map(slug)
            old["date"] = old["date"].dt.to_period("M").dt.to_timestamp()
            for sid in spans.index:
                a = shocks[shocks.series_id == sid].set_index("date")["value"]
                b = old[old.series_id == sid].set_index("date")["value"]
                both = pd.concat([a, b], axis=1).dropna()
                if len(both):
                    info(src, f"{sid}: correlation with the 2023 vintage (re-estimation drift)", f"{both.iloc[:, 0].corr(both.iloc[:, 1]):.3f} over {len(both)} months")
        except Exception as e:  # noqa: BLE001
            info(src, "2023-vintage comparison skipped", str(e))
    return df.sort_values(["kind", "series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D41  Kaenzig oil supply news shocks
# --------------------------------------------------------------------------------------
def clean_kanzig(m: dict, src: str = "kanzig") -> pd.DataFrame | None:
    files = sorted((RAW / src).glob("oilSupplyNewsShocks_*.xlsx"))
    if not check(src, "raw vintage files present", bool(files), f"{len(files)} files"):
        return None
    latest = files[-1]
    vintage = re.search(r"(\d{4}M\d{2})", latest.name).group(1)
    info(src, "vintages on disk", ", ".join(re.search(r"(\d{4}M\d{2})", f.name).group(1) for f in files) + f"; cleaned: {vintage}")
    xl = pd.ExcelFile(latest)
    check(src, "four sheets as documented in the README", set(xl.sheet_names) == {"Daily", "Monthly", "Daily (pre-Covid)", "Monthly (pre-Covid)"},
          ", ".join(xl.sheet_names))
    out, cells = [], 0
    for sheet in xl.sheet_names:
        sample = "pre_covid" if "pre-Covid" in sheet else "full"
        df = xl.parse(sheet)
        if sheet.startswith("Daily"):
            df = df.rename(columns={df.columns[0]: "date"})
            df["date"] = pd.to_datetime(df["date"])
            names = {c: f"surprise_{slug(c)}" for c in df.columns if c != "date"}
            long = df.melt(id_vars="date", var_name="series_name", value_name="value")
            long["series_id"] = long["series_name"].map(names)
            long["freq"] = "D"
            long["unit"] = "percent (futures price surprise)"
            check(src, f"{sheet}: announcement dates unique", not df["date"].duplicated().any(), f"{len(df)} dates {df['date'].min().date()} .. {df['date'].max().date()}")
        else:
            df = df.rename(columns={df.columns[0]: "date"})
            df["date"] = pd.to_datetime(df["date"].astype(str), format="%YM%m")
            ids = {"Oil supply surprise series": "monthly_surprise", "Oil supply news shock": "news_shock"}
            check(src, f"{sheet}: expected columns", set(ids) <= set(df.columns), ", ".join(map(str, df.columns)))
            long = df.melt(id_vars="date", var_name="series_name", value_name="value")
            long["series_id"] = long["series_name"].map(ids).fillna(long["series_name"].map(slug))
            long["freq"] = "M"
            long["unit"] = np.where(long["series_id"] == "news_shock", "standard deviations (VAR shock)", "percent (futures price surprise)")
            ok, detail = contiguous(df["date"], "MS")
            check(src, f"{sheet}: months contiguous", ok, detail)
        num = pd.to_numeric(long["value"], errors="coerce")
        cells += int(pd.to_numeric(df.drop(columns="date").stack(), errors="coerce").notna().sum())
        long["value"] = num
        long = long.dropna(subset=["value"])
        long["sample"] = sample
        long["sheet"] = sheet
        out.append(long)
    df = pd.concat(out, ignore_index=True)
    df.insert(0, "tracker_ids", "D41")
    df.insert(1, "source", src)
    df["vintage"] = vintage
    df["file"] = latest.name
    df = df[["tracker_ids", "source", "file", "vintage", "sample", "freq", "series_id", "series_name", "unit", "date", "value"]]
    check(src, "every numeric raw cell captured", len(df) == cells, f"{cells:,} cells -> {len(df):,} rows")
    check(src, "no duplicate (sample, series_id, date)", not df.duplicated(["sample", "series_id", "date"]).any())
    full_m = df[(df["sample"] == "full") & (df.freq == "M")]
    check(src, "monthly series start 1975 (tracker: 1983 daily / 1975 monthly)", full_m["date"].min() == pd.Timestamp("1975-01-01"), str(full_m["date"].min().date()))
    check(src, "latest vintage month equals the last monthly observation", full_m["date"].max().strftime("%YM%m") == vintage, str(full_m["date"].max().date()))
    for sample in ("full", "pre_covid"):
        d = df[df["sample"] == sample]
        daily_pc = d[(d.freq == "D") & (d.series_id == "surprise_pc")].set_index("date")["value"].resample("MS").sum()
        monthly = d[(d.freq == "M") & (d.series_id == "monthly_surprise")].set_index("date")["value"]
        both = pd.concat([monthly, daily_pc.reindex(monthly.index).fillna(0)], axis=1, keys=["monthly", "sum_daily_pc"])
        mx = (both["monthly"] - both["sum_daily_pc"]).abs().max()
        check(src, f"{sample}: monthly surprise = sum of daily PC surprises in the month", mx < 1e-6, f"max |diff| {mx:.2e} over {len(both)} months")
        ns = d[(d.freq == "M") & (d.series_id == "news_shock")]["value"]
        check(src, f"{sample}: news shock standardised (|mean| < 0.3, 0.5 < sd < 2.5)", abs(ns.mean()) < 0.3 and 0.5 < ns.std() < 2.5, f"mean {ns.mean():.3f}, sd {ns.std():.3f}")
    n_dates = df[(df["sample"] == "full") & (df.freq == "D")]["date"].nunique()
    info(src, "OPEC announcement dates in the full sample (event-study list)", f"{n_dates} dates, "
         f"{df[(df['sample'] == 'full') & (df.freq == 'D')]['date'].min().date()} .. {df[(df['sample'] == 'full') & (df.freq == 'D')]['date'].max().date()}")
    return df.sort_values(["sample", "freq", "series_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# D42  IMF PortWatch
# --------------------------------------------------------------------------------------
PW_COUNTS = ["n_container", "n_dry_bulk", "n_general_cargo", "n_roro", "n_tanker", "n_cargo", "n_total"]
PW_CAP = ["capacity_container", "capacity_dry_bulk", "capacity_general_cargo", "capacity_roro", "capacity_tanker", "capacity_cargo", "capacity"]


def clean_portwatch(m: dict, src: str = "portwatch") -> pd.DataFrame | None:
    p = RAW / src / "daily_chokepoints.json"
    if not check(src, "raw daily_chokepoints.json present", p.exists()):
        return None
    payload = json.loads(p.read_text(encoding="utf-8"))
    df = pd.DataFrame(payload["features"])
    check(src, "rows fetched = count reported by the ArcGIS service", len(df) == payload["count"], f"{len(df):,} vs {payload['count']:,}")
    check(src, "expected columns present", set(["date", "portid", "portname"] + PW_COUNTS + PW_CAP) <= set(df.columns), ", ".join(df.columns))
    df["date"] = pd.to_datetime(df["date"])
    check(src, "date agrees with year/month/day fields", ((df["date"].dt.year == df["year"]) & (df["date"].dt.month == df["month"]) & (df["date"].dt.day == df["day"])).all())
    check(src, "no duplicate (portid, date)", not df.duplicated(["portid", "date"]).any())
    meta_p = RAW / src / "chokepoints_database.json"
    if meta_p.exists():
        meta = pd.DataFrame(json.loads(meta_p.read_text(encoding="utf-8"))["features"])
        names = meta.set_index("portid")["portname"].to_dict()
        check(src, "28 chokepoints, all present in the daily table", set(df["portid"]) == set(names) and len(names) == 28,
              f"{df['portid'].nunique()} in daily, {len(names)} in the chokepoint database")
        check(src, "chokepoint names agree with the chokepoint database", (df["portid"].map(names) == df["portname"]).all())
    last_common = df.groupby("portid")["date"].max().min()
    for pid, g in df.groupby("portid"):
        ok, detail = contiguous(g["date"], "D")
        check(src, f"{g['portname'].iloc[0]} ({pid}): days contiguous", ok, detail)
    first = df.groupby("portid")["date"].min()
    check(src, "coverage: every chokepoint starts 2019-01-01 (tracker: 2019)", (first == pd.Timestamp("2019-01-01")).all(), f"{first.min().date()} .. {first.max().date()}")
    check(src, "every chokepoint ends on the same day", df.groupby("portid")["date"].max().nunique() == 1, str(last_common.date()))
    check(src, "last observation within 10 days of today", (pd.Timestamp(TODAY) - last_common).days <= 10, f"last {last_common.date()}, today {TODAY}")
    num = df[PW_COUNTS + PW_CAP].apply(pd.to_numeric, errors="coerce")
    check(src, "counts and capacities numeric, no missing", num.notna().all().all(), f"{num.isna().sum().sum()} missing")
    check(src, "no negative counts / capacities", (num >= 0).all().all(), f"{(num < 0).sum().sum()} negative")
    df[PW_COUNTS + PW_CAP] = num
    d1 = (df["n_total"] - df["n_cargo"] - df["n_tanker"]).abs().max()
    check(src, "identity: n_total = n_cargo + n_tanker", d1 == 0, f"max |diff| {d1}")
    d2 = (df["n_cargo"] - df[["n_container", "n_dry_bulk", "n_general_cargo", "n_roro"]].sum(axis=1)).abs().max()
    check(src, "identity: n_cargo = container + dry bulk + general cargo + roro", d2 == 0, f"max |diff| {d2}")
    d3 = (df["capacity"] - df["capacity_cargo"] - df["capacity_tanker"]).abs().max()
    check(src, "identity: capacity = capacity_cargo + capacity_tanker (integer rounding, tol 5 t)", d3 <= 5, f"max |diff| {d3}")
    d4 = (df["capacity_cargo"] - df[["capacity_container", "capacity_dry_bulk", "capacity_general_cargo", "capacity_roro"]].sum(axis=1)).abs().max()
    check(src, "identity: capacity_cargo = sum of cargo-type capacities (integer rounding, tol 5 t)", d4 <= 5, f"max |diff| {d4}")
    check(src, "capacity is zero whenever the count is zero", ((df[PW_COUNTS].values == 0) <= (df[PW_CAP].values == 0)).all())
    unk = int(((df["n_tanker"] > 0) & (df["capacity_tanker"] == 0)).sum())
    info(src, "tanker transits with no capacity estimate (count > 0, capacity 0)", f"{unk} chokepoint-days of {len(df):,}")
    df = df.sort_values(["portid", "date"])
    horm = df[df["portname"] == "Strait of Hormuz"].set_index("date")["n_tanker"]
    if len(horm):
        info(src, "Strait of Hormuz tanker transits per day: 2025 mean vs March 2026 mean vs last 30 days",
             f"{horm['2025'].mean():.1f} vs {horm['2026-03'].mean():.1f} vs {horm.iloc[-30:].mean():.1f}")
    bab = df[df["portname"] == "Bab el-Mandeb Strait"].set_index("date")["n_total"]
    if len(bab):
        info(src, "Bab el-Mandeb total transits per day: 2023-H1 mean vs 2024 mean", f"{bab['2023-01':'2023-06'].mean():.1f} vs {bab['2024'].mean():.1f}")
    out = df[["portid", "portname", "date"] + PW_COUNTS + PW_CAP].copy()
    out.insert(0, "tracker_ids", "D42")
    out.insert(1, "source", src)
    out["unit"] = "vessels per day (n_*) / deadweight tonnes (capacity_*)"
    out["vintage"] = payload.get("downloaded_at", TODAY)[:10]
    return out.sort_values(["portid", "date"]).reset_index(drop=True)


def clean_portwatch_disruptions(m: dict, src: str = "portwatch") -> pd.DataFrame | None:
    p = RAW / src / "disruptions_database.json"
    if not check(src + "_disruptions", "raw disruptions_database.json present", p.exists()):
        return None
    payload = json.loads(p.read_text(encoding="utf-8"))
    df = pd.DataFrame(payload["features"])
    check(src + "_disruptions", "rows = count reported", len(df) == payload["count"], f"{len(df)} vs {payload['count']}")
    for c in ("fromdate", "todate", "editdate"):
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            df[c] = pd.to_datetime(df[c], unit="ms", errors="coerce").dt.strftime("%Y-%m-%d")
        elif c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.strftime("%Y-%m-%d")
    check(src + "_disruptions", "every event has a start date", df["fromdate"].notna().all(), f"{df['fromdate'].isna().sum()} missing")
    check(src + "_disruptions", "eventid unique", not df["eventid"].duplicated().any())
    keep = [c for c in ["eventid", "eventtype", "eventname", "alertlevel", "country", "fromdate", "todate", "year", "severitytext",
                        "lat", "long", "affectedports", "n_affectedports", "affectedpopulation", "editdate"] if c in df.columns]
    out = df[keep].copy()
    out.insert(0, "tracker_ids", "D42")
    out.insert(1, "source", src)
    info(src + "_disruptions", "events by type", ", ".join(f"{k}: {v}" for k, v in out["eventtype"].value_counts().items()))
    return out.sort_values(["fromdate", "eventid"]).reset_index(drop=True)


# cleaner -> (output file name, catalog spec: (group keys, date column, value column or None))
CLEANERS = {
    "gpr": (clean_gpr, "gpr.csv", (["freq", "series_id"], "date", "value")),
    "ofac_recent_actions": (clean_ofac, "ofac_recent_actions.csv", (["category"], "date", None)),
    "ofac_sdn": (clean_ofac_sdn, "ofac_sdn.csv", (["sdn_type"], None, None)),
    "baumeister_hamilton": (clean_baumeister_hamilton, "baumeister_hamilton.csv", (["series_id"], "date", "value")),
    "kanzig": (clean_kanzig, "kanzig.csv", (["sample", "freq", "series_id"], "date", "value")),
    "portwatch_chokepoints": (clean_portwatch, "portwatch_chokepoints.csv", (["portname"], "date", "n_total")),
    "portwatch_disruptions": (clean_portwatch_disruptions, "portwatch_disruptions.csv", (["eventtype"], "fromdate", None)),
}


# --------------------------------------------------------------------------------------
# catalog, tracker status, CHECKS.md
# --------------------------------------------------------------------------------------
def catalog_rows(name: str, df: pd.DataFrame, keys: list[str], datecol: str | None, valuecol: str | None) -> list[dict]:
    out = []
    for key, g in df.groupby(keys, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        vals = g[valuecol] if valuecol else pd.Series([1.0] * len(g))
        out.append({"file": name, "tracker_ids": ";".join(sorted(set(g["tracker_ids"]))), "series_key": " | ".join(map(str, key)),
                    "first": str(g[datecol].min())[:10] if datecol else "", "last": str(g[datecol].max())[:10] if datecol else "",
                    "n_obs": int(vals.notna().sum()), "n_missing": int(vals.isna().sum())})
    return out


def tracker_status(outputs: dict[str, pd.DataFrame], m: dict) -> pd.DataFrame:
    loc = {ids: [] for ids in ("D37", "D38", "D39", "D40", "D41", "D42")}
    for name, df in outputs.items():
        for ids in sorted({i for s in df["tracker_ids"] for i in s.split(";")}):
            loc[ids].append(f"data/geopolitics/clean/{name}")
    rows = []
    for ids, files in loc.items():
        if files:
            rows.append({"ID": ids, "Status": "Cleaned", "Date retrieved": TODAY,
                         "Saved file / location": "; ".join(files) + " (raw: data/geopolitics/raw/)"})
    gsdb = m.get("sources", {}).get("gsdb", {})
    manual = [f["file"] for f in gsdb.get("files", []) if f.get("status") == "manual"]
    if manual:
        rows.append({"ID": "D38", "Status": "Downloaded", "Date retrieved": TODAY,
                     "Saved file / location": "data/geopolitics/raw/" + "; ".join(manual) + " (hand-placed; cleaner to be added once the release format is known)"})
    else:
        site = gsdb.get("site_check", {}).get("result", "not checked")
        rows.append({"ID": "D38", "Status": "Blocked / unavailable" if site.startswith("unreachable") else "Access requested",
                     "Date retrieved": "",
                     "Saved file / location": f"GSDB is released by e-mail request only; site {site}. Steps in data/geopolitics/raw/gsdb/README.md"})
    return pd.DataFrame(rows, columns=["ID", "Status", "Date retrieved", "Saved file / location"]).sort_values("ID").reset_index(drop=True)


def write_checks_md(outputs: dict[str, pd.DataFrame], failed: bool) -> None:
    n = {s: sum(1 for c in CHECKS if c[2] == s) for s in ("FAIL", "WARN", "PASS", "INFO")}
    lines = [f"# {CATEGORY} clean-up checks", "", f"Run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ",
             f"Result: **{'FAILED' if failed else 'ALL PASSED' + (' (with WARNs on coverage)' if n['WARN'] else '')}**  ",
             f"FAIL {n['FAIL']} · WARN {n['WARN']} · PASS {n['PASS']} · INFO {n['INFO']}", ""]
    warns = [c for c in CHECKS if c[2] in ("WARN", "FAIL")]
    if warns:
        lines += ["## Failures and warnings", ""] + [f"- **{s} [{src}] {name}** — {d}" for src, name, s, d in warns] + [""]
    lines += ["## Outputs", "", "| file | rows | columns |", "|---|---:|---|"]
    lines += [f"| {k} | {len(v):,} | {', '.join(v.columns)} |" for k, v in outputs.items()] + [""]
    lines += ["## Checks", ""]
    for src in dict.fromkeys(c[0] for c in CHECKS):
        lines += [f"### {src}", "", "| status | check | detail |", "|---|---|---|"]
        lines += [f"| {s} | {name} | {d.replace('|', '\\|')} |" for s0, name, s, d in CHECKS if s0 == src] + [""]
    CLEAN.mkdir(exist_ok=True)
    (CLEAN / "CHECKS.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=sorted(CLEANERS))
    a = ap.parse_args(argv)
    m = manifest()
    outputs: dict[str, pd.DataFrame] = {}
    specs: dict[str, tuple] = {}
    for name, (fn, fname, spec) in CLEANERS.items():
        if a.only and name not in a.only:
            continue
        print(f"[{name}] ...", flush=True)
        df = fn(m)
        if df is not None:
            outputs[fname] = df
            specs[fname] = spec
    failed = any(c[2] == "FAIL" for c in CHECKS)
    write_checks_md(outputs, failed)
    if failed:
        print("CHECKS FAILED - nothing written; see clean/CHECKS.md", file=sys.stderr)
        for src, name, s, d in CHECKS:
            if s == "FAIL":
                print(f"  FAIL [{src}] {name}: {d}".encode("ascii", "replace").decode(), file=sys.stderr)
        return 1
    catalog = []
    for fname, df in outputs.items():
        df.to_csv(CLEAN / fname, index=False, encoding="utf-8", lineterminator="\n")
        keys, datecol, valuecol = specs[fname]
        catalog += catalog_rows(fname, df, keys, datecol, valuecol)
        print(f"wrote clean/{fname}: {len(df):,} rows")
    pd.DataFrame(catalog).to_csv(CLEAN / "series_catalog.csv", index=False, encoding="utf-8", lineterminator="\n")
    tracker_status(outputs, m).to_csv(CLEAN / "tracker_status.csv", index=False, encoding="utf-8", lineterminator="\n")
    for src, name, s, d in CHECKS:
        if s == "WARN":
            print(f"  WARN [{src}] {name}: {d}".encode("ascii", "replace").decode())
    print("all checks passed; see clean/CHECKS.md and clean/tracker_status.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
