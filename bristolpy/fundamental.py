"""bristolpy.fundamental - oil fundamentals: one function per JODI balance, plus the other cleaned
fundamentals sources (EIA STEO, EIA WPSR, Eurostat, Energy Institute, UN Comtrade).

    >>> from bristolpy import fundamental as f
    >>> f.demand("China", product="Total oil products")                 # kb/d, long format
    >>> f.production(["Saudi Arabia", "Iraq"], product="Crude oil", wide=True)
    >>> f.imports("India", unit="kmt", start="2026-01")
    >>> f.get("Refinery intake", country="Germany")                     # any balance by name
    >>> f.balances()                                                    # what get() accepts
    >>> f.steo(), f.wpsr(), f.eurostat(), f.energy_institute(), f.comtrade()

Every JODI function shares the same keyword arguments (see jodi.query):
    country   name or list of names (case-insensitive); None = all 118 countries
    product   name or list; None = every product of the balance
              primary products:   Crude oil, NGL, Other, Total
              secondary products: Fuel oil, Gas/diesel oil, Kerosenes, Liquefied petroleum gases,
                                  Motor and aviation gasoline, Naphtha, Other oil products,
                                  Total oil products, of which: kerosene type jet fuel
    unit      "kb/d" (default), "kbbl", "kl", "kmt", "conv" (barrels per kilotonne), or None for all
    report    "primary" | "secondary" | None (both, for balances that exist in both)
    start/end inclusive "YYYY-MM" bounds
    numeric_only  drop cells jodidb reports as "-", "..", "x"
    wide      periods as columns instead of rows
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import pandas as pd

from . import jodi, paths

DEFAULT_UNIT = "kb/d"

# balance name -> (reports it exists in, what it means)
BALANCES = {
    "Production":                     (("primary",),              "indigenous production of crude, NGL, other primary"),
    "From other sources":             (("primary",),              "primary supply from other sources (e.g. additives, biofuels)"),
    "Imports":                        (("primary", "secondary"),  "imports"),
    "Exports":                        (("primary", "secondary"),  "exports"),
    "Products transferred/Backflows": (("primary",),              "primary: products transferred / backflows to refineries"),
    "Direct use":                     (("primary",),              "primary used directly without refining"),
    "Stock change":                   (("primary", "secondary"),  "change in closing stocks (positive = build)"),
    "Statistical difference":         (("primary", "secondary"),  "supply minus demand residual"),
    "Refinery intake":                (("primary",),              "primary feed into refineries"),
    "Closing stocks":                 (("primary", "secondary"),  "end-of-month stock level"),
    "Refinery output":                (("secondary",),            "refinery gross output of products"),
    "Receipts":                       (("secondary",),            "secondary: receipts (primary product receipts)"),
    "Products transferred":           (("secondary",),            "secondary: interproduct transfers out / reclassification"),
    "Interproduct transfers":         (("secondary",),            "secondary: interproduct transfers"),
    "Demand":                         (("secondary",),            "inland deliveries / consumption of products"),
}


def balances() -> pd.DataFrame:
    """Table of the JODI balances get() accepts, with the report(s) they exist in and a one-line meaning."""
    return pd.DataFrame([{"balance": b, "reports": ", ".join(r), "meaning": m} for b, (r, m) in BALANCES.items()])


def get(balance: str, country: str | Iterable[str] | None = None, product: str | Iterable[str] | None = None,
        unit: str | None = DEFAULT_UNIT, report: str | None = None, start: str | None = None,
        end: str | None = None, numeric_only: bool = False, wide: bool = False) -> pd.DataFrame:
    """Any JODI balance by name; see the module docstring for the arguments."""
    return jodi.query(balance=balance, country=country, product=product, unit=unit, report=report,
                      start=start, end=end, numeric_only=numeric_only, wide=wide)


def _balance_fn(balance: str):
    reports, meaning = BALANCES[balance]

    def fn(country=None, product=None, unit=DEFAULT_UNIT, report=None, start=None, end=None,
           numeric_only=False, wide=False) -> pd.DataFrame:
        return get(balance, country=country, product=product, unit=unit, report=report, start=start, end=end,
                   numeric_only=numeric_only, wide=wide)

    fn.__name__ = balance.lower().replace("/", "_").replace(" ", "_")
    fn.__doc__ = (f"JODI '{balance}' ({', '.join(reports)} report{'s' if len(reports) > 1 else ''}): {meaning}.\n"
                  f"Same keyword arguments as bristolpy.fundamental.get(); unit defaults to {DEFAULT_UNIT!r}.")
    return fn


production = _balance_fn("Production")
from_other_sources = _balance_fn("From other sources")
imports = _balance_fn("Imports")
exports = _balance_fn("Exports")
products_transferred_backflows = _balance_fn("Products transferred/Backflows")
direct_use = _balance_fn("Direct use")
stock_change = _balance_fn("Stock change")
statistical_difference = _balance_fn("Statistical difference")
refinery_intake = _balance_fn("Refinery intake")
closing_stocks = _balance_fn("Closing stocks")
refinery_output = _balance_fn("Refinery output")
receipts = _balance_fn("Receipts")
products_transferred = _balance_fn("Products transferred")
interproduct_transfers = _balance_fn("Interproduct transfers")
demand = _balance_fn("Demand")

# convenience aliases
consumption = demand
stocks = closing_stocks


def countries() -> list[str]:
    return jodi.countries()


def products(report: str | None = None, balance: str | None = None) -> list[str]:
    return jodi.products(report=report, balance=balance)


def periods() -> list[str]:
    return jodi.periods()


def describe() -> str:
    return jodi.describe()


def net_imports(country=None, product=None, unit=DEFAULT_UNIT, report=None, start=None, end=None,
                wide: bool = False) -> pd.DataFrame:
    """Imports minus exports per report x country x unit x period x product (numeric cells only)."""
    imp = imports(country, product, unit, report, start, end, numeric_only=True)
    exp = exports(country, product, unit, report, start, end, numeric_only=True)
    key = ["report", "country", "unit", "period", "date", "product"]
    m = imp[key + ["value"]].merge(exp[key + ["value"]], on=key, how="inner", suffixes=("_imports", "_exports"))
    m["value"] = m["value_imports"] - m["value_exports"]
    m.insert(1, "balance", "Net imports")
    out = m[["report", "balance", "country", "unit", "period", "date", "product", "value", "value_imports", "value_exports"]]
    if wide:
        out = (out.pivot(index=["report", "balance", "country", "unit", "product"], columns="period", values="value")
                  .rename_axis(columns=None).reset_index())
    return out


# ----------------------------------------------------------------------------------------------
# other fundamentals sources (data/fundamentals/clean/*.csv from data/fundamentals/clean_fundamentals.py)
# ----------------------------------------------------------------------------------------------
FUND_HINT = "Run: python data/fundamentals/download_fundamentals.py && python data/fundamentals/clean_fundamentals.py"
SOURCES = {
    "steo": ("eia_steo.csv", "EIA Short-Term Energy Outlook: world/OPEC/non-OPEC liquids production, consumption, inventories (monthly, D01 D03 D05 D07)"),
    "wpsr": ("eia_wpsr.csv", "EIA Weekly Petroleum Status Report: US crude production and stocks (weekly, D04 D06 D08)"),
    "jodi_tracker": ("jodi_fundamentals.csv", "JODI crude production and refinery intake as cleaned for the tracker (D02 D09)"),
    "eurostat": ("eurostat_nrg_cb_oilm.csv", "Eurostat nrg_cb_oilm monthly oil balance for FR, DE, EU27 (D10)"),
    "energy_institute": ("ei_statistical_review.csv", "Energy Institute Statistical Review: annual production, consumption, refining, trade flows (D11)"),
    "comtrade": ("comtrade_hs2709_2710.csv", "UN Comtrade HS 2709/2710 annual crude & product trade by reporter x partner (D12)"),
    "catalog": ("series_catalog.csv", "one row per series in the files above: first/last date, observations, missing"),
    "tracker_status": ("tracker_status.csv", "Status / Date retrieved / Saved file per tracker row D01-D12"),
}


@lru_cache(maxsize=None)
def _load_source(name: str) -> pd.DataFrame:
    fname, _ = SOURCES[name]
    path = paths.require(paths.FUNDAMENTALS_CLEAN / fname, FUND_HINT)
    date_cols = [c for c in ("date",) if c in pd.read_csv(path, nrows=0).columns]
    return pd.read_csv(path, parse_dates=date_cols, low_memory=False)


def sources() -> pd.DataFrame:
    """Table of the non-JODI fundamentals sources available through this module."""
    rows = []
    for name, (fname, desc) in SOURCES.items():
        p = paths.FUNDAMENTALS_CLEAN / fname
        rows.append({"function": f"fundamental.{name}()", "file": f"data/fundamentals/clean/{fname}",
                     "available": p.exists(), "description": desc})
    return pd.DataFrame(rows)


def _filtered(name: str, **eq) -> pd.DataFrame:
    df = _load_source(name)
    for col, val in eq.items():
        if val is None:
            continue
        if col not in df.columns:
            raise KeyError(f"{name}: no column {col!r}; columns are {list(df.columns)}")
        vals = [val] if isinstance(val, str) else list(val)
        df = df[df[col].isin(vals)]
    return df.reset_index(drop=True)


def steo(table: str | Iterable[str] | None = None, series_code: str | Iterable[str] | None = None,
         section: str | Iterable[str] | None = None) -> pd.DataFrame:
    """EIA STEO monthly series. Filter by table ("3a".."3e"), series_code (e.g. "copr_opec") or section text."""
    return _filtered("steo", table=table, series_code=series_code, section=section)


def wpsr(series_id: str | Iterable[str] | None = None) -> pd.DataFrame:
    """EIA WPSR weekly series (WCRFPUS2 production, WCESTUS1 commercial stocks, WCSSTUS1 SPR, WPULEUS3 utilisation)."""
    return _filtered("wpsr", series_id=series_id)


def jodi_tracker(tracker_ids: str | Iterable[str] | None = None, country: str | Iterable[str] | None = None) -> pd.DataFrame:
    """JODI D02 (crude production) / D09 (refinery intake) as cleaned by data/fundamentals/clean_fundamentals.py."""
    return _filtered("jodi_tracker", tracker_ids=tracker_ids, country=country)


def eurostat(geo: str | Iterable[str] | None = None, nrg_bal: str | Iterable[str] | None = None,
             siec: str | Iterable[str] | None = None) -> pd.DataFrame:
    """Eurostat nrg_cb_oilm (thousand tonnes). geo e.g. "DE", nrg_bal e.g. "IMP", siec e.g. "O4100_TOT"."""
    return _filtered("eurostat", geo=geo, nrg_bal=nrg_bal, siec=siec)


def energy_institute(sheet: str | Iterable[str] | None = None, region: str | Iterable[str] | None = None) -> pd.DataFrame:
    """Energy Institute Statistical Review annual tables."""
    return _filtered("energy_institute", sheet=sheet, region=region)


def comtrade(reporter: str | Iterable[str] | None = None, partner: str | Iterable[str] | None = None,
             flow: str | Iterable[str] | None = None, cmd_code: int | Iterable[int] | None = None) -> pd.DataFrame:
    """UN Comtrade HS 2709 (crude) / 2710 (products), annual, imports and exports by reporter x partner."""
    df = _filtered("comtrade", reporter=reporter, partner=partner, flow=flow)
    if cmd_code is not None:
        codes = [cmd_code] if isinstance(cmd_code, int) else list(cmd_code)
        df = df[df["cmd_code"].isin(codes)].reset_index(drop=True)
    return df


def catalog() -> pd.DataFrame:
    return _load_source("catalog")


def tracker_status() -> pd.DataFrame:
    return _load_source("tracker_status")


def reload():
    """Drop every cached table (after re-running the pipelines)."""
    jodi.reload()
    _load_source.cache_clear()
