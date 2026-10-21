"""Download the raw files for every *Currency markets* row (D43-D50) of
data/Oil_Dedollarisation_Data_Tracker.xlsx, sheet "Data Sources", into ./currency_markets/raw.

Tracker ID -> source -> raw location
  D43  IMF / Boz et al. invoicing currency      raw/imf_invoicing/Section2.zip + all_countries_update.dta
                                                 (imf.org returns 403 to scripts; the authors' replication files
                                                 on Mendeley Data, doi 10.17632/6z6w78968m.1, carry the same dataset)
  D44  RMB trade settlement                      raw/safe/crossborder_receipts_payments_timeseries.xls  (SAFE: monthly
                                                 cross-border receipts & payments by currency, 2010-01 onwards) and
                                                 raw/safe/by_region/<year>.xlsx; PBoC RMB Internationalization Report
                                                 PDFs -> raw/pboc_rmb_report/<year>.pdf (best effort, HTML discovery)
  D45  IMF COFER                                 raw/imf_cofer/cofer_data.json (SDMX 3.0 API, whole dataflow) +
                                                 cofer_structure.json (code lists / labels)
  D46  SWIFT RMB Tracker                         NOT downloadable by script (403 / login wall) -> raw/swift_rmb_tracker/README.md
  D47  CIPS volumes                              raw/cips/*.pdf (English + Chinese "Statistical Business Data" tables,
                                                 current year monthly + historical annual) + the statistics page HTML
  D48  BIS Triennial FX turnover                 raw/bis_triennial/WS_DER_OTC_TOV_csv_flat.zip (BIS bulk file, ~14 MB)
  D49  US Treasury TIC MFH                       raw/tic/slt_table5.txt (latest 13 months) + raw/tic/mfhhis01.txt
                                                 (2000 -> last complete year); mfh.txt is the stale legacy file
  D50  Central bank gold                         gold.org Excel is behind a free registration (403 to scripts) ->
                                                 raw/wgc_gold/README.md; backups downloaded instead:
                                                 raw/imf_irfcl/gold_*.json (IMF IRFCL monthly gold, troy oz & USD) and
                                                 raw/worldbank/FI.RES.*.json (WDI annual reserves with / without gold)

Everything is recorded in raw/manifest.json (url, HTTP status, bytes, sha256, Last-Modified, timestamp).

Usage:
  python data/currency_markets/download_currency_markets.py               # everything
  python data/currency_markets/download_currency_markets.py --only safe tic
  python data/currency_markets/download_currency_markets.py --skip bis

Standard library only.
"""
import argparse
import hashlib
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
MANIFEST = RAW / "manifest.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")

# --------------------------------------------------------------------------------------
# Source definitions
# --------------------------------------------------------------------------------------
MENDELEY_DATASET = "6z6w78968m"
MENDELEY_VERSION = 1
MENDELEY_FILES_API = (f"https://data.mendeley.com/public-api/datasets/{MENDELEY_DATASET}/files"
                      f"?folder_id=root&version={MENDELEY_VERSION}")
MENDELEY_WANTED = "Section2.zip"          # Section3.zip (791 MB) is the bilateral trade matrix: not needed
INVOICING_DTA = "Data/all_countries_update.dta"
IMF_INVOICING_PAGE = ("https://www.imf.org/en/Publications/WP/Issues/2022/01/07/"
                      "Patterns-of-Invoicing-Currency-in-Global-Trade-511145")

SAFE_PAGE = "https://www.safe.gov.cn/en/2019/0919/1561.html"      # Cross-border Receipts and Payments by Non-banking Sectors
SAFE_TIMESERIES_TEXT = "Time-series Data of Cross-border Receipts and Payments"
SAFE_BY_REGION_RE = re.compile(r"Cross-border Receipts and Payments by Non-banking Sectors in (\d{4})\s*\(by Region\)")

PBOC_REPORTS_PAGE = "http://www.pbc.gov.cn/en/3688241/3688636/3828468/index.html"

IMF_API = "https://api.imf.org/external/sdmx/3.0"
COFER_DATA_URL = f"{IMF_API}/data/dataflow/IMF.STA/COFER/+/*"
COFER_STRUCTURE_URL = f"{IMF_API}/structure/dataflow/IMF.STA/COFER/+?references=all&detail=full"
IRFCL_GOLD = {   # key = COUNTRY.INDICATOR.SECTOR.FREQUENCY
    "gold_troy_oz": f"{IMF_API}/data/dataflow/IMF.STA/IRFCL/+/*.IRFCLDT1_IRFCL56V_FTO.*.M",
    "gold_usd": f"{IMF_API}/data/dataflow/IMF.STA/IRFCL/+/*.IRFCLDT1_IRFCL56_USD.*.M",
    "official_reserve_assets_usd": f"{IMF_API}/data/dataflow/IMF.STA/IRFCL/+/*.IRFCLDT1_IRFCL65_USD.*.M",
}
IRFCL_STRUCTURE_URL = f"{IMF_API}/structure/dataflow/IMF.STA/IRFCL/+?references=all&detail=full"

SWIFT_PAGE = ("https://www.swift.com/our-solutions/compliance-and-shared-services/business-intelligence/"
              "renminbi/rmb-tracker")

CIPS_PAGES = {
    "en": "https://www.cips.com.cn/kjjqgsyyingw/cipsfw/index.shtml",
    "cn": "https://www.cips.com.cn/kjjqgs/cipsfw/index.shtml",
}

BIS_BULK_URL = "https://data.bis.org/static/bulk/WS_DER_OTC_TOV_csv_flat.zip"

TIC_FILES = {
    # current table (last 13 months; the tracker's URL is the .html rendering of the same .txt)
    "slt_table5.txt": "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt",
    "slt_table5.html": "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.html",
    # history 2000-01 -> last complete year, one block per year, with series-break columns
    "mfhhis01.txt": "https://ticdata.treasury.gov/Publish/mfhhis01.txt",
    # legacy "current" file: no longer updated (stops at January 2023) - kept for the record only
    "mfh.txt": "https://ticdata.treasury.gov/Publish/mfh.txt",
}

WGC_PAGE = "https://www.gold.org/goldhub/data/gold-reserves-by-country"

WB_INDICATORS = {
    "FI.RES.TOTL.CD": "Total reserves (includes gold, current US$)",
    "FI.RES.XGLD.CD": "Total reserves minus gold (current US$)",
}
WB_URL = "https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&per_page=20000&page={page}"

SOURCES = ["imf_invoicing", "safe", "pboc", "imf_cofer", "swift", "cips", "bis", "tic", "wgc", "imf_irfcl", "worldbank"]


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, timeout=300, retries=4, backoff=5.0, headers=None):
    """GET url -> (bytes, response headers, status). Retries on 429/5xx and network errors."""
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*",
                                                   "Accept-Language": "en-GB,en;q=0.9", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), dict(r.headers), r.status
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise
    raise last


class Manifest:
    def __init__(self):
        self.entries = {}
        if MANIFEST.exists():
            self.entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.errors = []

    def record(self, rel, url, data, headers, status, **extra):
        path = RAW / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.entries[rel.replace("\\", "/")] = {
            "url": url, "status": status, "bytes": len(data), "sha256": sha256(path),
            "last_modified": headers.get("Last-Modified"), "content_type": headers.get("Content-Type"),
            "downloaded_at": now(), **extra,
        }
        print(f"  {rel:70} {len(data):>12,} B")
        return path

    def note(self, rel, **info):
        self.entries[rel.replace("\\", "/")] = {"downloaded_at": now(), **info}

    def fail(self, source, url, exc):
        msg = f"{source}: {url} -> {type(exc).__name__}: {exc}"
        print("  !! " + msg)
        self.errors.append(msg)

    def save(self):
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(self.entries, indent=2, sort_keys=True), encoding="utf-8")


def download(m, source, url, rel, **extra):
    try:
        data, headers, status = fetch(url)
    except Exception as e:                      # noqa: BLE001
        m.fail(source, url, e)
        return None
    return m.record(rel, url, data, headers, status, **extra)


def links(page_html, base_url):
    """(href, text) pairs with absolute hrefs and unescaped, whitespace-collapsed link text."""
    out = []
    for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, re.I | re.S):
        text = html.unescape(re.sub(r"<[^>]+>|\s+", " ", m.group(2))).strip()
        out.append((urllib.parse.urljoin(base_url, html.unescape(m.group(1))), text))
    return out


def write_readme(rel, text):
    path = RAW / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  {rel:70} (README)")


# --------------------------------------------------------------------------------------
# D43  IMF invoicing currency dataset (Mendeley replication files)
# --------------------------------------------------------------------------------------
def dl_imf_invoicing(m):
    print("D43 IMF invoicing currency dataset (Boz et al.), via Mendeley Data")
    try:
        data, headers, status = fetch(MENDELEY_FILES_API)
    except Exception as e:                      # noqa: BLE001
        m.fail("imf_invoicing", MENDELEY_FILES_API, e)
        return
    m.record("imf_invoicing/mendeley_files.json", MENDELEY_FILES_API, data, headers, status)
    files = json.loads(data)
    wanted = [f for f in files if f["filename"] == MENDELEY_WANTED]
    if not wanted:
        m.fail("imf_invoicing", MENDELEY_FILES_API, RuntimeError(f"{MENDELEY_WANTED} not in file list"))
        return
    f = wanted[0]
    url = f["content_details"]["download_url"]
    p = download(m, "imf_invoicing", url, f"imf_invoicing/{MENDELEY_WANTED}",
                 mendeley_sha256=f["content_details"].get("sha256_hash"), mendeley_size=f.get("size"))
    if p is None:
        return
    if m.entries[f"imf_invoicing/{MENDELEY_WANTED}"]["sha256"] != f["content_details"].get("sha256_hash"):
        m.fail("imf_invoicing", url, RuntimeError("sha256 does not match Mendeley's file record"))
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        if INVOICING_DTA not in names:
            m.fail("imf_invoicing", url, RuntimeError(f"{INVOICING_DTA} not in zip: {names[:10]}"))
            return
        data = z.read(INVOICING_DTA)
        for extra in ("Readme replication Section 2.docx",):
            if extra in names:
                m.record(f"imf_invoicing/{Path(extra).name}", url, z.read(extra), {}, 200, extracted_from=MENDELEY_WANTED)
    m.record(f"imf_invoicing/{Path(INVOICING_DTA).name}", url, data, {}, 200, extracted_from=MENDELEY_WANTED,
             note="Boz, Casas, Georgiadis, Gopinath, Le Mezo, Mehl & Nguyen (2022, JIE) invoicing shares, 1990-2019")
    # record that the primary (imf.org) is blocked for scripts
    try:
        fetch(IMF_INVOICING_PAGE, retries=1)
        m.note("imf_invoicing/imf_page", url=IMF_INVOICING_PAGE, status=200)
    except Exception as e:                      # noqa: BLE001
        m.note("imf_invoicing/imf_page", url=IMF_INVOICING_PAGE, status=getattr(e, "code", None),
               note="imf.org publications pages/attachments refuse scripted requests; Mendeley mirror used")


# --------------------------------------------------------------------------------------
# D44  SAFE cross-border receipts & payments by currency; PBoC RMB Internationalization Reports
# --------------------------------------------------------------------------------------
def dl_safe(m):
    print("D44 SAFE cross-border receipts and payments by non-banking sectors (by currency)")
    try:
        page, headers, status = fetch(SAFE_PAGE)
    except Exception as e:                      # noqa: BLE001
        m.fail("safe", SAFE_PAGE, e)
        return
    m.record("safe/page_1561.html", SAFE_PAGE, page, headers, status)
    ts = [(h, t) for h, t in links(page.decode("utf-8", "replace"), SAFE_PAGE) if SAFE_TIMESERIES_TEXT.lower() in t.lower()]
    if not ts:
        m.fail("safe", SAFE_PAGE, RuntimeError("time-series xls link not found on page"))
    else:
        href = ts[0][0]
        ext = Path(urllib.parse.urlparse(href).path).suffix or ".xls"
        download(m, "safe", href, f"safe/crossborder_receipts_payments_timeseries{ext}", link_text=ts[0][1])
    for h, t in links(page.decode("utf-8", "replace"), SAFE_PAGE):
        mt = SAFE_BY_REGION_RE.search(t)
        if mt:
            ext = Path(urllib.parse.urlparse(h).path).suffix or ".xlsx"
            download(m, "safe", h, f"safe/by_region/{mt.group(1)}{ext}", link_text=t)


def dl_pboc(m):
    print("D44 PBoC RMB Internationalization Reports (PDF, best effort)")
    try:
        page, headers, status = fetch(PBOC_REPORTS_PAGE, timeout=120)
    except Exception as e:                      # noqa: BLE001
        m.fail("pboc", PBOC_REPORTS_PAGE, e)
        return
    m.record("pboc_rmb_report/index.html", PBOC_REPORTS_PAGE, page, headers, status)
    base = PBOC_REPORTS_PAGE.rsplit("/", 1)[0] + "/"
    year_pages = sorted({h for h, _ in links(page.decode("utf-8", "replace"), PBOC_REPORTS_PAGE)
                         if re.fullmatch(re.escape(base) + r"\d+/index\.html", h)})
    found = 0
    for yp in year_pages:
        try:
            yhtml, _, _ = fetch(yp, timeout=120)
        except Exception as e:                  # noqa: BLE001
            m.fail("pboc", yp, e)
            continue
        ytxt = yhtml.decode("utf-8", "replace")
        ytitle = re.search(r"<title>(.*?)</title>", ytxt, re.S)
        year = (ytitle.group(1).strip() if ytitle else "").strip()
        articles = sorted({h for h, _ in links(ytxt, yp) if re.fullmatch(re.escape(yp[:-len("index.html")]) + r"\d+/index\.html", h)})
        pdfs = {h for h, _ in links(ytxt, yp) if h.lower().endswith(".pdf")}
        for ap in articles:
            try:
                ahtml, _, _ = fetch(ap, timeout=120)
            except Exception as e:              # noqa: BLE001
                m.fail("pboc", ap, e)
                continue
            pdfs |= {h for h, _ in links(ahtml.decode("utf-8", "replace"), ap) if h.lower().endswith(".pdf")}
        for i, h in enumerate(sorted(pdfs)):
            name = f"pboc_rmb_report/{year or 'report'}{'' if i == 0 else f'_{i+1}'}.pdf"
            if download(m, "pboc", h, name, year_page=yp):
                found += 1
    if not found:
        m.fail("pboc", PBOC_REPORTS_PAGE, RuntimeError("no report PDFs discovered"))
    write_readme("pboc_rmb_report/README.md", f"""# PBoC RMB Internationalization Reports (tracker D44, secondary)

Discovered from {PBOC_REPORTS_PAGE} (year pages -> article pages -> PDF). Only the years that the
English site lists with a downloadable PDF are here ({found} file(s) on {now()[:10]}); older editions are
reachable from the Chinese site (人民币国际化报告) by hand. The reports are narrative PDFs - the clean
pipeline does not parse them. The monthly RMB-settlement series used for D44 comes from SAFE instead
(`raw/safe/crossborder_receipts_payments_timeseries.xls`, "By currency: RMB / Foreign Currency").
""")


# --------------------------------------------------------------------------------------
# D45  IMF COFER
# --------------------------------------------------------------------------------------
def dl_imf_cofer(m):
    print("D45 IMF COFER (SDMX 3.0 API)")
    download(m, "imf_cofer", COFER_DATA_URL, "imf_cofer/cofer_data.json")
    download(m, "imf_cofer", COFER_STRUCTURE_URL, "imf_cofer/cofer_structure.json")


# --------------------------------------------------------------------------------------
# D46  SWIFT RMB Tracker (blocked)
# --------------------------------------------------------------------------------------
def dl_swift(m):
    print("D46 SWIFT RMB Tracker")
    status, note = None, ""
    try:
        data, headers, status = fetch(SWIFT_PAGE, retries=1)
        m.record("swift_rmb_tracker/rmb_tracker_page.html", SWIFT_PAGE, data, headers, status)
        note = "page fetched; monthly PDFs still need the swift.com form/login"
    except Exception as e:                      # noqa: BLE001
        status = getattr(e, "code", None)
        note = f"{type(e).__name__}: {e}"
        print(f"  swift.com -> {note}")
    m.note("swift_rmb_tracker/rmb_tracker_page.html", url=SWIFT_PAGE, status=status, note=note)
    write_readme("swift_rmb_tracker/README.md", f"""# SWIFT RMB Tracker (tracker D46) - manual step

swift.com answers scripted requests with HTTP {status} ("SWIFT site off-line" interstitial) and the monthly
RMB Tracker PDFs sit behind a free swift.com registration form, so nothing is downloaded automatically.

To fill this source by hand:
1. Open {SWIFT_PAGE} in a browser, register (free) and download the monthly "RMB Tracker" PDFs.
2. Record, per month, the headline figures SWIFT publishes: RMB share of global payments by value (%),
   RMB rank, RMB share excluding intra-eurozone payments and the top-5/top-10 currency shares, into
   `raw/swift_rmb_tracker/swift_rmb_tracker.csv` with columns
   `month,currency,share_pct,rank,basis,source_pdf` (basis = "all" or "ex_eurozone").
3. Re-run `clean_currency_markets.py`; it picks the CSV up and writes `clean/swift_rmb_tracker.csv`.
""")


# --------------------------------------------------------------------------------------
# D47  CIPS statistics
# --------------------------------------------------------------------------------------
def dl_cips(m):
    print("D47 CIPS statistics (PDF tables + statistics page)")
    for lang, url in CIPS_PAGES.items():
        try:
            page, headers, status = fetch(url, timeout=120)
        except Exception as e:                  # noqa: BLE001
            m.fail("cips", url, e)
            continue
        m.record(f"cips/statistics_page_{lang}.html", url, page, headers, status)
        txt = page.decode("utf-8", "replace")
        # the two "Statistical Business Data ... (Current Year) / (Historical Years)" PDFs sit in the Statistics block
        pdfs = []
        for h, t in links(txt, url):
            if h.lower().endswith(".pdf") and "articleFileDir" in h:
                pdfs.append((h, t))
        seen = set()
        for i, (h, t) in enumerate(pdfs):
            if h in seen:
                continue
            seen.add(h)
            download(m, "cips", h, f"cips/{lang}_{i+1}_{Path(urllib.parse.urlparse(h).path).name}", link_text=t)
        if not pdfs:
            m.fail("cips", url, RuntimeError("no statistics PDFs found on page"))


# --------------------------------------------------------------------------------------
# D48  BIS Triennial survey turnover (bulk)
# --------------------------------------------------------------------------------------
def dl_bis(m):
    print("D48 BIS OTC derivatives / FX turnover bulk file (WS_DER_OTC_TOV)")
    p = download(m, "bis", BIS_BULK_URL, "bis_triennial/WS_DER_OTC_TOV_csv_flat.zip")
    if p is not None:
        with zipfile.ZipFile(p) as z:
            print("   members:", [(i.filename, i.file_size) for i in z.infolist()])


# --------------------------------------------------------------------------------------
# D49  TIC major foreign holders
# --------------------------------------------------------------------------------------
def dl_tic(m):
    print("D49 US Treasury TIC - Major Foreign Holders of Treasury Securities")
    for name, url in TIC_FILES.items():
        download(m, "tic", url, f"tic/{name}")


# --------------------------------------------------------------------------------------
# D50  Central bank gold: WGC (blocked) -> IMF IRFCL + World Bank WDI
# --------------------------------------------------------------------------------------
def dl_wgc(m):
    print("D50 World Gold Council gold reserves by country")
    status, xlsx = None, []
    try:
        page, headers, status = fetch(WGC_PAGE, retries=1)
        m.record("wgc_gold/goldhub_page.html", WGC_PAGE, page, headers, status)
        xlsx = [(h, t) for h, t in links(page.decode("utf-8", "replace"), WGC_PAGE) if ".xlsx" in h.lower()]
        for h, t in xlsx:
            name = Path(urllib.parse.urlparse(h).path).name
            try:
                data, hd, st = fetch(h, retries=1)
                m.record(f"wgc_gold/{name}", h, data, hd, st, link_text=t)
            except Exception as e:              # noqa: BLE001
                m.note(f"wgc_gold/{name}", url=h, status=getattr(e, "code", None), note=f"{type(e).__name__}: {e}")
                print(f"  {name}: {type(e).__name__} {getattr(e, 'code', '')} (Goldhub login required)")
    except Exception as e:                      # noqa: BLE001
        m.fail("wgc", WGC_PAGE, e)
    write_readme("wgc_gold/README.md", f"""# World Gold Council - gold reserves by country (tracker D50) - manual step

{WGC_PAGE} lists the Excel files ({', '.join(Path(urllib.parse.urlparse(h).path).name for h, _ in xlsx) or 'none found'})
but the downloads need a free Goldhub registration (HTTP 403 to scripts). To use the WGC file:
1. Log in to Goldhub in a browser, download "World_official_gold_holdings_as_of_<Mon><Year>_IFS.xlsx" and
   "Quarterly_gold_and_FX_Reserves_<Q>_<Year>.xlsx" and drop them in this folder.
2. Re-run `clean_currency_markets.py` (it reports them in CHECKS.md but the cleaned gold series come from the
   IMF IRFCL backup, `raw/imf_irfcl/`, and the World Bank WDI annual backup, `raw/worldbank/`).
WGC's figures are themselves compiled from IMF IFS, so the IRFCL monthly series are the same underlying data for
the ~90 SDDS-reporting countries (China, Russia, India, Saudi Arabia, Türkiye, Poland ... included).
""")


def dl_imf_irfcl(m):
    print("D50 IMF IRFCL - monetary gold (troy ounces and USD), monthly, all reporters")
    for name, url in IRFCL_GOLD.items():
        download(m, "imf_irfcl", url, f"imf_irfcl/{name}.json")
    download(m, "imf_irfcl", IRFCL_STRUCTURE_URL, "imf_irfcl/irfcl_structure.json")


def dl_worldbank(m):
    print("D50 World Bank WDI - total reserves with and without gold (annual)")
    for ind, desc in WB_INDICATORS.items():
        page = 1
        while True:
            url = WB_URL.format(ind=ind, page=page)
            try:
                data, headers, status = fetch(url)
            except Exception as e:              # noqa: BLE001
                m.fail("worldbank", url, e)
                break
            m.record(f"worldbank/{ind}_p{page}.json", url, data, headers, status, description=desc)
            meta = json.loads(data)[0]
            if page >= int(meta.get("pages", 1)):
                break
            page += 1


DOWNLOADERS = {
    "imf_invoicing": dl_imf_invoicing, "safe": dl_safe, "pboc": dl_pboc, "imf_cofer": dl_imf_cofer,
    "swift": dl_swift, "cips": dl_cips, "bis": dl_bis, "tic": dl_tic, "wgc": dl_wgc,
    "imf_irfcl": dl_imf_irfcl, "worldbank": dl_worldbank,
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=SOURCES, help="only these sources")
    ap.add_argument("--skip", nargs="+", choices=SOURCES, default=[], help="skip these sources")
    args = ap.parse_args(argv)
    todo = [s for s in (args.only or SOURCES) if s not in args.skip]
    RAW.mkdir(parents=True, exist_ok=True)
    m = Manifest()
    t0 = time.time()
    for s in todo:
        try:
            DOWNLOADERS[s](m)
        except Exception as e:                  # noqa: BLE001
            m.fail(s, "-", e)
        m.save()
    m.save()
    print(f"\ndone in {time.time() - t0:.0f}s; manifest: {MANIFEST}")
    if m.errors:
        print("errors:")
        for e in m.errors:
            print("  - " + e)
    # blocked sources are expected (swift / wgc); anything else is a failure
    hard = [e for e in m.errors if not e.startswith(("swift:", "wgc:", "pboc:"))]
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
