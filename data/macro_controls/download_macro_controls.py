"""Download the raw files for the *Macro controls* rows (D30-D36) of
data/Oil_Dedollarisation_Data_Tracker.xlsx, sheet "Data Sources", into data/macro_controls/raw/.

Tracker ID -> source -> raw location
  D30  Fed funds rate            raw/fed_h15/H15_data.zip        Federal Reserve H.15 data-download package (SDMX-ML);
                                                                 RIFSPFF_N.D = FRED DFF, RIFSPFF_N.M = FRED FEDFUNDS
       (cross-check)             raw/nyfed_effr/effr.csv         NY Fed EFFR with percentiles & volume, 2016-03 onwards
       (ZLB alternative)         raw/wu_xia/WuXiaShadowRate.xlsx Atlanta Fed Wu-Xia shadow rate (publication stopped 2022-02)
  D31  Monetary policy shocks    raw/bauer_swanson/FOMC_Bauer_Swanson.xlsx   Bauer & Swanson (2023) FOMC surprises + monthly SVAR data
                                 raw/jarocinski_karadi/shocks_fed_jk_{m,t}.csv  Jarocinski-Karadi shocks, updated on GitHub
  D32  US CPI                    raw/bls_cpi/cpi_<y0>_<y1>.json  BLS public API v1 (no key; 10-year windows): CUSR0000SA0 = FRED
                                                                 CPIAUCSL, CUSR0000SA0L1E = CPILFESL, + NSA twins and energy
  D33  Global inflation          raw/world_bank_inflation/Inflation-data.xlsx   World Bank Global Database of Inflation (link
                                                                 scraped from the brief page: it changes with each release)
  D34  World industrial prod.    raw/baumeister/OECD_plus6_industrial_production.xlsx  Baumeister & Hamilton (2019) world IP index,
                                 raw/baumeister/WIP_vintages.xlsx, raw/baumeister/GECON_indicator.xlsx  (Google Drive links scraped
                                                                 from sites.google.com/site/cjsbaumeister/datasets)
  D35  Global real activity      raw/dallasfed_igrea/igrea.xlsx  Kilian index, maintained by the Dallas Fed (= FRED IGREA)
  D36  Policy uncertainty        raw/epu/*.xlsx|csv              policyuncertainty.com: global, all-country, US monthly + daily,
                                                                 China (SCMP) and China mainland-paper EPU
       (alternative)             raw/wui/WUI_Data.xlsx           World Uncertainty Index (Ahir, Bloom, Furceri), quarterly
  D30/D32/D35 (optional)         raw/fred/<SERIES>.json          FRED JSON API, only when FRED_API_KEY is set in ./.env; the
                                                                 CSV endpoint is blocked by Akamai for scripts

Everything is recorded in raw/manifest.json (url, HTTP status, bytes, sha256, Last-Modified, timestamp).
Re-running is safe: files already on disk are skipped (pass --refresh to redo them). --only <source> runs one source.
Revised publications (shock series, WB release, Baumeister, IGREA) get a dated copy in raw/<source>/vintages/.
Uses only the standard library. API keys are read from ./.env at the repo root (never hard-coded).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent          # data/macro_controls
RAW = HERE / "raw"
MANIFEST = RAW / "manifest.json"
ROOT = HERE.parents[1]                           # repo root
CATEGORY = "Macro controls"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) de-dollarisation-oil research downloader"
TODAY = date.today().isoformat()

# --------------------------------------------------------------------------------------
# source URLs
# --------------------------------------------------------------------------------------
H15_ZIP_URL = "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H15&filetype=zip"
NYFED_EFFR_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.csv?startDate=2016-03-01"
WU_XIA_URL = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/datafiles/cqer/research/"
              "wu-xia-shadow-federal-funds-rate/WuXiaShadowRate.xlsx")
BAUER_SWANSON_URL = "https://www.michaeldbauer.com/files/FOMC_Bauer_Swanson.xlsx"
JK_URLS = {
    "shocks_fed_jk_m.csv": "https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/main/shocks_fed_jk_m.csv",
    "shocks_fed_jk_t.csv": "https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/main/shocks_fed_jk_t.csv",
}
BLS_API_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"     # no key: 10 years/call, 25 series/call, 25 calls/day
BLS_SERIES = {
    "CUSR0000SA0": "CPI-U all items, SA (FRED CPIAUCSL)",
    "CUSR0000SA0L1E": "CPI-U all items less food and energy, SA (FRED CPILFESL)",
    "CUSR0000SA0E": "CPI-U energy, SA (FRED CPIENGSL)",
    "CUUR0000SA0": "CPI-U all items, NSA (FRED CPIAUCNS)",
    "CUUR0000SA0L1E": "CPI-U all items less food and energy, NSA (FRED CPILFENS)",
}
BLS_FIRST_YEAR = 1947
WB_INFLATION_PAGE = "https://www.worldbank.org/en/research/brief/inflation-database"
BAUMEISTER_PAGE = "https://sites.google.com/site/cjsbaumeister/datasets"
BAUMEISTER_FILES = {   # anchor text on the datasets page -> (expected file name, fallback Google Drive id)
    "Monthly World Industrial Production (WIP) index": ("OECD_plus6_industrial_production.xlsx", "1i5gl07FbEUoWQrIdSpB_ZWBcNlZuxm0R"),
    "Real-time vintages from 2012M3": ("WIP_vintages.xlsx", "1F-DcHt0VrzQ1tqDXNqgOBarG08IdsLH_"),
    "Monthly Global Economic Conditions (GECON) indicator": ("GECON_indicator.xlsx", "1-xGp5-PvgjoAcDQuw09nq4Kgoj16hqsu"),
}
IGREA_URL = "https://www.dallasfed.org/-/media/Documents/research/igrea/igrea.xlsx"
EPU_URLS = {
    "Global_Policy_Uncertainty_Data.xlsx": "https://www.policyuncertainty.com/media/Global_Policy_Uncertainty_Data.xlsx",
    "All_Country_Data.xlsx": "https://www.policyuncertainty.com/media/All_Country_Data.xlsx",
    "US_Policy_Uncertainty_Data.xlsx": "https://www.policyuncertainty.com/media/US_Policy_Uncertainty_Data.xlsx",
    "All_Daily_Policy_Data.csv": "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv",
    "China_Policy_Uncertainty_Data.xlsx": "https://www.policyuncertainty.com/media/China_Policy_Uncertainty_Data.xlsx",
    "China_Mainland_Paper_EPU.xlsx": "https://www.policyuncertainty.com/media/China_Mainland_Paper_EPU.xlsx",
}
WUI_PAGE = "https://worlduncertaintyindex.com/data/"
FRED_SERIES = {"DFF": "D30", "FEDFUNDS": "D30", "CPIAUCSL": "D32", "CPILFESL": "D32", "IGREA": "D35"}


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def load_env() -> dict[str, str]:
    """KEY=value lines from ./.env (comments and blanks ignored); os.environ wins."""
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k in env or k.endswith("_API_KEY")})
    return env


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_html(head: bytes) -> bool:
    s = head.lstrip()[:64].lower()
    return s.startswith(b"<!doctype html") or s.startswith(b"<html")


def rel(path: Path) -> str:
    return path.relative_to(RAW).as_posix()


def fetch(url: str, dest: Path, *, expect: str = "file", retries: int = 3, timeout: int = 180, refresh: bool = False,
          headers: dict | None = None, data: bytes | None = None) -> dict:
    """GET (or POST when data is given) url -> dest (via dest.part). Returns a manifest entry.
    expect: "file" | "json" | "csv" | "html". Refuses challenge pages when a file/JSON/CSV is expected.
    Honours Retry-After. Skips existing files unless refresh."""
    if dest.exists() and not refresh:
        return {"url": url, "file": rel(dest), "status": "skipped (exists)", "bytes": dest.stat().st_size,
                "sha256": sha256(dest)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp, part.open("wb") as out:
                shutil.copyfileobj(resp, out)
                status = resp.status
                ctype = resp.headers.get("Content-Type", "")
                lastmod = resp.headers.get("Last-Modified")
                cdisp = resp.headers.get("Content-Disposition", "")
            with part.open("rb") as f:
                head = f.read(512)
            if expect != "html" and looks_like_html(head):
                part.unlink(missing_ok=True)
                return {"url": url, "file": rel(dest), "status": "blocked (HTML page returned instead of a file)",
                        "http_status": status, "downloaded_at": now()}
            if expect == "json" and not head.lstrip().startswith((b"{", b"[")):
                part.unlink(missing_ok=True)
                return {"url": url, "file": rel(dest), "status": "failed: response is not JSON", "http_status": status,
                        "downloaded_at": now()}
            if part.stat().st_size == 0:
                raise OSError("empty response")
            part.replace(dest)
            entry = {"url": url, "file": rel(dest), "downloaded_at": now(), "status": "ok", "http_status": status,
                     "bytes": dest.stat().st_size, "sha256": sha256(dest), "last_modified": lastmod, "content_type": ctype}
            if cdisp:
                entry["content_disposition"] = cdisp
            return entry
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503) and attempt < retries:
                time.sleep(float(e.headers.get("Retry-After", 2 ** attempt)))
                continue
            if e.code in (400, 401, 403, 404):
                break
        except (urllib.error.URLError, OSError) as e:
            last_err = e
        time.sleep(2 ** attempt)
    part.unlink(missing_ok=True)
    return {"url": url, "file": rel(dest), "status": f"failed: {last_err}", "downloaded_at": now()}


def fetch_text(url: str, timeout: int = 120) -> str:
    """GET a web page (HTML) as text; raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def vintage_copy(src: Path, stamp: str = TODAY) -> dict:
    """Keep a dated copy of a file whose content is revised by the publisher (forecasts, shock series ...)."""
    vdir = src.parent / "vintages"
    vdir.mkdir(exist_ok=True)
    dst = vdir / f"{src.stem}_{stamp}{src.suffix}"
    if not dst.exists():
        shutil.copy2(src, dst)
    return {"file": rel(dst), "status": "ok", "note": "vintage copy", "bytes": dst.stat().st_size, "sha256": sha256(dst)}


def with_vintage(entry: dict, dest: Path, files: list) -> None:
    """Append entry, plus a vintage copy when the file is present on disk."""
    files.append(entry)
    if dest.exists():
        files.append(vintage_copy(dest))


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"tracker": f"data/Oil_Dedollarisation_Data_Tracker.xlsx [Data Sources], Category = {CATEGORY}", "sources": {}}


def save_manifest(m: dict) -> None:
    m["updated_at"] = now()
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------------------
# one function per source: returns {"tracker_ids": [...], "files": [manifest entries], ...}
# --------------------------------------------------------------------------------------
def fetch_fed_h15(refresh: bool) -> dict:
    """D30: the complete H.15 release as the Board's SDMX-ML zip (all series, all frequencies). The cleaner keeps
    the RIFSPFF_N.* (effective federal funds rate) series: daily (= FRED DFF), business daily, weekly, monthly
    (= FRED FEDFUNDS). FRED itself is blocked for scripts, the Board's own download is not."""
    entry = fetch(H15_ZIP_URL, RAW / "fed_h15" / "H15_data.zip", refresh=refresh, timeout=300)
    return {"tracker_ids": ["D30"], "files": [entry],
            "note": "SDMX-ML package of the whole H.15 release; cleaner extracts RIFSPFF_N.D/B/WW/M"}


def fetch_nyfed_effr(refresh: bool) -> dict:
    """D30 cross-check: the NY Fed's own EFFR publication (rate, percentiles, volume, target range), 2016-03 onwards."""
    entry = fetch(NYFED_EFFR_URL, RAW / "nyfed_effr" / "effr.csv", expect="csv", refresh=refresh)
    return {"tracker_ids": ["D30"], "files": [entry], "note": "cross-check for the H.15 daily EFFR"}


def fetch_wu_xia(refresh: bool) -> dict:
    """D30 alternative: Wu-Xia shadow federal funds rate from the Atlanta Fed (monthly, 1960-01 .. 2022-02)."""
    entry = fetch(WU_XIA_URL, RAW / "wu_xia" / "WuXiaShadowRate.xlsx", refresh=refresh)
    return {"tracker_ids": ["D30"], "files": [entry],
            "note": "Atlanta Fed stopped updating the shadow rate in 2022-02 (covers both ZLB episodes in the tracker note)"}


def fetch_bauer_swanson(refresh: bool) -> dict:
    """D31: Bauer & Swanson (2023) FOMC announcement surprises (1988-02 .. 2019-12) and monthly SVAR data."""
    dest = RAW / "bauer_swanson" / "FOMC_Bauer_Swanson.xlsx"
    files: list = []
    with_vintage(fetch(BAUER_SWANSON_URL, dest, refresh=refresh), dest, files)
    return {"tracker_ids": ["D31"], "files": files, "note": "direct link from michaeldbauer.com/research; updated irregularly"}


def fetch_jarocinski_karadi(refresh: bool) -> dict:
    """D31: Jarocinski-Karadi (2020) monetary policy / central bank information shocks, updated on GitHub
    (monthly aggregates and per-announcement)."""
    files: list = []
    for name, url in JK_URLS.items():
        dest = RAW / "jarocinski_karadi" / name
        with_vintage(fetch(url, dest, expect="csv", refresh=refresh), dest, files)
    return {"tracker_ids": ["D31"], "files": files, "note": "github.com/marekjarocinski/jkshocks_update_fed"}


def fetch_bls_cpi(refresh: bool) -> dict:
    """D32: CPI-U from the BLS public API v1 (no key needed; 10 years and 25 series per call, 25 calls a day).
    One JSON per 10-year window; the window containing the current year is always re-fetched."""
    files: list = []
    this_year = date.today().year
    for y0 in range(BLS_FIRST_YEAR, this_year + 1, 10):
        y1 = min(y0 + 9, this_year)
        dest = RAW / "bls_cpi" / f"cpi_{y0}_{y1}.json"
        body = json.dumps({"seriesid": list(BLS_SERIES), "startyear": str(y0), "endyear": str(y1)}).encode()
        entry = fetch(BLS_API_V1, dest, expect="json", refresh=refresh or y1 >= this_year,
                      headers={"Content-Type": "application/json"}, data=body)
        entry.update({"window": [y0, y1], "series": list(BLS_SERIES)})
        if entry["status"] == "ok":
            payload = json.loads(dest.read_text(encoding="utf-8"))
            if payload.get("status") != "REQUEST_SUCCEEDED":
                entry["status"] = f"failed: BLS {payload.get('status')} {payload.get('message')}"
                dest.unlink(missing_ok=True)
            time.sleep(0.5)
        files.append(entry)
    return {"tracker_ids": ["D32"], "files": files, "series": BLS_SERIES,
            "note": "BLS flat files (download.bls.gov) need a contact e-mail in the User-Agent; the v1 API does not"}


def fetch_world_bank_inflation(refresh: bool) -> dict:
    """D33: World Bank Global Database of Inflation (Ha, Kose & Ohnsorge). The xlsx link changes with each release,
    so it is scraped from the brief page every run; a dated vintage copy is kept."""
    files: list = []
    try:
        page = html.unescape(fetch_text(WB_INFLATION_PAGE))
        links = sorted(set(re.findall(r'https://thedocs\.worldbank\.org/[^"\'\s]+/Inflation-data\.xlsx', page)))
    except Exception as e:  # noqa: BLE001
        return {"tracker_ids": ["D33"], "files": [{"url": WB_INFLATION_PAGE, "file": "world_bank_inflation/Inflation-data.xlsx",
                                                   "status": f"failed: could not read the brief page ({e!r})", "downloaded_at": now()}]}
    if not links:
        return {"tracker_ids": ["D33"], "files": [{"url": WB_INFLATION_PAGE, "file": "world_bank_inflation/Inflation-data.xlsx",
                                                   "status": "failed: no Inflation-data.xlsx link on the brief page", "downloaded_at": now()}]}
    dest = RAW / "world_bank_inflation" / "Inflation-data.xlsx"
    with_vintage(fetch(links[0], dest, refresh=refresh, timeout=300), dest, files)
    return {"tracker_ids": ["D33"], "files": files, "page": WB_INFLATION_PAGE, "links_found": links}


def baumeister_drive_ids() -> dict[str, str]:
    """anchor text -> Google Drive file id, scraped from the (classic) Google Sites datasets page."""
    page = html.unescape(fetch_text(BAUMEISTER_PAGE))
    found = {}
    for m in re.finditer(r'<a[^>]+href="https://drive\.google\.com/uc\?export=download&id=([^"&]+)"[^>]*>(.*?)</a>', page, re.S):
        anchor = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
        found[anchor] = m.group(1)
    return found


def fetch_baumeister(refresh: bool) -> dict:
    """D34: Baumeister & Hamilton (2019) monthly world industrial production index (OECD + 6 major non-member
    economies, 1958-01 onwards), its real-time vintages, and the Baumeister-Korobilis-Lee GECON indicator."""
    files: list = []
    try:
        found = baumeister_drive_ids()
        note = f"{len(found)} Drive links on the datasets page"
    except Exception as e:  # noqa: BLE001
        found, note = {}, f"datasets page not readable ({e!r}); fallback Drive ids used"
    for anchor, (name, fallback) in BAUMEISTER_FILES.items():
        fid = next((v for k, v in found.items() if k.startswith(anchor)), fallback)
        dest = RAW / "baumeister" / name
        entry = fetch(f"https://drive.google.com/uc?export=download&id={fid}", dest, refresh=refresh, timeout=300)
        entry.update({"anchor": anchor, "drive_id": fid, "scraped": fid != fallback or anchor in found})
        if name == "WIP_vintages.xlsx":
            files.append(entry)          # already a vintage archive
        else:
            with_vintage(entry, dest, files)
    return {"tracker_ids": ["D34"], "files": files, "page": BAUMEISTER_PAGE, "note": note}


def fetch_dallasfed_igrea(refresh: bool) -> dict:
    """D35: Kilian's index of global real economic activity, maintained and corrected by the Dallas Fed
    (the same series FRED publishes as IGREA)."""
    dest = RAW / "dallasfed_igrea" / "igrea.xlsx"
    files: list = []
    with_vintage(fetch(IGREA_URL, dest, refresh=refresh), dest, files)
    return {"tracker_ids": ["D35"], "files": files, "note": "dallasfed.org/research/igrea; revised every month"}


def fetch_epu(refresh: bool) -> dict:
    """D36: Baker-Bloom-Davis economic policy uncertainty indices from policyuncertainty.com (direct files)."""
    files: list = []
    for name, url in EPU_URLS.items():
        files.append(fetch(url, RAW / "epu" / name, expect="csv" if name.endswith(".csv") else "file", refresh=refresh))
    return {"tracker_ids": ["D36"], "files": files}


def fetch_wui(refresh: bool) -> dict:
    """D36 alternative: World Uncertainty Index (Ahir, Bloom & Furceri), quarterly by country; link scraped from the
    data page because the upload path carries the release month."""
    try:
        page = html.unescape(fetch_text(WUI_PAGE))
        links = sorted(set(re.findall(r'https://worlduncertaintyindex\.com/wp-content/uploads/[^"\'\s]+/WUI_Data\.xlsx', page)))
    except Exception as e:  # noqa: BLE001
        return {"tracker_ids": ["D36"], "files": [{"url": WUI_PAGE, "file": "wui/WUI_Data.xlsx",
                                                   "status": f"failed: could not read the data page ({e!r})", "downloaded_at": now()}]}
    if not links:
        return {"tracker_ids": ["D36"], "files": [{"url": WUI_PAGE, "file": "wui/WUI_Data.xlsx",
                                                   "status": "failed: no WUI_Data.xlsx link on the data page", "downloaded_at": now()}]}
    entry = fetch(links[-1], RAW / "wui" / "WUI_Data.xlsx", refresh=refresh)
    return {"tracker_ids": ["D36"], "files": [entry], "page": WUI_PAGE, "links_found": links}


def fetch_fred(refresh: bool) -> dict:
    """D30/D32/D35 optional: the same series straight from FRED's JSON API when FRED_API_KEY is in ./.env (the
    cleaner then cross-checks them against the primary publishers). Without a key the step is skipped, not failed."""
    key = load_env().get("FRED_API_KEY")
    if not key:
        return {"tracker_ids": ["D30", "D32", "D35"], "files": [],
                "note": "skipped: FRED_API_KEY not set in ./.env (primary publishers H.15 / BLS / Dallas Fed are used instead)"}
    files = []
    for sid, ids in FRED_SERIES.items():
        for kind, path in (("series/observations", RAW / "fred" / f"{sid}.json"), ("series", RAW / "fred" / f"{sid}_meta.json")):
            url = f"https://api.stlouisfed.org/fred/{kind}?" + urllib.parse.urlencode(
                {"series_id": sid, "api_key": key, "file_type": "json"})
            entry = fetch(url, path, expect="json", refresh=refresh or kind == "series/observations")
            entry["url"] = entry["url"].replace(key, "<FRED_API_KEY>")       # never persist the key
            entry.update({"series": sid, "tracker_ids": ids})
            files.append(entry)
            time.sleep(0.5)
    return {"tracker_ids": ["D30", "D32", "D35"], "files": files}


SOURCES = {
    "fed_h15": fetch_fed_h15,
    "nyfed_effr": fetch_nyfed_effr,
    "wu_xia": fetch_wu_xia,
    "bauer_swanson": fetch_bauer_swanson,
    "jarocinski_karadi": fetch_jarocinski_karadi,
    "bls_cpi": fetch_bls_cpi,
    "world_bank_inflation": fetch_world_bank_inflation,
    "baumeister": fetch_baumeister,
    "dallasfed_igrea": fetch_dallasfed_igrea,
    "epu": fetch_epu,
    "wui": fetch_wui,
    "fred": fetch_fred,
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=sorted(SOURCES), help="run only these sources")
    ap.add_argument("--refresh", action="store_true", help="re-download files that already exist")
    a = ap.parse_args(argv)

    RAW.mkdir(exist_ok=True)
    manifest = load_manifest()
    failed = []
    for name, fn in SOURCES.items():
        if a.only and name not in a.only:
            continue
        print(f"[{name}] ...", flush=True)
        result = fn(a.refresh)
        result["tracker_ids"] = sorted(result["tracker_ids"])
        result["run_at"] = now()
        manifest["sources"][name] = result
        if result.get("note") and not result["files"]:
            print(f"    {result['note']}")
        for f in result["files"]:
            print(f"    {str(f.get('status', '?')):<40} {f.get('file', '')}  {f.get('bytes', '')}")
            if str(f.get("status", "")).startswith(("failed", "blocked")):
                failed.append((name, f.get("file")))
        save_manifest(manifest)
    print(f"manifest: {MANIFEST.relative_to(ROOT).as_posix()}")
    if failed:
        print("FAILED/BLOCKED:", failed, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
