"""Clean the raw *<CATEGORY>* downloads (tracker rows <ID RANGE>) in ./raw into tidy CSVs in ./clean, and run
sanity checks that must all pass before anything is written.

Outputs (data/<category_slug>/clean/)
  <source_slug>.csv      <IDs>   <what it holds: dims, frequency, span>
  series_catalog.csv              one row per series in every file: coverage and observation counts
  tracker_status.csv              suggested Status / Date retrieved / Saved file values for the tracker workbook
  CHECKS.md                       every check with PASS / WARN / FAIL / INFO and details

Any FAIL aborts the write of the data files (CHECKS.md is still written) and exits 1.
Run `python data/<category_slug>/download_<category_slug>.py` first.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent          # data/<category_slug>
RAW = HERE / "raw"
CLEAN = HERE / "clean"
ROOT = HERE.parents[1]
CATEGORY = "<Category as written in the tracker>"
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


def to_float(v):
    """(float or NaN, flag): flags are the source's non-numeric tokens, kept verbatim."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan, ""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v), ""
    s = str(v).strip()
    if s == "":
        return np.nan, ""
    try:
        return float(s.replace(",", "")), ""
    except ValueError:
        return np.nan, s


def contiguous(dates: pd.Series, freq: str) -> tuple[bool, str]:
    """freq: 'D' (business days, gaps <= 4 days allowed), 'W', 'MS', 'QS', 'YS'."""
    d = pd.to_datetime(pd.Series(dates).drop_duplicates()).sort_values()
    if d.empty:
        return False, "no dates"
    if freq == "D":
        gaps = d.diff().dt.days.dropna()
        bad = gaps[gaps > 4]
        return bad.empty, f"{d.iloc[0].date()} .. {d.iloc[-1].date()}, {len(d)} days, {len(bad)} gaps > 4 days"
    expected = pd.date_range(d.iloc[0], d.iloc[-1], freq=freq)
    missing = expected.difference(d)
    return missing.empty, f"{d.iloc[0].date()} .. {d.iloc[-1].date()}, {len(d)} periods, {len(missing)} missing"


def manifest() -> dict:
    p = RAW / "manifest.json"
    if not p.exists():
        sys.exit(f"{p.relative_to(ROOT).as_posix()} not found: run download_<category_slug>.py first")
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# one cleaner per source -> tidy long DataFrame (or None when the raw files are absent)
# --------------------------------------------------------------------------------------
def clean_example(src: str = "<source_slug>") -> pd.DataFrame | None:
    files = sorted((RAW / src).glob("*.json"))
    if not check(src, "raw files present", bool(files), f"{len(files)} files in raw/{src}"):
        return None
    rows, n_raw = [], 0
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        for obs in payload.get("observations", []):
            n_raw += 1
            value, flag = to_float(obs.get("value"))
            rows.append({"tracker_ids": "Dxx", "source": src, "series_id": f.stem, "unit": "<unit>",
                         "date": obs["date"], "value": value, "flag": flag})
    df = pd.DataFrame(rows)
    check(src, "every raw observation captured", len(df) == n_raw, f"{n_raw:,} raw -> {len(df):,} rows")
    check(src, "no duplicate (series_id, date)", not df.duplicated(["series_id", "date"]).any())
    for sid, g in df.groupby("series_id"):
        ok, detail = contiguous(g["date"], "D")
        check(src, f"{sid}: dates contiguous", ok, detail)
        check(src, f"{sid}: values finite", np.isfinite(g["value"].dropna()).all())
    info(src, "cells with a status flag instead of a number", int((df["flag"] != "").sum()))
    return df.sort_values(["series_id", "date"]).reset_index(drop=True)


CLEANERS = {
    "<source_slug>": clean_example,
}


# --------------------------------------------------------------------------------------
# catalog, tracker status, CHECKS.md
# --------------------------------------------------------------------------------------
def catalog_rows(name: str, df: pd.DataFrame, keys: list[str], datecol: str = "date") -> list[dict]:
    out = []
    for key, g in df.groupby(keys, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        out.append({"file": name, "tracker_ids": ";".join(sorted(set(g["tracker_ids"]))), "series_key": " | ".join(map(str, key)),
                    "first": g[datecol].min(), "last": g[datecol].max(), "n_obs": int(g["value"].notna().sum()),
                    "n_missing": int(g["value"].isna().sum())})
    return out


def tracker_status(outputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in outputs.items():
        for ids in sorted({i for s in df["tracker_ids"] for i in s.split(";")}):
            rows.append({"ID": ids, "Status": "Cleaned", "Date retrieved": TODAY,
                         "Saved file / location": f"data/{HERE.name}/clean/{name}; raw data/{HERE.name}/raw/{df['source'].iloc[0]}/"})
    # add Blocked / unavailable or Access requested rows here for sources that could not be fetched
    return pd.DataFrame(rows, columns=["ID", "Status", "Date retrieved", "Saved file / location"]).sort_values("ID")


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
    manifest()
    outputs: dict[str, pd.DataFrame] = {}
    for name, fn in CLEANERS.items():
        if a.only and name not in a.only:
            continue
        df = fn()
        if df is not None:
            outputs[f"{name}.csv"] = df
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
        keys = [c for c in ("series_id", "country", "geo", "product", "table") if c in df.columns]
        catalog += catalog_rows(name, df, keys or ["source"], "year" if "year" in df.columns else "date")
        print(f"wrote clean/{name}: {len(df):,} rows")
    pd.DataFrame(catalog).to_csv(CLEAN / "series_catalog.csv", index=False)
    tracker_status(outputs).to_csv(CLEAN / "tracker_status.csv", index=False)
    print("all checks passed; see clean/CHECKS.md and clean/tracker_status.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
