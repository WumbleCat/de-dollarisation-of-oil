"""Download the raw files for the *Geopolitics* rows (D37-D42) of
data/Oil_Dedollarisation_Data_Tracker.xlsx, sheet "Data Sources", into data/geopolitics/raw/.

Tracker ID -> source -> raw location
  D37  Caldara & Iacoviello GPR index      raw/gpr/data_gpr_export.xls (monthly, 1900->) and
                                           raw/gpr/data_gpr_daily_recent.xls (daily, 1985->), + dated vintage copies
  D38  Global Sanctions Database (GSDB)    raw/gsdb/manual/  -- released by e-mail request only; the website
                                           (globalsanctionsdatabase.com) did not answer at all on 2026-10-21.
                                           See raw/gsdb/README.md; a hand-placed file is recorded as "manual".
  D39  US Treasury OFAC recent actions     raw/ofac/listing/page_NNN.html  (the paginated index, re-crawled every run)
                                           raw/ofac/actions/<slug>.html    (one page per action, 2010-> ; skipped if on disk)
                                           raw/ofac/sdn/{sdn,alt,add,sdn_comments}.csv + vintage copies (structured SDN list)
  D40  Baumeister & Hamilton (2019) shocks raw/baumeister_hamilton/BH2_supply_shocks.xlsx, BH2_demand_shocks.xlsx,
                                           OECD_plus6_industrial_production.xlsx, market-based_oil_price_shocks.xlsx
                                           (Google-Drive links from the author's research page) + dated vintage copies
  D41  Kaenzig (2021) oil supply news      raw/kanzig/oilSupplyNewsShocks_<vintage>.xlsx (every vintage in the GitHub
                                           repo dkaenzig/oilsupplynews), VARdata.xlsx, README.md
  D42  IMF PortWatch chokepoints           raw/portwatch/daily_chokepoints.json (all 28 chokepoints, daily 2019->, via
                                           the public ArcGIS REST table Daily_Chokepoints_Data, 1000 rows per call),
                                           chokepoints_database.json, disruptions_database.json + dated vintage copy

Everything is recorded in raw/manifest.json (url, HTTP status, bytes, sha256, Last-Modified, timestamp).
Re-running is safe: files already on disk are skipped (pass --refresh to redo them). --only <source> runs one source.
Uses only the standard library. No API keys are needed for any of these sources.

Usage:
  .venv/Scripts/python.exe data/geopolitics/download_geopolitics.py
  .venv/Scripts/python.exe data/geopolitics/download_geopolitics.py --only gpr portwatch
  .venv/Scripts/python.exe data/geopolitics/download_geopolitics.py --only ofac --ofac-workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent          # data/geopolitics
RAW = HERE / "raw"
MANIFEST = RAW / "manifest.json"
ROOT = HERE.parents[1]                           # repo root
CATEGORY = "Geopolitics"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
TODAY = date.today().isoformat()

# --------------------------------------------------------------------------------------
# Source definitions
# --------------------------------------------------------------------------------------
GPR_PAGE = "https://www.matteoiacoviello.com/gpr.htm"
GPR_FILES = {                                   # file name -> (url, what it is)
    "data_gpr_export.xls": ("https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
                            "monthly GPR, GPR Threats/Acts, historical GPR, country GPR indexes (1900->)"),
    "data_gpr_daily_recent.xls": ("https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls",
                                  "daily GPR, GPR Acts, GPR Threats (1985->)"),
}

GSDB_URL = "https://www.globalsanctionsdatabase.com/"

OFAC_BASE = "https://ofac.treasury.gov"
OFAC_LISTING = OFAC_BASE + "/recent-actions"      # Drupal view, 10 actions per page, ?page=N (0-based)
OFAC_PER_PAGE = 10
OFAC_SDN_FILES = {                                # structured SDN list files (treasury.gov -> S3)
    "sdn.csv": "https://www.treasury.gov/ofac/downloads/sdn.csv",
    "add.csv": "https://www.treasury.gov/ofac/downloads/add.csv",
    "alt.csv": "https://www.treasury.gov/ofac/downloads/alt.csv",
    "sdn_comments.csv": "https://www.treasury.gov/ofac/downloads/sdn_comments.csv",
}

# Baumeister & Hamilton (2019, AER) updated shock series: Google-Drive files linked from
# https://sites.google.com/view/cjsbaumeister/research (the page itself redirects scripts to a Google login;
# the download links work without one). Mirrored on https://econweb.ucsd.edu/~jhamilto/software.htm
BH_PAGE = "https://sites.google.com/view/cjsbaumeister/research"
BH_FILES = {                                      # file name -> (Google Drive id, what it is)
    "BH2_supply_shocks.xlsx": ("1OsA8btgm2rmDucUFngiLkwv4uywTDmya", "structural oil supply shocks, monthly 1975-02->"),
    "BH2_demand_shocks.xlsx": ("1neFXLrIvGwggebQRwjmtrWK-dfQZ9NH8",
                               "economic activity, oil consumption demand, oil inventory demand shocks, monthly 1975-02->"),
    "OECD_plus6_industrial_production.xlsx": ("1i5gl07FbEUoWQrIdSpB_ZWBcNlZuxm0R",
                                              "world industrial production index used in the BH VAR (monthly)"),
    "market-based_oil_price_shocks.xlsx": ("1_LMvR279GJl7U64wY0EsbZ4Kjv-if7N4",
                                           "Baumeister (2023) market-based oil price surprises + 2023 vintage of the BH shocks"),
}
GDRIVE_URL = "https://drive.google.com/uc?export=download&id={id}"

KANZIG_REPO = "dkaenzig/oilsupplynews"
KANZIG_TREE = f"https://api.github.com/repos/{KANZIG_REPO}/git/trees/HEAD?recursive=1"
KANZIG_RAW = f"https://raw.githubusercontent.com/{KANZIG_REPO}/HEAD/{{path}}"

PORTWATCH_PAGE = "https://portwatch.imf.org/"
ARCGIS = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/{service}/FeatureServer/0"
PORTWATCH_TABLES = {                              # file name -> (ArcGIS service, what it is)
    "daily_chokepoints.json": ("Daily_Chokepoints_Data",
                               "daily transit counts and capacity by vessel type for the 28 chokepoints (2019-01-01->)"),
    "chokepoints_database.json": ("PortWatch_chokepoints_database", "chokepoint metadata (id, name, lat/lon, shares)"),
    "disruptions_database.json": ("portwatch_disruptions_database", "PortWatch disruption events (type, dates, ports)"),
}
ARCGIS_PAGE = 1000                                # maxRecordCount of these services


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
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


def get(url: str, *, retries: int = 3, timeout: int = 120, headers: dict | None = None) -> tuple[bytes, dict, int]:
    """GET url -> (bytes, headers, status). Retries with back-off on 429/5xx and network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(), dict(resp.headers), resp.status
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))
                continue
            raise
        except (urllib.error.URLError, OSError) as e:
            last = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise last  # type: ignore[misc]


def fetch(url: str, dest: Path, *, expect: str = "file", refresh: bool = False, retries: int = 3,
          timeout: int = 120, headers: dict | None = None, extra: dict | None = None) -> dict:
    """GET url -> dest (via dest.part). Returns a manifest entry. expect: "file" | "json" | "csv" | "html".
    Refuses challenge/login pages when a file/JSON/CSV is expected. Skips existing files unless refresh."""
    if dest.exists() and not refresh:
        return {"url": url, "file": rel(dest), "status": "skipped (exists)", "bytes": dest.stat().st_size,
                "sha256": sha256(dest), **(extra or {})}
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        body, hdrs, status = get(url, retries=retries, timeout=timeout, headers=headers)
    except Exception as e:  # noqa: BLE001
        return {"url": url, "file": rel(dest), "status": f"failed: {e}", "downloaded_at": now(), **(extra or {})}
    if expect != "html" and looks_like_html(body[:512]):
        return {"url": url, "file": rel(dest), "status": "blocked (HTML page returned where a file was expected)",
                "http_status": status, "downloaded_at": now(), **(extra or {})}
    if expect == "json":
        try:
            json.loads(body)
        except ValueError:
            return {"url": url, "file": rel(dest), "status": "failed: response is not JSON", "http_status": status,
                    "downloaded_at": now(), **(extra or {})}
    if not body:
        return {"url": url, "file": rel(dest), "status": "failed: empty response", "downloaded_at": now(), **(extra or {})}
    part.write_bytes(body)
    part.replace(dest)
    return {"url": url, "file": rel(dest), "downloaded_at": now(), "status": "ok", "http_status": status,
            "bytes": dest.stat().st_size, "sha256": sha256(dest), "last_modified": hdrs.get("Last-Modified"),
            "content_type": hdrs.get("Content-Type"), **(extra or {})}


def vintage_copy(src: Path, stamp: str = TODAY) -> dict:
    """Keep a dated copy of a file whose content is revised by the publisher (indexes, shock series, PortWatch)."""
    vdir = src.parent / "vintages"
    vdir.mkdir(exist_ok=True)
    dst = vdir / f"{src.stem}_{stamp}{src.suffix}"
    if not dst.exists():
        shutil.copy2(src, dst)
    return {"file": rel(dst), "status": "ok", "note": "vintage copy", "bytes": dst.stat().st_size, "sha256": sha256(dst)}


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"tracker": f"data/Oil_Dedollarisation_Data_Tracker.xlsx [Data Sources], Category = {CATEGORY}", "sources": {}}


def save_manifest(m: dict) -> None:
    m["updated_at"] = now()
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


def bad(entry: dict) -> bool:
    return str(entry.get("status", "")).startswith(("failed", "blocked"))


# --------------------------------------------------------------------------------------
# D37  GPR index (Caldara & Iacoviello)
# --------------------------------------------------------------------------------------
def fetch_gpr(refresh: bool, **_) -> dict:
    files = []
    for name, (url, what) in GPR_FILES.items():
        dest = RAW / "gpr" / name
        entry = fetch(url, dest, refresh=True, extra={"what": what})      # always refresh: the index is revised monthly
        files.append(entry)
        if not bad(entry):
            files.append(vintage_copy(dest))
    return {"tracker_ids": ["D37"], "page": GPR_PAGE, "files": files,
            "note": "Files are re-downloaded on every run (the whole history is revised with each monthly update); "
                    "dated copies are kept in raw/gpr/vintages/."}


# --------------------------------------------------------------------------------------
# D38  Global Sanctions Database (manual: e-mail request)
# --------------------------------------------------------------------------------------
GSDB_README = """# Global Sanctions Database (GSDB) - tracker row D38

The GSDB (Felbermayr, Kirilakha, Syropoulos, Yalcin, Yotov) is **not downloadable by script**: the data set is
released on request for academic use, by e-mail from the authors / via the form on
https://www.globalsanctionsdatabase.com/ (the site did not answer at all - connection timed out from two
different networks - on 2026-10-21, so the request could not even be filed automatically).

Manual steps
1. Open https://www.globalsanctionsdatabase.com/ (or e-mail the GSDB team; the current release is GSDB-R4,
   covering 1950-2023) and request the data for academic use. Turnaround is a few days.
2. Save the delivered workbook unchanged in this folder as `manual/GSDB_<release>.xlsx` (e.g. `manual/GSDB_R4.xlsx`)
   together with the codebook / README that comes with it.
3. Re-run `download_geopolitics.py --only gsdb` so the file is recorded in raw/manifest.json, then
   `clean_geopolitics.py`, which builds `clean/gsdb.csv` and the Iran / Russia sanction dummies from it.

Until then the tracker status for D38 is "Access requested" (or "Blocked / unavailable" while the site is down).
"""


def fetch_gsdb(refresh: bool, **_) -> dict:
    folder = RAW / "gsdb"
    manual = folder / "manual"
    manual.mkdir(parents=True, exist_ok=True)
    readme = folder / "README.md"
    if not readme.exists():
        readme.write_text(GSDB_README, encoding="utf-8")
    # record whether the site answers at all (it is HTML-only either way; nothing is downloaded)
    try:
        _, _, status = get(GSDB_URL, retries=1, timeout=30)
        site = f"reachable (HTTP {status}); data still by e-mail request"
    except Exception as e:  # noqa: BLE001
        site = f"unreachable: {e}"
    files = [{"file": rel(p), "status": "manual", "bytes": p.stat().st_size, "sha256": sha256(p)}
             for p in sorted(manual.glob("*")) if p.is_file()]
    return {"tracker_ids": ["D38"], "page": GSDB_URL, "site_check": {"at": now(), "result": site}, "files": files,
            "note": "manual e-mail request, see raw/gsdb/README.md" if not files else ""}


# --------------------------------------------------------------------------------------
# D39  OFAC recent actions (HTML crawl) + SDN list files
# --------------------------------------------------------------------------------------
RE_TOTAL = re.compile(r"Displaying\s+\d+\s*-\s*\d+\s+of\s+([\d,]+)\s+results", re.I)
RE_ROW = re.compile(r'<div class="[^"]*search-result views-row">(.*?)</div>\s*</div>\s*</div>', re.S)
# the title link sits in the "font-sans-lg" div; a few actions link outside /recent-actions/ (/node/..., /recent-issues/...)
RE_LINK = re.compile(r'font-sans-lg[^"]*">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
RE_META = re.compile(r'line-height-sans-3[^"]*">\s*([A-Za-z]+ \d{1,2}, \d{4})\s*-\s*<a href="(/recent-actions/[^"]+)"[^>]*>(.*?)</a>', re.S)


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_listing(page_html: str) -> tuple[int | None, list[dict]]:
    """-> (total results, [{slug, url, title, date_text, category}]) from one listing page."""
    m = RE_TOTAL.search(page_html)
    total = int(m.group(1).replace(",", "")) if m else None
    rows = []
    for block in RE_ROW.findall(page_html):
        link = RE_LINK.search(block)
        meta = RE_META.search(block)
        if not link:
            continue
        href = link.group(1)
        path = urllib.parse.urlparse(href).path.strip("/")
        parts = path.split("/")
        # file name: the last path segment, prefixed by its parent when the page is not under /recent-actions/
        slug = parts[-1] if parts[0] == "recent-actions" and len(parts) == 2 else "__".join(parts[-2:])
        rows.append({"url": href if href.startswith("http") else OFAC_BASE + href, "slug": slug,
                     "title": _clean_text(link.group(2)),
                     "date_text": meta.group(1) if meta else "",
                     "category": _clean_text(meta.group(3)) if meta else "",
                     "category_url": (OFAC_BASE + meta.group(2)) if meta else ""})
    return total, rows


def fetch_ofac(refresh: bool, workers: int = 4, **_) -> dict:
    folder = RAW / "ofac"
    listing_dir, actions_dir, sdn_dir = folder / "listing", folder / "actions", folder / "sdn"
    for d in (listing_dir, actions_dir, sdn_dir):
        d.mkdir(parents=True, exist_ok=True)
    files, index = [], []

    # 1. the paginated index: always re-crawled (new actions shift every page), one HTML file per page
    first = fetch(OFAC_LISTING, listing_dir / "page_000.html", expect="html", refresh=True)
    files.append(first)
    if bad(first):
        return {"tracker_ids": ["D39"], "page": OFAC_LISTING, "files": files, "note": "listing page 0 failed"}
    total, rows = parse_listing((listing_dir / "page_000.html").read_text(encoding="utf-8", errors="replace"))
    if not total or not rows:
        files[-1]["status"] = "failed: could not parse the listing (layout changed?)"
        return {"tracker_ids": ["D39"], "page": OFAC_LISTING, "files": files}
    n_pages = math.ceil(total / OFAC_PER_PAGE)
    index.extend(rows)
    print(f"    listing: {total} actions on {n_pages} pages", flush=True)
    lock = threading.Lock()

    def one_page(p: int) -> dict:
        dest = listing_dir / f"page_{p:03d}.html"
        e = fetch(f"{OFAC_LISTING}?page={p}", dest, expect="html", refresh=True)
        if not bad(e):
            _, r = parse_listing(dest.read_text(encoding="utf-8", errors="replace"))
            with lock:
                index.extend(r)
        time.sleep(0.2)
        return e

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(one_page, p) for p in range(1, n_pages)]):
            files.append(fut.result())
    # de-duplicate (a new action published mid-crawl shifts one row onto two pages)
    seen, uniq = set(), []
    for r in index:
        if r["slug"] not in seen:
            seen.add(r["slug"])
            uniq.append(r)
    index = uniq
    (folder / "index.json").write_text(json.dumps({"crawled_at": now(), "total_reported": total, "pages": n_pages,
                                                   "actions": index}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"    listing: {len(index)} unique actions indexed", flush=True)

    # 2. one HTML page per action (skipped when already on disk - the pages are not revised)
    todo = [r for r in index if refresh or not (actions_dir / f"{r['slug']}.html").exists()]
    print(f"    actions: {len(todo)} pages to fetch, {len(index) - len(todo)} already on disk", flush=True)
    n_done = 0

    def one_action(r: dict) -> dict:
        e = fetch(r["url"], actions_dir / f"{r['slug']}.html", expect="html", refresh=refresh,
                  extra={"slug": r["slug"], "date_text": r["date_text"]})
        time.sleep(0.25)
        return e

    action_entries = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(one_action, r) for r in todo]):
            action_entries.append(fut.result())
            n_done += 1
            if n_done % 250 == 0:
                print(f"    actions: {n_done}/{len(todo)}", flush=True)
    n_bad = sum(bad(e) for e in action_entries)
    on_disk = len(list(actions_dir.glob("*.html")))
    files.append({"file": "ofac/actions/", "status": "ok" if not n_bad else f"failed: {n_bad} pages failed",
                  "pages_fetched_this_run": len(action_entries) - n_bad, "pages_on_disk": on_disk,
                  "failed_slugs": [e["slug"] for e in action_entries if bad(e)]})

    # 3. the structured SDN list files (a current snapshot; dated copies kept)
    for name, url in OFAC_SDN_FILES.items():
        dest = sdn_dir / name
        e = fetch(url, dest, expect="csv", refresh=True)
        files.append(e)
        if not bad(e):
            files.append(vintage_copy(dest))
    return {"tracker_ids": ["D39"], "page": OFAC_LISTING, "listing_total": total, "listing_pages": n_pages,
            "actions_indexed": len(index), "files": files,
            "note": "listing re-crawled every run; action pages fetched once; SDN csv snapshot + vintages"}


# --------------------------------------------------------------------------------------
# D40  Baumeister & Hamilton structural shocks
# --------------------------------------------------------------------------------------
def fetch_baumeister_hamilton(refresh: bool, **_) -> dict:
    files = []
    for name, (gid, what) in BH_FILES.items():
        dest = RAW / "baumeister_hamilton" / name
        entry = fetch(GDRIVE_URL.format(id=gid), dest, refresh=True, extra={"what": what})   # revised: always refresh
        if not bad(entry) and dest.read_bytes()[:2] != b"PK":
            entry["status"] = "failed: not an xlsx (Google Drive returned something else)"
            dest.unlink(missing_ok=True)
        files.append(entry)
        if not bad(entry):
            files.append(vintage_copy(dest))
    return {"tracker_ids": ["D40"], "page": BH_PAGE, "files": files,
            "note": "shock series are re-estimated with every update: dated copies in raw/baumeister_hamilton/vintages/"}


# --------------------------------------------------------------------------------------
# D41  Kaenzig oil supply news shocks (GitHub)
# --------------------------------------------------------------------------------------
def fetch_kanzig(refresh: bool, **_) -> dict:
    files = []
    try:
        body, _, _ = get(KANZIG_TREE, headers={"Accept": "application/vnd.github+json"})
        tree = [t["path"] for t in json.loads(body)["tree"] if t["type"] == "blob"]
    except Exception as e:  # noqa: BLE001
        return {"tracker_ids": ["D41"], "page": f"https://github.com/{KANZIG_REPO}", "files": [],
                "note": f"failed to list the repository: {e}"}
    (RAW / "kanzig").mkdir(parents=True, exist_ok=True)
    (RAW / "kanzig" / "tree.json").write_text(json.dumps({"listed_at": now(), "paths": tree}, indent=1), encoding="utf-8")
    for path in sorted(tree):
        if not path.lower().endswith((".xlsx", ".xls", ".csv", ".md")):
            continue
        dest = RAW / "kanzig" / path.replace("/", "__")
        files.append(fetch(KANZIG_RAW.format(path=path), dest, expect="html" if path.endswith(".md") else "file",
                           refresh=refresh))
    vint = sorted(re.findall(r"oilSupplyNewsShocks_(\d{4}M\d{2})\.xlsx", " ".join(tree)))
    return {"tracker_ids": ["D41"], "page": f"https://github.com/{KANZIG_REPO}", "vintages": vint,
            "latest_vintage": vint[-1] if vint else None, "files": files,
            "note": "every vintage file in the repo is kept; the cleaner uses the latest one and keeps a vintage column"}


# --------------------------------------------------------------------------------------
# D42  IMF PortWatch (ArcGIS REST)
# --------------------------------------------------------------------------------------
def arcgis_query(service: str, **params) -> dict:
    url = ARCGIS.format(service=service) + "/query?" + urllib.parse.urlencode({"f": "json", **params})
    body, _, _ = get(url, timeout=180)
    payload = json.loads(body)
    if "error" in payload:
        raise RuntimeError(f"{service}: {payload['error']}")
    return payload


def fetch_portwatch_table(service: str, dest: Path, *, refresh: bool, what: str) -> dict:
    """Pull every row of an ArcGIS feature table (paged by resultOffset) into one JSON file."""
    if dest.exists() and not refresh:
        return {"file": rel(dest), "status": "skipped (exists)", "bytes": dest.stat().st_size, "sha256": sha256(dest), "what": what}
    try:
        total = arcgis_query(service, where="1=1", returnCountOnly="true")["count"]
        meta_body, _, _ = get(ARCGIS.format(service=service) + "?f=pjson")
        meta = json.loads(meta_body)
        features, fields, offset = [], None, 0
        while True:
            page = arcgis_query(service, where="1=1", outFields="*", returnGeometry="false",
                                orderByFields="ObjectId", resultOffset=offset, resultRecordCount=ARCGIS_PAGE)
            fields = fields or page.get("fields")
            feats = page.get("features", [])
            features.extend(f["attributes"] for f in feats)
            offset += len(feats)
            if not feats or not page.get("exceededTransferLimit", False) and len(feats) < ARCGIS_PAGE:
                break
            if offset >= total + ARCGIS_PAGE:          # safety: never loop forever
                break
        if len(features) != total:
            return {"file": rel(dest), "status": f"failed: fetched {len(features)} rows but the service reports {total}",
                    "downloaded_at": now(), "what": what}
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = {"service": service, "url": ARCGIS.format(service=service), "downloaded_at": now(), "count": total,
               "data_last_edit_ms": meta.get("editingInfo", {}).get("dataLastEditDate"), "fields": fields,
               "features": features}
        dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return {"url": out["url"], "file": rel(dest), "status": "ok", "rows": total, "downloaded_at": now(),
                "bytes": dest.stat().st_size, "sha256": sha256(dest), "what": what}
    except Exception as e:  # noqa: BLE001
        return {"url": ARCGIS.format(service=service), "file": rel(dest), "status": f"failed: {e}", "downloaded_at": now(), "what": what}


def fetch_portwatch(refresh: bool, **_) -> dict:
    files = []
    for name, (service, what) in PORTWATCH_TABLES.items():
        dest = RAW / "portwatch" / name
        entry = fetch_portwatch_table(service, dest, refresh=True, what=what)   # daily table grows: always refresh
        files.append(entry)
        if not bad(entry) and name == "daily_chokepoints.json":
            files.append(vintage_copy(dest))
    return {"tracker_ids": ["D42"], "page": PORTWATCH_PAGE, "files": files,
            "note": "ArcGIS REST, no key; 1000 rows per call; daily table re-pulled every run with a dated copy"}


SOURCES = {
    "gpr": fetch_gpr,
    "gsdb": fetch_gsdb,
    "ofac": fetch_ofac,
    "baumeister_hamilton": fetch_baumeister_hamilton,
    "kanzig": fetch_kanzig,
    "portwatch": fetch_portwatch,
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=sorted(SOURCES), help="run only these sources")
    ap.add_argument("--refresh", action="store_true", help="re-download files that already exist")
    ap.add_argument("--ofac-workers", type=int, default=4, help="parallel connections for the OFAC crawl (default 4)")
    a = ap.parse_args(argv)

    RAW.mkdir(exist_ok=True)
    manifest = load_manifest()
    failed = []
    for name, fn in SOURCES.items():
        if a.only and name not in a.only:
            continue
        print(f"[{name}] ...", flush=True)
        t0 = time.time()
        result = fn(a.refresh, workers=a.ofac_workers)
        result["run_at"] = now()
        manifest["sources"][name] = result
        for f in result["files"]:
            print(f"    {str(f.get('status', '?'))[:60]:<60} {f.get('file', '')}  {f.get('bytes', f.get('rows', ''))}")
            if bad(f):
                failed.append((name, f.get("file")))
        if result.get("note"):
            print(f"    note: {result['note']}")
        print(f"    {time.time() - t0:.0f}s")
        save_manifest(manifest)
    print(f"manifest: {MANIFEST.relative_to(ROOT).as_posix()}")
    if failed:
        print("FAILED/BLOCKED:", failed, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
