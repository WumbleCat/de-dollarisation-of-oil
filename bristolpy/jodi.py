"""Low-level access to the clean JODI-Oil World Database (monthly, Jan 2002 -> latest).

Data is read from the per-balance files written by data/jodi/clean_jodi.py
(data/jodi/balances/<balance>/<balance>.csv, wide: products as columns) and unpivoted on demand, one balance
at a time, cached in memory. Long rows have the columns
    report, balance, country, unit, period (YYYY-MM), date, product, value, flag, assessment
`value` is numeric or empty; when empty, `flag` holds JODI's status token. `assessment` is JODI's data-quality
code for the cell: 1 reasonable comparability, 2 consult metadata / use with caution, 3 not assessed.

    >>> from bristolpy import jodi
    >>> jodi.balances()
    >>> jodi.query(balance="Production", country="Saudi Arabia", product="Crude oil", unit="kb/d", start="2015-01")
    >>> jodi.wide("Imports")          # the per-balance table as written by the cleaner

Most users want bristolpy.fundamental, which wraps query() with one function per balance.
"""
from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from typing import Iterable

import pandas as pd

from . import paths

REBUILD_HINT = ("Run: python data/jodi/download_jodi.py && python data/jodi/clean_jodi.py "
                "(&& python data/jodi/compile_jodi.py for the single compiled file)")

COLUMNS = ["report", "balance", "country", "unit", "period", "date", "product", "value", "flag", "assessment"]
KEY = ["report", "balance", "country", "unit", "period", "product"]
ID_COLS = ["report", "balance", "country", "unit", "period", "date"]

# short unit aliases -> the labels used in the data
UNITS = {
    "kb/d": "Thousand Barrels per day (kb/d)",
    "kbbl": "Thousand Barrels (kbbl)",
    "kl": "Thousand Kilolitres (kl)",
    "kmt": "Thousand Metric Tons (kmt)",
    "conv": "Conversion factor barrels/ktons",
}
_UNIT_LOOKUP = {k.lower(): v for k, v in UNITS.items()} | {v.lower(): v for v in UNITS.values()}

FLAGS = {"-": "not available", "..": "not applicable / not reported", "x": "confidential", "N/A": "not applicable"}
ASSESSMENT = {1: "reasonable comparability", 2: "consult metadata / use with caution", 3: "not assessed"}

# JODI codes -> labels, for products/balances (countries come from the manifest + cleaner)
PRODUCT_LABELS = {
    "CRUDEOIL": "Crude oil", "NGL": "NGL", "OTHERCRUDE": "Other", "TOTCRUDE": "Total",
    "LPG": "Liquefied petroleum gases", "NAPHTHA": "Naphtha", "GASOLINE": "Motor and aviation gasoline",
    "KEROSENE": "Kerosenes", "JETKERO": "of which: kerosene type jet fuel", "GASDIES": "Gas/diesel oil",
    "RESFUEL": "Fuel oil", "ONONSPEC": "Other oil products", "TOTPRODS": "Total oil products",
}
FLOW_LABELS = {
    "INDPROD": "Production", "OSOURCES": "From other sources", "TOTIMPSB": "Imports", "TOTEXPSB": "Exports",
    "TRANSBAK": "Products transferred/Backflows", "DIRECUSE": "Direct use", "STOCKCH": "Stock change",
    "STATDIFF": "Statistical difference", "REFINOBS": "Refinery intake", "CLOSTLV": "Closing stocks",
    "REFGROUT": "Refinery output", "RECEIPTS": "Receipts", "PTRANSF": "Products transferred",
    "IPTRANSF": "Interproduct transfers", "TOTDEMO": "Demand",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


# ----------------------------------------------------------------------------------------------
# manifest and dimension members (cheap: no data file is read)
# ----------------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def manifest() -> dict:
    """data/jodi/raw/manifest.json: counts, dimension members (JODI codes), slice list, download time."""
    return json.loads(paths.require(paths.JODI_MANIFEST, REBUILD_HINT).read_text(encoding="utf-8"))


def reports() -> list[str]:
    return sorted(manifest()["reports"])


def balances(report: str | None = None) -> list[str]:
    reps = [report] if report else reports()
    return sorted({FLOW_LABELS[b] for r in reps for b in manifest()["reports"][r]["balances"]})


def products(report: str | None = None, balance: str | None = None) -> list[str]:
    reps = [report] if report else reports()
    out = set()
    for r in reps:
        for s in manifest()["reports"][r]["slices"]:
            if balance is None or FLOW_LABELS[s["balance"]] == balance:
                out.add(PRODUCT_LABELS[s["product"]])
    return sorted(out)


def reports_of(balance: str) -> list[str]:
    return [r for r in reports() if balance in balances(r)]


@lru_cache(maxsize=1)
def countries() -> list[str]:
    # the cleaner translates ISO2 codes to names; read them from the smallest per-balance file available
    for b in balances():
        p = _balance_path(b)
        if p.exists():
            return sorted(pd.read_csv(p, usecols=["country"])["country"].unique())
    raise FileNotFoundError(f"no per-balance CSV found under {paths.JODI_BALANCES}. {REBUILD_HINT}")


def units() -> dict[str, str]:
    """Short alias -> full unit label."""
    return dict(UNITS)


def periods() -> list[str]:
    return list(manifest()["reports"]["primary"]["times"])


def checks_passed(balance: str | None = None) -> bool:
    """True if the cleaner's CHECKS.md for the balance (or every balance) says all checks passed."""
    for b in [balance] if balance else balances():
        p = _balance_path(b).with_name("CHECKS.md")
        if not (p.exists() and "**Result: ALL PASSED**" in p.read_text(encoding="utf-8")):
            return False
    return True


def describe() -> str:
    """Human-readable summary of what is available."""
    m = manifest()
    per = periods()
    lines = [f"JODI-Oil World Database, downloaded {m.get('downloaded_at', '?')} from jodidata.org",
             f"months: {per[0]} .. {per[-1]} ({len(per)})",
             f"countries: {m['reports']['primary']['counts']['Country']}",
             f"units: {', '.join(UNITS)}  (aliases for {', '.join(UNITS.values())})"]
    for rep in reports():
        lines.append(f"[{rep}] balances: {', '.join(balances(rep))}")
        lines.append(f"[{rep}] products: {', '.join(products(rep))}")
    lines.append(f"per-balance files: {paths.JODI_BALANCES.relative_to(paths.ROOT).as_posix()}/<balance>/<balance>.csv")
    lines.append(f"checks passed: {checks_passed()}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------
# loading (per balance, cached)
# ----------------------------------------------------------------------------------------------
def _balance_path(balance: str):
    return paths.JODI_BALANCES / _slug(balance) / f"{_slug(balance)}.csv"


@lru_cache(maxsize=None)
def wide(balance: str) -> pd.DataFrame:
    """The per-balance table as written by the cleaner: one row per report x country x unit x month,
    product value columns plus '<product> [flag]' and '<product> [assessment]' columns."""
    balance = _resolve([balance], balances(), "balance")[0]
    path = paths.require(_balance_path(balance), REBUILD_HINT)
    prods = products(balance=balance)
    fcols, acols = [f"{p} [flag]" for p in prods], [f"{p} [assessment]" for p in prods]
    df = pd.read_csv(path, dtype={**{c: str for c in ID_COLS + fcols}, **{c: "Int64" for c in acols}},
                     keep_default_na=False, na_values=[""])
    for c in fcols:
        df[c] = df[c].fillna("")
    df["date"] = pd.to_datetime(df["date"])
    return df


@lru_cache(maxsize=None)
def load_balance(balance: str) -> pd.DataFrame:
    """One balance in long format (one row per report x country x unit x month x product)."""
    w = wide(balance)
    parts = []
    for rep in w["report"].unique():
        prods = products(report=rep, balance=balance)
        sub = w[w["report"] == rep]
        vals = sub.melt(id_vars=ID_COLS, value_vars=prods, var_name="product", value_name="value")
        flags = sub.melt(id_vars=ID_COLS, value_vars=[f"{p} [flag]" for p in prods], var_name="product", value_name="flag")
        flags["product"] = flags["product"].str.removesuffix(" [flag]")
        assess = sub.melt(id_vars=ID_COLS, value_vars=[f"{p} [assessment]" for p in prods], var_name="product", value_name="assessment")
        assess["product"] = assess["product"].str.removesuffix(" [assessment]")
        parts.append(vals.merge(flags, on=ID_COLS + ["product"]).merge(assess, on=ID_COLS + ["product"]))
    return pd.concat(parts, ignore_index=True)[COLUMNS].sort_values(KEY, ignore_index=True)


def load(balance: str | Iterable[str] | None = None) -> pd.DataFrame:
    """Long table for the given balance(s); all balances when None (about 22.7 million rows - prefer a subset)."""
    bals = _resolve(_as_list(balance), balances(), "balance") if balance is not None else balances()
    return pd.concat([load_balance(b) for b in bals], ignore_index=True)


def reload() -> None:
    """Drop every cached table (after re-running the pipeline)."""
    manifest.cache_clear()
    countries.cache_clear()
    wide.cache_clear()
    load_balance.cache_clear()


# ----------------------------------------------------------------------------------------------
# querying
# ----------------------------------------------------------------------------------------------
def _as_list(x) -> list | None:
    if x is None:
        return None
    if isinstance(x, str):
        return [x]
    return list(x)


def _resolve(values: Iterable[str] | None, universe: list[str], what: str) -> list[str] | None:
    """Match user-supplied names to the data's names, case-insensitively, with suggestions on a miss."""
    if values is None:
        return None
    lookup = {u.lower(): u for u in universe}
    out = []
    for v in values:
        hit = lookup.get(str(v).strip().lower())
        if hit is None:
            close = difflib.get_close_matches(str(v), universe, n=5, cutoff=0.5)
            raise KeyError(f"unknown {what} {v!r}. Did you mean: {close}" if close else
                           f"unknown {what} {v!r}. Choices: {universe}")
        out.append(hit)
    return out


def resolve_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    hit = _UNIT_LOOKUP.get(unit.strip().lower())
    if hit is None:
        raise KeyError(f"unknown unit {unit!r}. Use one of {list(UNITS)} or a full label {list(UNITS.values())}")
    return hit


def query(balance: str | Iterable[str] | None = None, country: str | Iterable[str] | None = None,
          product: str | Iterable[str] | None = None, unit: str | None = None, report: str | None = None,
          start: str | None = None, end: str | None = None, numeric_only: bool = False,
          wide: bool = False) -> pd.DataFrame:
    """Filter the clean table.

    balance, country, product: a name or list of names (case-insensitive; unknown names raise with suggestions);
                 balance=None reads every balance (slow the first time)
    unit:        short alias ("kb/d", "kbbl", "kl", "kmt", "conv") or full label; None = all units
    report:      "primary" | "secondary" | None (both)
    start, end:  inclusive period bounds as "YYYY-MM" (or anything pandas parses to a month)
    numeric_only: drop rows whose value is empty (status token in `flag`)
    wide:        return periods as columns (index: report, balance, country, unit, product); flags dropped
    """
    bals = _resolve(_as_list(balance), balances(), "balance") if balance is not None else balances()
    if report is not None:
        if report not in reports():
            raise KeyError(f"unknown report {report!r}; choices {reports()}")
        bals = [b for b in bals if report in reports_of(b)]
    c = _resolve(_as_list(country), countries(), "country")
    p = _resolve(_as_list(product), products(), "product")
    u = resolve_unit(unit)
    lo = pd.Period(start, freq="M").strftime("%Y-%m") if start is not None else None
    hi = pd.Period(end, freq="M").strftime("%Y-%m") if end is not None else None

    parts = []
    for b in bals:
        df = load_balance(b)
        mask = pd.Series(True, index=df.index)
        if report is not None:
            mask &= df["report"] == report
        if c is not None:
            mask &= df["country"].isin(c)
        if p is not None:
            mask &= df["product"].isin(p)
        if u is not None:
            mask &= df["unit"] == u
        if lo is not None:
            mask &= df["period"] >= lo
        if hi is not None:
            mask &= df["period"] <= hi
        if numeric_only:
            mask &= df["value"].notna()
        parts.append(df.loc[mask])
    out = pd.concat(parts, ignore_index=True).sort_values(KEY, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS)
    if wide:
        out = (out.pivot(index=["report", "balance", "country", "unit", "product"], columns="period", values="value")
                  .rename_axis(columns=None).reset_index())
    return out
