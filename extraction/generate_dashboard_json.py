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
last_c12 = natl_m.log_dev_2019.dropna()
last_trail = natl_m.trailing_yoy.dropna()
last_wk = natl_w.yoy_28d.dropna()

monthly_series = []
for date, row in natl_m.tail(48).iterrows():
    monthly_series.append({
        "month": date.strftime("%Y-%m"),
        "log_dev_2019": safe(row.log_dev_2019),
        "trailing_yoy": safe(row.trailing_yoy),
    })

weekly_series = []
for date, row in natl_w.tail(104).iterrows():
    weekly_series.append({
        "week": date.strftime("%Y-%m-%d"),
        "yoy_28d": safe(row.yoy_28d),
    })

national = {
    "centered_12m": safe(last_c12.iloc[-1]),
    "centered_12m_date": last_c12.index[-1].strftime("%Y-%m"),
    "trailing_yoy": safe(last_trail.iloc[-1]),
    "weekly_yoy_28d": safe(last_wk.iloc[-1]),
    "weekly_date": last_wk.index[-1].strftime("%Y-%m-%d"),
    "status": status(float(last_trail.iloc[-1])),
    "monthly_series": monthly_series,
    "weekly_series": weekly_series,
}

# ── Per metro ───────────────────────────────────────────────────────
metros = {}
for roi_id, meta in ROI_META.items():
    mc = metro_c12[metro_c12.roi == roi_id].set_index("date").sort_index()
    mw = metro_wk[metro_wk.roi == roi_id].set_index("date").sort_index()

    valid_c12 = mc.log_dev_2019.dropna()
    valid_tyoy = mc.trailing_yoy.dropna()

    m_series = []
    for date, row in mc.tail(48).iterrows():
        m_series.append({
            "month": date.strftime("%Y-%m"),
            "log_dev_2019": safe(row.log_dev_2019),
            "no2": float(row.no2_monthly) if not np.isnan(row.no2_monthly) else None,
        })

    sparkline = []
    for date, row in mw.tail(52).iterrows():
        sparkline.append(safe(row.yoy_28d))

    metros[roi_id] = {
        "name": meta["name"],
        "dept": meta["dept"],
        "altitude": meta["altitude"],
        "centered_12m": safe(valid_c12.iloc[-1]) if len(valid_c12) > 0 else None,
        "centered_12m_date": valid_c12.index[-1].strftime("%Y-%m") if len(valid_c12) > 0 else None,
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
    "note": "centered_12m = log(12-month centered rolling NO2 / 2019 mean) x 100. "
            "This is the paper's headline indicator (Figure 2). "
            "trailing_yoy = trailing 12-month YoY growth in log points. "
            "weekly_yoy_28d = 28-day rolling YoY for early warning.",
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
        <span class="kpi"><span class="kpi-label" data-i18n="kpi-c12">Centered 12m</span> <span class="kpi-val" id="current-c12">—</span> <span class="dot" id="current-dot"></span></span>
        <span class="kpi"><span class="kpi-label" data-i18n="kpi-asof">As of</span> <span class="kpi-val" id="c12-date">—</span></span>
        <span class="kpi"><span class="kpi-label" data-i18n="kpi-trail">Trailing 12m YoY</span> <span class="kpi-val" id="current-trail" style="color:var(--muted)">—</span></span>
      </div>
    </div>
  </section>

  <section class="detail-grid">
    <div class="panel">
      <h2 data-i18n="metro-chart-c12">Paper's indicator: centered 12-month</h2>
      <div class="chart-wrap"><canvas id="chart-monthly"></canvas></div>
      <p class="caption" data-i18n="caption-metro-c12">log(centered 12m NO₂ / 2019 mean) × 100. Zero = 2019 baseline.</p>
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
