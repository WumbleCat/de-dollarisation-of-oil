"""bristolpy - built-in data library for the oil de-dollarisation project.

Sub-libraries:
    bristolpy.fundamental   oil fundamentals: demand, production, imports, exports, stocks, refinery
                            intake/output ... from JODI, plus EIA STEO/WPSR, Eurostat, Energy Institute, Comtrade
    bristolpy.jodi          low-level access to the compiled JODI table (query by any dimension)
    bristolpy.currency      currency markets (tracker D43-D50): invoicing shares, COFER, SAFE RMB settlement, CIPS,
                            BIS FX turnover, TIC Treasury holders, central-bank gold
    bristolpy.paths         where the data files live

    >>> from bristolpy import fundamental as f
    >>> f.demand("China", product="Total oil products")
    >>> f.production(["Saudi Arabia", "Russian Federation"], product="Crude oil", wide=True)
    >>> from bristolpy import currency as c
    >>> c.cofer(currency=["USD", "CNY"], wide=True)
"""
from . import currency, fundamental, jodi, paths

__all__ = ["currency", "fundamental", "jodi", "paths"]
__version__ = "0.1.0"
