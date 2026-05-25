#!/usr/bin/env python3
"""
Generate docs/data/dashboard.json from computed indicators.
Two layers: monthly headline (the paper's indicator) + weekly supplement.
"""
import json, os
import pandas as pd
import numpy as np

with open("config.json") as f:
    cfg = json.load(f)
ROI_META = {r["id"]: r for r in cfg["rois"]}

os.makedirs("docs/data", exist_ok=True)

# Load
natl_m = pd.read_csv("data/national/national_monthly.csv", index_col=0, parse_dates=True)
natl_w = pd.read_csv("data/national/national_weekly.csv", index_col=0, parse_dates=True)
metro_c12 = pd.read_csv("data/monthly/centered_12m.csv", parse_dates=["date"])
metro_wk = pd.read_csv("data/weekly/weekly_28d.csv", parse_dates=["date"])

def status(val):
    if pd.isna(val): return "nodata"
    if val > 5: return "green"
    if val < -5: return "red"
    return "yellow"

def safe(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), 1)

# ── National ────────────────────────────────────────────────────────
last_c12_yoy = natl_m.centered_yoy.dropna()
last_trail = natl_m.trailing_yoy.dropna()

monthly_series = []
for date, row in natl_m.tail(48).iterrows():
    monthly_series.append({
        "month": date.strftime("%Y-%m"),
        "centered_yoy": safe(row.centered_yoy),
        "trailing_yoy": safe(row.trailing_yoy),
    })

national = {
    "centered_yoy": safe(last_c12_yoy.iloc[-1]),
    "centered_yoy_date": last_c12_yoy.index[-1].strftime("%Y-%m"),
    "trailing_yoy": safe(last_trail.iloc[-1]),
    "trailing_yoy_date": last_trail.index[-1].strftime("%Y-%m"),
    "status": status(float(last_trail.iloc[-1])),
    "monthly_series": monthly_series,
}

# ── Per metro ───────────────────────────────────────────────────────
metros = {}
for roi_id, meta in ROI_META.items():
    mc = metro_c12[metro_c12.roi == roi_id].set_index("date").sort_index()
    mw = metro_wk[metro_wk.roi == roi_id].set_index("date").sort_index()

    valid_c12_yoy = mc.centered_yoy.dropna() if "centered_yoy" in mc.columns else pd.Series(dtype=float)
    valid_tyoy = mc.trailing_yoy.dropna()

    m_series = []
    for date, row in mc.tail(48).iterrows():
        m_series.append({
            "month": date.strftime("%Y-%m"),
            "centered_yoy": safe(row.centered_yoy) if "centered_yoy" in mc.columns else None,
            "trailing_yoy": safe(row.trailing_yoy),
            "no2": float(row.no2_monthly) if not np.isnan(row.no2_monthly) else None,
        })

    sparkline = []
    for date, row in mw.tail(52).iterrows():
        sparkline.append(safe(row.yoy_28d))

    metros[roi_id] = {
        "name": meta["name"],
        "dept": meta["dept"],
        "altitude": meta["altitude"],
        "centered_yoy": safe(valid_c12_yoy.iloc[-1]) if len(valid_c12_yoy) > 0 else None,
        "centered_yoy_date": valid_c12_yoy.index[-1].strftime("%Y-%m") if len(valid_c12_yoy) > 0 else None,
        "trailing_yoy": safe(valid_tyoy.iloc[-1]) if len(valid_tyoy) > 0 else None,
        "status": status(float(valid_tyoy.iloc[-1])) if len(valid_tyoy) > 0 else "nodata",
        "sparkline_28d": sparkline,
        "monthly_series": m_series,
    }

# ── Write ───────────────────────────────────────────────────────────
out = {
    "last_updated": pd.Timestamp.now().strftime("%Y-%m-%d"),
    "gasolinazo_date": "2025-12-17",
    "reference_year": 2019,
    "note": "centered_yoy = YoY growth of 12-month centered rolling NO2 (log points %). "
            "trailing_yoy = trailing 12-month YoY growth (log points %). "
            "Both are approximate percentage changes in NO2 activity vs same period last year.",
    "national": national,
    "metros": metros,
}

with open("docs/data/dashboard.json", "w") as f:
    json.dump(out, f, indent=2)
print(f"Wrote docs/data/dashboard.json ({len(metros)} metros)")

# ── Per-metro HTML pages ───────────────────────────────────────────
METRO_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__ROI_NAME__ — Smog Tracker</title>
<link rel="stylesheet" href="../style.css" />
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="../i18n.js"></script>
</head>
<body>
<header>
  <div class="bar">
    <h1>SMOG TRACKER <span class="sub">· <a href="../index.html" class="back-link" data-i18n="back-link">← all metros</a></span></h1>
    <nav>
      <span id="last-updated"></span>
      <a href="#" id="csv-dl" data-i18n="download-csv">Download CSV</a>
      <a href="#" id="lang-toggle" class="lang-btn">ES</a>
      <a href="#" id="theme-toggle">☾</a>
    </nav>
  </div>
</header>

<main>
  <section class="panel">
    <div class="panel-head">
      <h2 id="metro-name">__ROI_NAME__</h2>
      <div class="kpis">
        <span class="kpi"><span class="kpi-label" data-i18n="kpi-dept">Department</span> <span class="kpi-val" id="metro-meta">—</span></span>
        <span class="kpi"><span class="kpi-label" data-i18n="kpi-c12-yoy">Centered 12m YoY</span> <span class="kpi-val" id="current-c12">—</span> <span class="dot" id="current-dot"></span></span>
        <span class="kpi"><span class="kpi-label" data-i18n="kpi-asof">As of</span> <span class="kpi-val" id="c12-date">—</span></span>
        <span class="kpi"><span class="kpi-label" data-i18n="kpi-trail">Trailing 12m YoY</span> <span class="kpi-val" id="current-trail" style="color:var(--muted)">—</span></span>
      </div>
    </div>
  </section>

  <section class="detail-grid">
    <div class="panel">
      <h2 data-i18n="metro-chart-c12">Year-over-year growth</h2>
      <div class="chart-wrap"><canvas id="chart-monthly"></canvas></div>
      <p class="caption" data-i18n="caption-metro-c12">YoY growth of centered and trailing 12-month NO₂ (%). Zero = no change vs prior year.</p>
    </div>
    <div class="panel">
      <h2 data-i18n="metro-chart-lvl">Monthly NO₂ level</h2>
      <div class="chart-wrap"><canvas id="lvl-chart"></canvas></div>
      <p class="caption" data-i18n="caption-metro-lvl">Monthly mean NO₂ (mol/m²).</p>
    </div>
  </section>
</main>

<script>window.ROI_ID = "__ROI_ID__";</script>
<script src="../metro.js"></script>
</body>
</html>
"""

metros_dir = os.path.join("docs", "metros")
os.makedirs(metros_dir, exist_ok=True)
for roi in cfg["rois"]:
    html = METRO_TEMPLATE.replace("__ROI_ID__", roi["id"]).replace("__ROI_NAME__", roi["name"])
    with open(os.path.join(metros_dir, f"{roi['id']}.html"), "w") as f:
        f.write(html)
print(f"Wrote {len(cfg['rois'])} per-metro HTML pages")
