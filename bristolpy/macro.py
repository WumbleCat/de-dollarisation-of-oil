"""bristolpy.macro - macro controls (tracker rows D30-D36) from data/macro_controls/clean/.

    >>> from bristolpy import macro as mc
    >>> mc.fed_funds()                          # FRED FEDFUNDS equivalent: H.15 monthly effective rate
    >>> mc.fed_funds(freq="D", start="2022-01") # FRED DFF equivalent: calendar-daily
    >>> mc.shadow_rate()                        # Wu-Xia shadow rate (NaN outside the ZLB months)
    >>> mc.effr()                               # NY Fed EFFR publication (rate, percentiles, volume)
    >>> mc.policy_shocks()                      # Bauer-Swanson MPS / MPS_ORTH per FOMC announcement
    >>> mc.policy_shocks(monthly=True)          # ... summed by month (the paper's SVAR instrument)
    >>> mc.jk_shocks()                          # Jarocinski-Karadi MP_pm / CBI_pm, monthly (updated)
    >>> mc.us_cpi()                             # CPIAUCSL equivalent (CUSR0000SA0); core=True -> CPILFESL
    >>> mc.global_inflation("CHN", indicator="hcpi", freq="m")
    >>> mc.global_inflation_annual(indicator="hcpi", country="World")   # aggregates live under sheet == "Aggregate"
    >>> mc.world_ip()                           # Baumeister-Hamilton OECD+6 world IP index
    >>> mc.world_ip(vintage="2024-01-01")       # a real-time vintage
    >>> mc.gecon()                              # Baumeister-Korobilis-Lee global economic conditions
    >>> mc.igrea()                              # Kilian index (Dallas Fed = FRED IGREA)
    >>> mc.epu("GEPU_current"); mc.epu("US", table="all_country"); mc.epu(table="us_daily")
    >>> mc.wui("CHN"); mc.wui(table="T1")       # World Uncertainty Index by country / by region

Every function returns a tidy DataFrame (one row per observation, ISO `date`, float `value`) or, with
wide=True, dates as the index and series as columns. start/end are inclusive ISO-date prefixes
("2020", "2020-03", "2020-03-15"). Loaders are cached; call reload() after re-running the cleaner.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd

from . import paths

MACRO_CONTROLS = getattr(paths, "MACRO_CONTROLS", paths.DATA / "macro_controls")
MACRO_CONTROLS_CLEAN = getattr(paths, "MACRO_CONTROLS_CLEAN", MACRO_CONTROLS / "clean")
_HINT = "Run `.venv/Scripts/python.exe data/macro_controls/download_macro_controls.py` then `clean_macro_controls.py`."

FILES = {
    "fed_h15": "fed_h15.csv", "nyfed_effr": "nyfed_effr.csv", "wu_xia": "wu_xia.csv", "bauer_swanson": "bauer_swanson.csv",
    "jarocinski_karadi": "jarocinski_karadi.csv", "bls_cpi": "bls_cpi.csv", "world_bank_inflation": "world_bank_inflation.csv",
    "world_bank_inflation_annual": "world_bank_inflation_annual.csv", "baumeister_wip": "baumeister_wip.csv",
    "baumeister_wip_vintages": "baumeister_wip_vintages.csv", "dallasfed_igrea": "dallasfed_igrea.csv", "epu": "epu.csv", "wui": "wui.csv",
}


@lru_cache(maxsize=None)
def _load(name: str) -> pd.DataFrame:
    path = paths.require(MACRO_CONTROLS_CLEAN / FILES[name], _HINT)
    df = pd.read_csv(path, dtype={"flag": str, "country_code": str, "note": str, "data_source": str, "aggregation": str,
                                  "sample_country": str, "imf_country_code": str, "time": str},
                     keep_default_na=False, na_values=[""], low_memory=False)
    df["flag"] = df["flag"].fillna("")
    return df


def reload() -> None:
    """Forget cached files (after re-running clean_macro_controls.py)."""
    _load.cache_clear()


def _filtered(name: str, filters: dict, start: str | None, end: str | None, wide: bool, datecol: str = "date",
              wide_cols: str | Iterable[str] = "series_id") -> pd.DataFrame:
    df = _load(name)
    for col, val in filters.items():
        if val is None or col not in df.columns:
            continue
        vals = [val] if isinstance(val, (str, int, float)) else list(val)
        df = df[df[col].isin(vals)]
    if start is not None:
        df = df[df[datecol].astype(str) >= str(start)]
    if end is not None:
        e = str(end)
        df = df[df[datecol].astype(str).str[:len(e)] <= e]
    df = df.reset_index(drop=True)
    if wide:
        cols = [wide_cols] if isinstance(wide_cols, str) else list(wide_cols)
        w = df.pivot_table(index=datecol, columns=cols, values="value", aggfunc="first")
        if len(cols) == 1:
            w.columns = [str(c) for c in w.columns]
        return w.sort_index()
    return df


# ---------------------------------------------------------------- D30 -----------------------------------------------
def fed_funds(freq: str = "M", start: str | None = None, end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Effective federal funds rate from the Board's H.15 release. freq: "M" (= FRED FEDFUNDS, monthly average),
    "D" (= FRED DFF, every calendar day), "B" (business days) or "W" (Wednesday-ending weeks)."""
    return _filtered("fed_h15", {"freq": freq.upper()}, start, end, wide)


def effr(series: str | Iterable[str] | None = "EFFR_RATE", start: str | None = None, end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """NY Fed EFFR publication (2016-03 onwards): EFFR_RATE, EFFR_1ST_PERCENTILE .. EFFR_99TH_PERCENTILE, EFFR_VOLUME,
    EFFR_TARGET_RATE_FROM / _TO. series=None returns all of them."""
    return _filtered("nyfed_effr", {"series_id": series}, start, end, wide)


def shadow_rate(series: str | Iterable[str] | None = "SHADOW_RATE", start: str | None = None, end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Wu-Xia shadow federal funds rate (monthly, Atlanta Fed file, ends 2022-02). The file's EFFR column is the
    end-of-month effective rate; series=None returns both."""
    return _filtered("wu_xia", {"series_id": series}, start, end, wide)


# ---------------------------------------------------------------- D31 -----------------------------------------------
def policy_shocks(series: str | Iterable[str] | None = ("MPS", "MPS_ORTH"), monthly: bool = False, start: str | None = None,
                  end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Bauer-Swanson (2023) monetary policy surprises. monthly=False: one row per FOMC announcement (1988-02 .. 2019-12,
    with time and unscheduled flag; series=None gives every column incl. FF1/ED1-4/SP500/Treasury responses).
    monthly=True: the 'Monthly SVAR Data' sheet (1973-01 onwards; MPS / MPS_ORTH summed by month, plus IP, unemp, CPI ...)."""
    return _filtered("bauer_swanson", {"table": "monthly_svar" if monthly else "fomc_announcements", "series_id": series}, start, end, wide)


def jk_shocks(series: str | Iterable[str] | None = ("MP_pm", "CBI_pm"), monthly: bool = True, start: str | None = None,
              end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Jarocinski-Karadi monetary policy (MP_*) and central bank information (CBI_*) shocks, poor-man's sign
    restriction (_pm) and median rotation (_median) versions, plus the raw pc1 / SP500 surprises. monthly=True sums by
    month (1990-02 onwards, updated after each FOMC meeting); monthly=False is per announcement."""
    return _filtered("jarocinski_karadi", {"table": "monthly" if monthly else "announcements", "series_id": series}, start, end, wide)


# ---------------------------------------------------------------- D32 -----------------------------------------------
def us_cpi(core: bool = False, seasonal: str = "SA", series: str | Iterable[str] | None = None, start: str | None = None,
           end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """CPI-U index (1982-84=100) from the BLS API. Default all items SA (CUSR0000SA0 = FRED CPIAUCSL); core=True gives
    all items less food and energy (CUSR0000SA0L1E = CPILFESL); seasonal="NSA" the unadjusted twins; series=None with
    seasonal=None returns all five series (incl. energy CUSR0000SA0E)."""
    if series is None and seasonal is not None:
        sid = ("CUSR" if seasonal.upper() == "SA" else "CUUR") + "0000SA0" + ("L1E" if core else "")
        series = sid
    return _filtered("bls_cpi", {"series_id": series}, start, end, wide)


# ---------------------------------------------------------------- D33 -----------------------------------------------
def global_inflation(country: str | Iterable[str] | None = None, indicator: str = "hcpi", freq: str = "m", start: str | None = None,
                     end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """World Bank Global Database of Inflation, index levels. indicator: hcpi (headline), fcpi (food), ecpi (energy),
    ccpi (core), ppi, def (GDP deflator, quarterly only); freq "m" or "q"; country = ISO3 code(s) (column country_code).
    A country can appear on several rows of a sheet (different sources): raw_row tells them apart."""
    return _filtered("world_bank_inflation", {"sheet": f"{indicator}_{freq}", "country_code": country}, start, end, wide, wide_cols="country_code")


def global_inflation_annual(country: str | Iterable[str] | None = None, indicator: str = "hcpi", start: str | None = None,
                            end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Annual inflation rates (percent). indicator as above, or "aggregate" for the Aggregate sheet, where country_code
    holds the aggregate code (HCPI_GLOBAL_MED, HCPI_AE_AVE_GDP, ENERGY_EMDE_MED ...)."""
    sheet = "Aggregate" if indicator == "aggregate" else f"{indicator}_a"
    return _filtered("world_bank_inflation_annual", {"sheet": sheet, "country_code": country}, start, end, wide, datecol="year", wide_cols="country_code")


# ---------------------------------------------------------------- D34 -----------------------------------------------
def world_ip(vintage: str | None = None, start: str | None = None, end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Baumeister-Hamilton world (OECD + 6 non-member) industrial production index, monthly from 1958-01 (current file),
    or one real-time vintage (vintage="YYYY-MM-01", from 2012-03; see world_ip_vintages())."""
    if vintage is None:
        return _filtered("baumeister_wip", {"series_id": "WIP"}, start, end, wide)
    return _filtered("baumeister_wip_vintages", {"vintage": vintage}, start, end, wide, wide_cols="vintage")


def world_ip_vintages() -> list[str]:
    """Available vintage dates of the world IP index."""
    return sorted(_load("baumeister_wip_vintages")["vintage"].unique().tolist())


def gecon(series: str | Iterable[str] | None = "GECON", start: str | None = None, end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Baumeister-Korobilis-Lee global economic conditions indicator: GECON, GECON_STD, GECON3_SMOOTH, GECON3_STD (monthly, 1973-02 ->)."""
    return _filtered("baumeister_wip", {"series_id": series}, start, end, wide)


# ---------------------------------------------------------------- D35 -----------------------------------------------
def igrea(start: str | None = None, end: str | None = None, wide: bool = False) -> pd.DataFrame:
    """Kilian index of global real economic activity (Dallas Fed = FRED IGREA), monthly from 1968-01."""
    return _filtered("dallasfed_igrea", {}, start, end, wide)


# ---------------------------------------------------------------- D36 -----------------------------------------------
def epu(series: str | Iterable[str] | None = None, table: str | None = None, start: str | None = None, end: str | None = None,
        wide: bool = False) -> pd.DataFrame:
    """policyuncertainty.com indices. table: global (GEPU_current, GEPU_ppp), all_country (one column per country incl.
    'US', 'SCMP China', 'Mainland China'), us_news, us_legacy (three-component index and parts), us_daily, china_scmp,
    china_mainland. With a series and no table the series is looked up across tables."""
    return _filtered("epu", {"table": table, "series_id": series}, start, end, wide, wide_cols=("table", "series_id") if table is None else "series_id")


def wui(country: str | Iterable[str] | None = None, table: str = "T2", start: str | None = None, end: str | None = None,
        wide: bool = False) -> pd.DataFrame:
    """World Uncertainty Index (quarterly). table T2 = WUI by country (ISO3 in country_code / series_id), T1 = global and
    regional aggregates, T3/T4/T5 = word, total-word and page counts, T6 = 3-quarter weighted moving average (the
    authors' preferred country measure), T8 = world trade uncertainty (aggregates + by country); see column table_name."""
    return _filtered("wui", {"table": table, "series_id": country}, start, end, wide)


def describe() -> pd.DataFrame:
    """The series catalog of every macro-controls file (coverage and observation counts)."""
    return pd.read_csv(paths.require(MACRO_CONTROLS_CLEAN / "series_catalog.csv", _HINT))
