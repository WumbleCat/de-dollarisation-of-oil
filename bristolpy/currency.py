"""bristolpy.currency - the *Currency markets* rows (D43-D50) of the data tracker, as cleaned by
data/currency_markets/clean_currency_markets.py.

    >>> from bristolpy import currency as c
    >>> c.invoicing("JPN")                                   # Boz et al. invoicing shares, 1990-2019
    >>> c.cofer(currency="USD", freq="Q")                   # IMF COFER: USD share of allocated reserves, quarterly
    >>> c.rmb_share()                                        # SAFE: RMB share of China's cross-border receipts/payments
    >>> c.safe_crossborder(flow="Receipts", group="by_currency")
    >>> c.cips()                                             # CIPS transactions / value
    >>> c.fx_turnover_by_currency(currency=["USD", "CNY"])    # BIS Triennial, share of 200%
    >>> c.fx_turnover(instrument_code="B")                   # BIS Triennial spot turnover by currency pair
    >>> c.treasury_holders("China, Mainland")                # TIC major foreign holders, USD bn
    >>> c.gold_reserves("RUS")                               # IMF IRFCL monetary gold, tonnes / USD
    >>> c.gold_reserves_annual("RUS")                        # World Bank WDI implied gold value, annual
    >>> c.sources(); c.catalog(); c.tracker_status()

Every function returns a pandas DataFrame; string arguments accept a single value or a list and filter by equality.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import pandas as pd

from . import paths

HINT = ("Run `python data/currency_markets/download_currency_markets.py` then "
        "`python data/currency_markets/clean_currency_markets.py` (all checks must pass).")

SOURCES = {  # name -> (file, description)
    "invoicing": ("imf_invoicing_currency.csv", "D43 Boz et al. (IMF/ECB) invoicing currency shares, annual 1990-2019, % of exports/imports"),
    "safe_crossborder": ("safe_crossborder_by_currency.csv", "D44 SAFE cross-border receipts & payments of non-banking sectors by transaction / currency, monthly + annual, 100 million CNY or USD"),
    "rmb_share": ("safe_rmb_share.csv", "D44 derived: RMB share (%) of China's cross-border receipts, payments and total"),
    "cofer": ("imf_cofer.csv", "D45 IMF COFER reserves by currency: shares (%) and USD, quarterly + annual, world / advanced / EMDE"),
    "swift": ("swift_rmb_tracker.csv", "D46 SWIFT RMB Tracker headline shares (only if hand-collected)"),
    "cips": ("cips_volumes.csv", "D47 CIPS transactions and value (bn CNY), monthly current year + annual history"),
    "fx_turnover": ("bis_fx_turnover.csv", "D48 BIS Triennial global FX turnover by instrument x counterparty x currency pair, USD mn/day"),
    "fx_turnover_by_currency": ("bis_fx_turnover_by_currency.csv", "D48 derived: turnover and share of 200% per currency"),
    "treasury_holders": ("tic_major_foreign_holders.csv", "D49 TIC Major Foreign Holders of Treasury Securities, monthly, USD bn"),
    "gold_reserves": ("imf_irfcl_gold_reserves.csv", "D50 IMF IRFCL monetary gold: troy oz, tonnes, USD, monthly"),
    "gold_reserves_annual": ("wb_gold_reserves_annual.csv", "D50 World Bank WDI reserves with / without gold and implied gold value, annual"),
    "catalog": ("series_catalog.csv", "coverage of every series in the clean files"),
    "tracker_status": ("tracker_status.csv", "Status / Date retrieved / Saved file rows for the tracker workbook"),
}


@lru_cache(maxsize=None)
def _load(name: str) -> pd.DataFrame:
    fname, _ = SOURCES[name]
    path = paths.require(paths.CURRENCY_MARKETS_CLEAN / fname, HINT)
    date_cols = [c for c in ("date",) if c in pd.read_csv(path, nrows=0).columns]
    return pd.read_csv(path, parse_dates=date_cols, low_memory=False)


def _filtered(name: str, **eq) -> pd.DataFrame:
    df = _load(name)
    for col, val in eq.items():
        if val is None:
            continue
        if col not in df.columns:
            raise KeyError(f"{name}: no column {col!r}; columns are {list(df.columns)}")
        vals = [val] if isinstance(val, (str, int, float)) else list(val)
        df = df[df[col].isin(vals)]
    return df.reset_index(drop=True)


def _window(df: pd.DataFrame, start=None, end=None, col="date") -> pd.DataFrame:
    if start is not None:
        df = df[df[col] >= pd.Timestamp(str(start))]
    if end is not None:
        df = df[df[col] <= pd.Timestamp(str(end))]
    return df.reset_index(drop=True)


def sources() -> pd.DataFrame:
    """Table of the currency-markets files available through this module."""
    rows = []
    for name, (fname, desc) in SOURCES.items():
        p = paths.CURRENCY_MARKETS_CLEAN / fname
        rows.append({"function": f"currency.{name}()", "file": f"data/currency_markets/clean/{fname}",
                     "available": p.exists(), "description": desc})
    return pd.DataFrame(rows)


# -- D43 -------------------------------------------------------------------------------
def invoicing(iso3: str | Iterable[str] | None = None, flow: str | Iterable[str] | None = None,
              currency: str | Iterable[str] | None = None, wide: bool = False) -> pd.DataFrame:
    """Invoicing currency shares (% of the country's exports / imports). flow: "Export" | "Import";
    currency: USD, EUR, Home, Other, Unclassified, Other_Excl_USDEUR. wide=True -> currencies as columns."""
    df = _filtered("invoicing", iso3=iso3, flow=flow, currency=currency)
    if wide:
        df = df.pivot_table(index=["country", "iso3", "year", "flow"], columns="currency", values="share_pct").reset_index()
        df.columns.name = None
    return df


# -- D44 -------------------------------------------------------------------------------
def safe_crossborder(flow: str | Iterable[str] | None = None, group: str | Iterable[str] | None = None,
                     item: str | Iterable[str] | None = None, unit_currency: str = "USD", freq: str = "M",
                     start=None, end=None) -> pd.DataFrame:
    """SAFE cross-border receipts / payments / balance of non-banking sectors. flow: Receipts | Payments | Balance;
    group: total | by_transaction | by_currency | memo; item e.g. "Goods", "RMB", "USD"; unit_currency "USD" or "CNY"
    (values in 100 million); freq "M" or "A"."""
    df = _filtered("safe_crossborder", flow=flow, group=group, item=item, unit_currency=unit_currency, freq=freq)
    return _window(df, start, end)


def rmb_share(freq: str = "M", start=None, end=None) -> pd.DataFrame:
    """RMB share (%) of China's cross-border receipts, payments and total (derived from the SAFE table, USD sheet)."""
    return _window(_filtered("rmb_share", freq=freq), start, end)


# -- D45 -------------------------------------------------------------------------------
def cofer(currency: str | Iterable[str] | None = None, country_code: str = "G001", indicator_code: str = "AFXRA",
          transformation: str = "share_pct", freq: str = "Q", start=None, end=None, wide: bool = False) -> pd.DataFrame:
    """IMF COFER. Defaults: world (G001; G110 advanced, G200 EMDE), allocated reserves (AFXRA; TFXRA total, UFXRA
    unallocated), shares in % (or transformation="usd"), quarterly. currency: USD, EUR, CNY, JPY, GBP, AUD, CAD, CHF,
    OTHC, T (all) and legacy DEM, FRF, NLG, ECU. wide=True -> currencies as columns."""
    df = _filtered("cofer", currency_code=currency, country_code=country_code, indicator_code=indicator_code,
                   transformation=transformation, freq=freq)
    df = _window(df, start, end)
    if wide:
        df = df.pivot_table(index=["country_code", "country", "freq", "period", "date"], columns="currency_code", values="value").reset_index()
        df.columns.name = None
    return df


# -- D46 -------------------------------------------------------------------------------
def swift(currency: str | Iterable[str] | None = None, basis: str | None = None) -> pd.DataFrame:
    """SWIFT RMB Tracker headline shares - available only after the manual collection step (see raw/swift_rmb_tracker/README.md)."""
    return _filtered("swift", currency=currency, basis=basis)


# -- D47 -------------------------------------------------------------------------------
def cips(freq: str | None = None) -> pd.DataFrame:
    """CIPS transactions and value (bn CNY). freq "M" (current year, monthly) or "A" (annual since 2015)."""
    return _filtered("cips", freq=freq)


# -- D48 -------------------------------------------------------------------------------
def fx_turnover(instrument_code: str | Iterable[str] | None = "A", counterparty_code: str | Iterable[str] | None = "A",
                currency_1: str | Iterable[str] | None = None, currency_2: str | Iterable[str] | None = None,
                year: int | Iterable[int] | None = None) -> pd.DataFrame:
    """BIS Triennial global OTC FX turnover (USD mn, daily average in April, net-net). instrument_code: A total, B spot,
    E outright forwards, H FX swaps, I currency swaps, R options; counterparty_code: A total, B reporting dealers,
    C other financial institutions, U non-financial customers. currency_2 == "TO1" gives single-currency rows."""
    return _filtered("fx_turnover", instrument_code=instrument_code, counterparty_code=counterparty_code,
                     currency_1=currency_1, currency_2=currency_2, year=year)


def fx_turnover_by_currency(currency: str | Iterable[str] | None = None, year: int | Iterable[int] | None = None,
                            wide: bool = False) -> pd.DataFrame:
    """Per-currency turnover and share of 200% (TO1 = total = 200%; OTH = residual other currencies)."""
    df = _filtered("fx_turnover_by_currency", currency=currency, year=year)
    if wide:
        df = df.pivot_table(index="year", columns="currency", values="share_pct_of_200").reset_index()
        df.columns.name = None
    return df


# -- D49 -------------------------------------------------------------------------------
def treasury_holders(country: str | Iterable[str] | None = None, row_type: str | Iterable[str] | None = None,
                     start=None, end=None, wide: bool = False) -> pd.DataFrame:
    """TIC Major Foreign Holders of Treasury securities (USD bn, end of month). row_type: country | all_other |
    grand_total | memo (For. Official, Treasury Bills, T-Bonds & Notes). Country names as published, e.g.
    "China, Mainland", "Korea, South", "United Kingdom". wide=True -> countries as columns."""
    df = _window(_filtered("treasury_holders", country=country, row_type=row_type), start, end)
    if wide:
        df = df.pivot_table(index=["period", "date"], columns="country", values="holdings_usd_bn").reset_index()
        df.columns.name = None
    return df


# -- D50 -------------------------------------------------------------------------------
def gold_reserves(iso3: str | Iterable[str] | None = None, sector_code: str = "S1XS1311", start=None, end=None,
                  wide: bool = False) -> pd.DataFrame:
    """IMF IRFCL monetary gold by reporter: gold_troy_oz, gold_tonnes, gold_usd (national valuation - several countries
    use book value, see CHECKS.md), official_reserve_assets_usd. sector_code S1XS1311 = monetary authorities + central
    government (the headline), S1X / S1311 split where reported. Rows flagged implausible_volume_in_source have the
    reported ounce figure kept but the derived volume blanked. wide=True -> tonnes with countries as columns."""
    df = _window(_filtered("gold_reserves", iso3=iso3, sector_code=sector_code), start, end)
    if wide:
        df = df.pivot_table(index=["period", "date"], columns="iso3", values="gold_tonnes").reset_index()
        df.columns.name = None
    return df


def gold_reserves_annual(iso3: str | Iterable[str] | None = None, start=None, end=None) -> pd.DataFrame:
    """World Bank WDI: total reserves, reserves ex gold and the implied gold value (USD, year end, market valuation)."""
    df = _filtered("gold_reserves_annual", iso3=iso3)
    if start is not None:
        df = df[df.year >= int(start)]
    if end is not None:
        df = df[df.year <= int(end)]
    return df.reset_index(drop=True)


# -- meta ------------------------------------------------------------------------------
def catalog() -> pd.DataFrame:
    return _load("catalog")


def tracker_status() -> pd.DataFrame:
    return _load("tracker_status")


def reload():
    """Drop every cached table (after re-running the pipeline)."""
    _load.cache_clear()
