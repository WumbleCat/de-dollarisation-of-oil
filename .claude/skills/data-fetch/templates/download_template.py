"""Download the raw files for the *<CATEGORY>* rows (<ID RANGE>) of
data/Oil_Dedollarisation_Data_Tracker.xlsx, sheet "Data Sources", into data/<category_slug>/raw/.

Tracker ID -> source -> raw location
  <IDS>   <Source name>   raw/<source_slug>/<file>   (<access notes>)

Everything is recorded in raw/manifest.json (url, HTTP status, bytes, sha256, Last-Modified, timestamp).
Re-running is safe: files already on disk are skipped (pass --refresh to redo them). --only <source> runs one source.
Uses only the standard library. API keys are read from ./.env at the repo root (never hard-coded).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent          # data/<category_slug>
RAW = HERE / "raw"
MANIFEST = RAW / "manifest.json"
ROOT = HERE.parents[1]                           # repo root
CATEGORY = "<Category as written in the tracker>"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) de-dollarisation-oil research downloader"
TODAY = date.today().isoformat()


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


def need_key(name: str) -> str:
    key = load_env().get(name)
    if not key:
        sys.exit(f"{name} is not set: add `{name}=<key>` to {ROOT / '.env'} (free key; see tracker Findings)")
    return key


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


def fetch(url: str, dest: Path, *, expect: str = "file", retries: int = 3, timeout: int = 120, refresh: bool = False,
          headers: dict | None = None) -> dict:
    """GET url -> dest (via dest.part). Returns a manifest entry. expect: "file" | "json" | "csv" | "html".
    Refuses challenge pages when a file/JSON/CSV is expected. Honours Retry-After. Skips existing files unless refresh."""
    rel = dest.relative_to(RAW).as_posix()
    if dest.exists() and not refresh:
        return {"url": url, "file": rel, "status": "skipped (exists)", "bytes": dest.stat().st_size, "sha256": sha256(dest)}
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp, part.open("wb") as out:
                shutil.copyfileobj(resp, out)
                status, ctype, lastmod = resp.status, resp.headers.get("Content-Type", ""), resp.headers.get("Last-Modified")
            with part.open("rb") as f:
                head = f.read(512)
            if expect != "html" and looks_like_html(head):
                part.unlink(missing_ok=True)
                return {"url": url, "file": rel, "status": "blocked (HTML challenge page returned)", "http_status": status,
                        "downloaded_at": now()}
            if part.stat().st_size == 0:
                raise OSError("empty response")
            part.replace(dest)
            return {"url": url, "file": rel, "downloaded_at": now(), "status": "ok", "http_status": status,
                    "bytes": dest.stat().st_size, "sha256": sha256(dest), "last_modified": lastmod, "content_type": ctype}
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 503) and attempt < retries:
                time.sleep(float(e.headers.get("Retry-After", 2 ** attempt)))
                continue
            if e.code in (401, 403, 404):
                break
        except (urllib.error.URLError, OSError) as e:
            last_err = e
        time.sleep(2 ** attempt)
    part.unlink(missing_ok=True)
    return {"url": url, "file": rel, "status": f"failed: {last_err}", "downloaded_at": now()}


def vintage_copy(src: Path, stamp: str = TODAY) -> dict:
    """Keep a dated copy of a file whose content is revised by the publisher (forecasts, shock series ...)."""
    vdir = src.parent / "vintages"
    vdir.mkdir(exist_ok=True)
    dst = vdir / f"{src.stem}_{stamp}{src.suffix}"
    if not dst.exists():
        shutil.copy2(src, dst)
    return {"file": dst.relative_to(RAW).as_posix(), "status": "ok", "note": "vintage copy", "sha256": sha256(dst)}


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
def fetch_fred(refresh: bool) -> dict:
    """Example: FRED series via the JSON API (the CSV endpoint is blocked by Akamai for scripts)."""
    key = need_key("FRED_API_KEY")
    series = {"DCOILBRENTEU": "D13", "DCOILWTICO": "D14"}          # series id -> tracker id(s)
    files = []
    for sid, ids in series.items():
        for kind, path in (("observations", RAW / "fred" / f"{sid}.json"), ("series", RAW / "fred" / f"{sid}_meta.json")):
            url = f"https://api.stlouisfed.org/fred/{'series/observations' if kind == 'observations' else 'series'}?" + \
                  urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json"})
            entry = fetch(url, path, expect="json", refresh=refresh)
            entry["url"] = entry["url"].replace(key, "<FRED_API_KEY>")       # never persist the key
            entry.update({"series": sid, "tracker_ids": ids})
            files.append(entry)
            time.sleep(0.5)
    return {"tracker_ids": sorted({i for v in series.values() for i in v.split(",")}), "files": files}


def fetch_manual_example(refresh: bool) -> dict:
    """Example of a source that cannot be scripted: record hand-placed files, document the manual step."""
    folder = RAW / "<source_slug>"
    folder.mkdir(parents=True, exist_ok=True)
    readme = folder / "README.md"
    if not readme.exists():
        readme.write_text("# <Source>\n\nManual download: <steps>. Save as `<expected file name>` in this folder.\n", encoding="utf-8")
    files = [{"file": p.relative_to(RAW).as_posix(), "status": "manual", "bytes": p.stat().st_size, "sha256": sha256(p)}
             for p in folder.glob("*") if p.name != "README.md"]
    return {"tracker_ids": ["Dxx"], "files": files, "note": "manual download, see README.md" if not files else ""}


SOURCES = {
    "fred": fetch_fred,
    # "<source_slug>": fetch_<source_slug>,
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
        manifest["sources"][name] = result
        for f in result["files"]:
            print(f"    {f.get('status', '?'):<28} {f.get('file', '')}  {f.get('bytes', '')}")
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
