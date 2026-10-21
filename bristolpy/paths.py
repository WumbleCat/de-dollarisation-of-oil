"""Where the project's data lives, relative to the repo root (the folder containing pyproject.toml)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# JODI-Oil (data/jodi): download_jodi.py -> raw/, clean_jodi.py -> balances/, compile_jodi.py -> clean/final_clean/
JODI = DATA / "jodi"
JODI_RAW = JODI / "raw"
JODI_MANIFEST = JODI_RAW / "manifest.json"
JODI_BALANCES = JODI / "balances"
JODI_FINAL = JODI / "clean" / "final_clean" / "jodi_oil.csv"   # compiled long file (large); bristolpy reads JODI_BALANCES
JODI_FINAL_CHECKS = JODI / "clean" / "final_clean" / "CHECKS.md"

# Fundamentals (tracker rows D01-D12): data/fundamentals/clean_fundamentals.py -> clean/
FUNDAMENTALS = DATA / "fundamentals"
FUNDAMENTALS_CLEAN = FUNDAMENTALS / "clean"

# Currency markets (tracker rows D43-D50): data/currency_markets/clean_currency_markets.py -> clean/
CURRENCY_MARKETS = DATA / "currency_markets"
CURRENCY_MARKETS_RAW = CURRENCY_MARKETS / "raw"
CURRENCY_MARKETS_CLEAN = CURRENCY_MARKETS / "clean"

TRACKER_XLSX = DATA / "Oil_Dedollarisation_Data_Tracker.xlsx"


def require(path: Path, hint: str) -> Path:
    """Return `path` or raise a FileNotFoundError that says which script produces it."""
    if not path.exists():
        rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
        raise FileNotFoundError(f"{rel} not found. {hint}")
    return path
