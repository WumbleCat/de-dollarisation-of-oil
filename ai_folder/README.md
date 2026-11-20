# MOSUM structural-change analysis: WTI vs DXY

This folder is self-contained. On any machine with Python 3.9 and internet access,
the steps below recreate the environment, re-download the price data from Yahoo
Finance and re-run every scenario in the notebook.

## Contents

| File | What it is |
|---|---|
| `mosum_wti_dxy.ipynb` | The notebook. Downloads WTI (`CL=F`) and DXY (`DX-Y.NYB`) daily closes, builds the scenario series and runs the MOSUM change-point procedures. Committed with executed outputs from the 2026-11-19 run. |
| `requirements.txt` | Exact package versions used for that run. |
| `wti_dxy_prices.csv` | Aligned daily closes as downloaded on 2026-11-19 (regenerated on every run). |
| `mosum_change_points.csv` | Every detected change point, all scenarios and methods (regenerated). |
| `mosum_headline_confidence_intervals.csv` | Bootstrap 95% intervals for the headline change points (regenerated). |
| `structural_break_dates.csv` | Compact list of structural-break dates from the multiscale methods, excluding the raw-level reference runs. |

## Reproduce on a fresh machine

Python **3.9 is required**. The `mosum` package (0.2.0) pins `numpy<1.24`, `pandas<2`
and `numba 0.53`, and that numba does not install on Python 3.10 or later.

```bash
git clone https://github.com/WumbleCat/de-dollarisation-of-oil.git
cd de-dollarisation-of-oil/ai_folder

# 1. Python 3.9 virtual environment (pick one)
uv venv --python 3.9 .venv            # with uv
python3.9 -m venv .venv               # or with a system Python 3.9

# 2. activate it
source .venv/bin/activate             # macOS / Linux
.venv\Scripts\activate                # Windows

# 3. install the pinned dependencies
pip install -r requirements.txt

# 4. re-download the data and re-run every cell (about 3 minutes)
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 mosum_wti_dxy.ipynb
```

Alternatively open the notebook in Jupyter Lab (`jupyter lab`) and run all cells.

Running the notebook overwrites the four CSV files with fresh results. The data
window is `START = "2000-01-01"` to the latest close (`END = None`), so a later
run extends the sample and can move or add the most recent change point.
`structural_break_dates.csv` is not written by the notebook; it is a filtered view
of `mosum_change_points.csv` (multiscale methods only, reference scenarios dropped).

Notes:

* On Windows, nbconvert prints a harmless `Proactor event loop` warning from zmq.
* The first MOSUM call compiles numba kernels and takes a few seconds; all later runs are sub-second.
* If Yahoo Finance returns no data, the download cell raises `RuntimeError`; check the
  connection or the ticker symbols in the `TICKERS` dictionary.

## What the notebook does

MOSUM (moving-sum) detects changes in the mean of a series with stationary noise, so
the two prices are first transformed into stationary objects. Each scenario is run at
three single bandwidths and with the two multiscale procedures (bottom-up merging and
localised pruning) from the `mosum` package:

| Scenario | Series | Change point means |
|---|---|---|
| A, B | WTI / DXY daily log return | shift in average drift |
| C, D | WTI / DXY absolute log return | shift in volatility regime |
| E, E2 | product of locally standardised returns | shift in WTI-DXY correlation |
| F, F2 | OLS residual of log WTI on log DXY (the spread) | shift in the long-run level relationship |
| G, H | raw log levels | reference only; shows why MOSUM must not be run on integrated prices |

Scenarios E2 and F2 use multi-year bandwidths (1, 2 and 3 years) because the
relationship between the two prices moves over years. The pooled section adds bootstrap
confidence intervals, a timeline plot, matching of shared WTI and DXY breaks, and
sensitivity tables for the significance level and the bandwidth grid. Section 7 of the
notebook interprets the 2026-11-19 results.

Key settings live in the first code cell: `START`, `END`, `TICKERS`, `ALPHA`,
`BANDWIDTHS`, `SLOW_BANDWIDTHS`, `ETA`, `VOL_WINDOW`, `CI_REPS`, `MATCH_TOL_DAYS`.
