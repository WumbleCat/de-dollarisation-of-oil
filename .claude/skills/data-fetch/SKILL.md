---
name: data-fetch
description: Download (fetch, pull, refresh, update) the raw files for one or more tracker rows (D01-D50), a variable, a source or a whole category into ./data/<category>/raw/<source>/ with a manifest, by writing or extending that category's download_<category>.py. Use whenever the user asks to get, download, fetch, pull, scrape, refresh or update data; follow with the data-store skill to clean it.
---

# Data fetch

Raw data lives in **`./data/<category slug>/raw/<source slug>/`** and nowhere else (rule:
`.claude/rules/data-layout.md`). One script per category, `data/<category>/download_<category>.py`, with one
function per source. The existing pipelines `data/jodi/download_jodi.py` and
`data/fundamentals/download_fundamentals.py` are the reference implementations: match their style.

## Workflow

1. **Resolve the rows** with the `data-sources` skill:
   `.venv/Scripts/python.exe .claude/skills/data-sources/scripts/tracker_sources.py D13 D19` (or `-c <category>`).
   Note `Category` (-> folder), `Specific series / ticker`, `URL`, `Access`, `Format / API`, `Findings / limitations`.
   Then read `.claude/skills/data-sources/reference.md` for the access pattern (direct file / API key /
   registration / bot-protected / paid).
2. **Pick the folder**: `data/<category slug>/`. Create `raw/` on first use. Source slug = short lower-case name of
   the provider + dataset (`fred`, `eia_spot`, `world_bank_pink_sheet`, `gpr`, `portwatch`, `tic_mfh` ...).
   JODI rows (D02, D09) are an exception: `data/jodi/download_jodi.py` owns them.
3. **Extend, don't duplicate**: if `download_<category>.py` exists, add a `fetch_<source>()` function and register
   it in its `SOURCES` table. Only create the script when the category folder has none; start from
   `templates/download_template.py` in this skill folder.
4. **Write the downloader** (stdlib `urllib` + `json`/`csv`; pandas only for parsing checks):
   - browser `User-Agent`, timeout, 3 retries with back-off, honour `Retry-After` on 429/503;
   - API keys from `./.env` (`FRED_API_KEY`, `EIA_API_KEY`, `COMTRADE_API_KEY`); abort with a clear message naming
     the key if it is missing, never embed keys in code or output;
   - download to `<file>.part` then rename; refuse HTML where a file/JSON is expected (Cloudflare/Akamai challenge
     pages start with `<!DOCTYPE html` or `<html`); delete the partial file on failure;
   - sha256, bytes, HTTP status, `Last-Modified`, timestamp -> `raw/manifest.json` (one entry per file, grouped by
     source with its `tracker_ids`), merged with the existing manifest;
   - idempotent: skip files already on disk unless `--refresh`; `--only <source>` to run one source;
   - revised sources (STEO, forecasts, shock series, PortWatch): keep a dated copy under
     `raw/<source>/vintages/<name>_<YYYY-MM-DD>.<ext>` in addition to the current file;
   - rate limits: sleep between calls, stop cleanly on quota errors and resume on the next run (see Comtrade in
     the fundamentals script);
   - FRED: use the JSON API with `FRED_API_KEY`, save one `raw/fred/<SERIES>.json` per series plus
     `raw/fred/<SERIES>_meta.json`.
5. **Blocked / manual sources** (registration wall, PDF, HTML-only, paid): do not fake a download. Write
   `raw/<source>/README.md` with the exact manual steps and the expected file name; have the script detect a
   hand-placed file and record it in the manifest with `"status": "manual"`. Report the row as
   `Blocked / unavailable` or `Access requested` in `tracker_status.csv` (via the clean script).
6. **Run it** with the project venv: `.venv/Scripts/python.exe data/<category>/download_<category>.py --only <source>`.
   Check each file: non-empty, opens as its declared format, first/last dates agree with `Frequency` and
   `Coverage from` in the tracker. Fix and re-run before reporting.
7. **Document**: add/refresh the source row in `data/<category>/README.md` (IDs, source, raw path, notes/limits).
   Never edit `data/Oil_Dedollarisation_Data_Tracker.xlsx`.
8. **Hand over**: tell the user what landed (files, sizes, date range), what was skipped and why, then clean it
   with the `data-store` skill (or say that is the next step).

## Report format

- per source: tracker IDs, raw path, number of files, bytes, date range covered, vintage date;
- anything blocked, with the manual step;
- the exact command to re-run.
