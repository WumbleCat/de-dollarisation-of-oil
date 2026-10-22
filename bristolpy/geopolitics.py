"""bristolpy.geopolitics - the cleaned Geopolitics sources (tracker rows D37-D42) from
data/geopolitics/clean/*.csv, produced by data/geopolitics/clean_geopolitics.py.

    >>> from bristolpy import geopolitics as g
    >>> g.gpr("GPR")                                   # monthly GPR index (Caldara & Iacoviello), 1900->
    >>> g.gpr(["GPRD_ACT", "GPRD_THREAT"], freq="D")   # daily acts vs threats, 1985->
    >>> g.gpr("GPRC_RUS", wide=True)                   # country index, dates as columns
    >>> g.ofac(is_iran=1)                              # OFAC recent actions flagged Iran-related
    >>> g.ofac(category="Sanctions List Updates", start="2022-02-01")
    >>> g.sdn(sdn_type="vessel")                       # current SDN list entries
    >>> g.baumeister_hamilton("oil_supply_shocks")     # BH (2019) structural shocks, monthly
    >>> g.kanzig("news_shock")                         # Kaenzig oil supply news shock, monthly
    >>> g.kanzig("surprise_pc", freq="D")              # daily surprises on OPEC announcement dates
    >>> g.opec_announcement_dates()                    # the event-study date list
    >>> g.chokepoints("Strait of Hormuz")              # PortWatch daily transits and capacity
    >>> g.chokepoints(["Strait of Hormuz", "Bab el-Mandeb Strait"], start="2026-02-01")
    >>> g.disruptions(eventtype="TC")                  # PortWatch disruption events
    >>> g.catalog(); g.tracker_status(); g.sources()

Filters are simple equality filters on the file's columns (a string or a list of strings); `start` / `end`
are inclusive ISO-date bounds on `date`; `wide=True` pivots series x date for the series files.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import pandas as pd

from . import paths

GEOPOLITICS = paths.DATA / "geopolitics"
GEOPOLITICS_CLEAN = GEOPOLITICS / "clean"
HINT = "Run: python data/geopolitics/download_geopolitics.py && python data/geopolitics/clean_geopolitics.py"

SOURCES = {
    "gpr": ("gpr.csv", "Caldara & Iacoviello geopolitical risk: monthly (1900->) and daily (1985->) GPR, threats, acts, country indexes (D37)"),
    "ofac": ("ofac_recent_actions.csv", "US Treasury OFAC recent actions, one row per action with programme tags, SDN counts and Iran/Russia/Venezuela flags (D39)"),
    "sdn": ("ofac_sdn.csv", "OFAC Specially Designated Nationals list, current snapshot (D39)"),
    "baumeister_hamilton": ("baumeister_hamilton.csv", "Baumeister & Hamilton (2019) structural oil supply / demand shocks, monthly 1975-> (D40)"),
    "kanzig": ("kanzig.csv", "Kaenzig (2021) oil supply surprises (daily, OPEC announcement dates) and news shocks (monthly) (D41)"),
    "chokepoints": ("portwatch_chokepoints.csv", "IMF PortWatch daily transits and capacity by vessel type for 28 chokepoints, 2019-> (D42)"),
    "disruptions": ("portwatch_disruptions.csv", "IMF PortWatch disruption events (D42)"),
    "catalog": ("series_catalog.csv", "one row per series in the files above: first/last date, observations"),
    "tracker_status": ("tracker_status.csv", "Status / Date retrieved / Saved file per tracker row D37-D42"),
}
DATE_COLS = ("date", "fromdate", "todate", "editdate")


@lru_cache(maxsize=None)
def _load_source(name: str) -> pd.DataFrame:
    fname, _ = SOURCES[name]
    path = paths.require(GEOPOLITICS_CLEAN / fname, HINT)
    cols = pd.read_csv(path, nrows=0).columns
    return pd.read_csv(path, parse_dates=[c for c in DATE_COLS if c in cols], low_memory=False)


def sources() -> pd.DataFrame:
    """Table of the geopolitics sources available through this module."""
    rows = []
    for name, (fname, desc) in SOURCES.items():
        rows.append({"function": f"geopolitics.{name}()", "file": f"data/geopolitics/clean/{fname}",
                     "available": (GEOPOLITICS_CLEAN / fname).exists(), "description": desc})
    return pd.DataFrame(rows)


def _filtered(name: str, start: str | None = None, end: str | None = None, datecol: str = "date", **eq) -> pd.DataFrame:
    df = _load_source(name)
    for col, val in eq.items():
        if val is None:
            continue
        if col not in df.columns:
            raise KeyError(f"{name}: no column {col!r}; columns are {list(df.columns)}")
        vals = [val] if isinstance(val, (str, int, float)) else list(val)
        df = df[df[col].isin(vals)]
    if start is not None and datecol in df.columns:
        df = df[df[datecol] >= pd.Timestamp(start)]
    if end is not None and datecol in df.columns:
        df = df[df[datecol] <= pd.Timestamp(end)]
    return df.reset_index(drop=True)


def _wide(df: pd.DataFrame, index: list[str]) -> pd.DataFrame:
    return df.pivot_table(index=index, columns="date", values="value").rename_axis(columns=None).reset_index()


def gpr(series_id: str | Iterable[str] | None = None, freq: str | None = None, start: str | None = None,
        end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """GPR indexes. series_id e.g. "GPR", "GPRT" (threats), "GPRA" (acts), "GPRH" (historical, 1900->),
    "GPRC_IRN"-style country indexes (GPRC_RUS, GPRC_SAU, GPRC_USA ...), daily "GPRD", "GPRD_ACT", "GPRD_THREAT".
    freq "M" (monthly) or "D" (daily); None = both."""
    df = _filtered("gpr", start, end, series_id=series_id, freq=freq)
    return _wide(df, ["freq", "series_id", "series_name"]) if wide else df


def gpr_series() -> pd.DataFrame:
    """The GPR series ids with their labels and frequency."""
    return _load_source("gpr").drop_duplicates(["freq", "series_id"])[["freq", "series_id", "series_name"]].reset_index(drop=True)


def ofac(category: str | Iterable[str] | None = None, start: str | None = None, end: str | None = None,
         is_iran: int | None = None, is_russia: int | None = None, is_venezuela: int | None = None,
         is_oil_shipping: int | None = None, programs_contain: str | None = None) -> pd.DataFrame:
    """OFAC recent actions (one row per action). Flags are 1/0; programs_contain matches a programme tag
    substring such as "IRAN", "RUSSIA-EO14024", "UKRAINE-EO13662"."""
    df = _filtered("ofac", start, end, category=category, is_iran=is_iran, is_russia=is_russia,
                   is_venezuela=is_venezuela, is_oil_shipping=is_oil_shipping)
    if programs_contain:
        df = df[df["programs"].fillna("").str.contains(programs_contain, case=False, regex=False)].reset_index(drop=True)
    return df


def ofac_monthly_counts(**filters) -> pd.DataFrame:
    """Number of OFAC actions per month (after the same filters as ofac()), as a monthly series."""
    df = ofac(**filters)
    s = df.groupby(df["date"].dt.to_period("M").dt.to_timestamp()).size()
    return s.rename("n_actions").rename_axis("date").reset_index()


def sdn(sdn_type: str | Iterable[str] | None = None, program_contains: str | None = None) -> pd.DataFrame:
    """Current SDN list snapshot. sdn_type "individual", "vessel", "aircraft"; entities carry a blank type in the source."""
    df = _filtered("sdn", sdn_type=sdn_type)
    if program_contains:
        df = df[df["program"].fillna("").str.contains(program_contains, case=False, regex=False)].reset_index(drop=True)
    return df


def baumeister_hamilton(series_id: str | Iterable[str] | None = None, start: str | None = None, end: str | None = None,
                        wide: bool = False) -> pd.DataFrame:
    """BH (2019) shocks: "oil_supply_shocks", "economic_activity_shocks", "oil_consumption_demand_shocks",
    "oil_inventory_demand_shocks"; plus the VAR input "oecd_6nme_industrial_production"."""
    df = _filtered("baumeister_hamilton", start, end, series_id=series_id)
    return _wide(df, ["series_id", "series_name"]) if wide else df


def kanzig(series_id: str | Iterable[str] | None = None, freq: str | None = None, sample: str = "full",
           start: str | None = None, end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Kaenzig (2021). Monthly (freq "M"): "monthly_surprise", "news_shock". Daily (freq "D", OPEC announcement
    dates): "surprise_front", "surprise_1m" .. "surprise_12m", "surprise_pc". sample "full" or "pre_covid"."""
    df = _filtered("kanzig", start, end, series_id=series_id, freq=freq, sample=sample)
    return _wide(df, ["sample", "freq", "series_id"]) if wide else df


def opec_announcement_dates(sample: str = "full") -> pd.Series:
    """The OPEC announcement dates on which Kaenzig's daily surprises are measured (event-study list)."""
    d = _filtered("kanzig", freq="D", sample=sample, series_id="surprise_pc")["date"]
    return d.drop_duplicates().sort_values().reset_index(drop=True)


def chokepoints(portname: str | Iterable[str] | None = None, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """PortWatch daily transit counts (n_*) and capacity in DWT (capacity_*) per chokepoint, e.g.
    "Strait of Hormuz", "Bab el-Mandeb Strait", "Suez Canal", "Cape of Good Hope", "Malacca Strait"."""
    return _filtered("chokepoints", start, end, portname=portname)


def chokepoint_names() -> list[str]:
    return sorted(_load_source("chokepoints")["portname"].unique())


def disruptions(eventtype: str | Iterable[str] | None = None, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """PortWatch disruption events. eventtype: TC tropical cyclone, EQ earthquake, FL flood, DR drought, WF wildfire,
    VO volcano, OT other. start/end bound `fromdate`."""
    return _filtered("disruptions", start, end, datecol="fromdate", eventtype=eventtype)


def catalog() -> pd.DataFrame:
    return _load_source("catalog")


def tracker_status() -> pd.DataFrame:
    return _load_source("tracker_status")


def checks_passed() -> bool:
    """True when data/geopolitics/clean/CHECKS.md says ALL PASSED."""
    p = GEOPOLITICS_CLEAN / "CHECKS.md"
    return p.exists() and "Result: **ALL PASSED" in p.read_text(encoding="utf-8")


def reload():
    """Drop every cached table (after re-running the pipeline)."""
    _load_source.cache_clear()
