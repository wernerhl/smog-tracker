"""Generate docs/data/dashboard.json + per-metro HTML pages.

Emits both yoy_28d (headline, 28-day rolling) and yoy_7d (raw weekly, for
the thin gray context line). Status is computed off the 28-day series.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_config, repo_root

WEEKS_CHART = 104
WEEKS_SPARK = 52
WEEKS_TABLE = 12


def _f(x):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return None
    if isinstance(x, (np.floating,)):
        return float(round(float(x), 6))
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def main() -> None:
    cfg = load_config()
    root = repo_root()

    nat = pd.read_csv(root / "data" / "national" / "national_aggregate.csv",
                      parse_dates=["week_ending"]).sort_values("week_ending")
    anom = pd.read_csv(root / "data" / "anomalies" / "yoy_anomalies.csv",
                       parse_dates=["week_ending"]).sort_values(["roi", "week_ending"])
    weekly = pd.read_csv(root / "data" / "weekly" / "weekly_no2.csv",
                         parse_dates=["week_ending"]).sort_values(["roi", "week_ending"])

    last_week = nat["week_ending"].max()
    nat_recent = nat[nat["week_ending"] >= (last_week - pd.Timedelta(weeks=WEEKS_CHART))]
    nat_last_28 = (nat.dropna(subset=["yoy_28d"]).iloc[-1]
                   if nat["yoy_28d"].notna().any() else None)

    payload: dict = {
        "last_updated": date.today().isoformat(),
        "last_week": last_week.date().isoformat() if pd.notna(last_week) else None,
        "gasolinazo_date": cfg.get("gasolinazo_date"),
        "national": {
            "current_yoy_28d": _f(nat_last_28["yoy_28d"]) if nat_last_28 is not None else None,
            "current_yoy_7d":  _f(nat_last_28["yoy_7d"])  if nat_last_28 is not None else None,
            "trailing_12m_yoy": _f(nat_last_28["trailing_12m_yoy"]) if nat_last_28 is not None else None,
            "status": nat_last_28["status"] if nat_last_28 is not None else None,
            "series": [
                {"week": r["week_ending"].date().isoformat(),
                 "yoy_28d": _f(r["yoy_28d"]),
                 "yoy_7d":  _f(r["yoy_7d"])}
                for _, r in nat_recent.iterrows()
            ],
        },
        "metros": {},
    }

    for roi in cfg["rois"]:
        rid = roi["id"]
        a = anom[anom["roi"] == rid].sort_values("week_ending")
        w = weekly[weekly["roi"] == rid].sort_values("week_ending")

        a_recent = a[a["week_ending"] >= (last_week - pd.Timedelta(weeks=WEEKS_CHART))]
        spark = a[a["week_ending"] >= (last_week - pd.Timedelta(weeks=WEEKS_SPARK))]
        recent_table_rows = w.merge(
            a[["week_ending", "yoy_28d", "yoy_7d", "status"]],
            on="week_ending", how="left",
        ).sort_values("week_ending").tail(WEEKS_TABLE)

        a_last = (a.dropna(subset=["yoy_28d"]).iloc[-1]
                  if a["yoy_28d"].notna().any() else None)

        payload["metros"][rid] = {
            "name": roi["name"],
            "dept": roi["dept"],
            "altitude": roi["altitude"],
            "current_yoy_28d": _f(a_last["yoy_28d"]) if a_last is not None else None,
            "current_yoy_7d":  _f(a_last["yoy_7d"])  if a_last is not None else None,
            "status": a_last["status"] if a_last is not None else None,
            "sparkline": [_f(v) for v in spark["yoy_28d"].tolist()],
            "series": [
                {"week": r["week_ending"].date().isoformat(),
                 "yoy_28d": _f(r["yoy_28d"]),
                 "yoy_7d":  _f(r["yoy_7d"])}
                for _, r in a_recent.iterrows()
            ],
            "level_series": [
                {"week": r["week_ending"].date().isoformat(),
                 "no2_28d": _f(r["no2_28d"]),
                 "no2_7d":  _f(r["no2_7d"])}
                for _, r in w.tail(WEEKS_CHART).iterrows()
            ],
            "recent_weeks": [
                {
                    "week": r["week_ending"].date().isoformat(),
                    "no2_28d": _f(r["no2_28d"]),
                    "yoy_28d": _f(r["yoy_28d"]),
                    "yoy_7d":  _f(r["yoy_7d"]),
                    "status": r["status"] if isinstance(r.get("status"), str) else None,
                }
                for _, r in recent_table_rows.iterrows()
            ],
        }

    out = root / "docs" / "data" / "dashboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[dashboard-json] wrote {out} ({out.stat().st_size/1024:.1f} KB)")

    # ---------- per-metro HTML pages ----------
    metros_dir = root / "docs" / "metros"
    metros_dir.mkdir(parents=True, exist_ok=True)
    for roi in cfg["rois"]:
        html = METRO_TEMPLATE.replace("__ROI_ID__", roi["id"]).replace("__ROI_NAME__", roi["name"])
        (metros_dir / f"{roi['id']}.html").write_text(html)
    print(f"[dashboard-json] wrote {len(cfg['rois'])} per-metro HTML pages")


METRO_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__ROI_NAME__ — Smog Tracker</title>
<link rel="stylesheet" href="../style.css" />
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head>
<body>
<header>
  <div class="bar">
    <h1>SMOG TRACKER <span class="sub">· <a href="../index.html" class="back-link">← all metros</a></span></h1>
    <nav>
      <span id="last-updated"></span>
      <a href="#" id="csv-dl">Download CSV</a>
      <a href="#" id="theme-toggle">☾</a>
    </nav>
  </div>
</header>

<main>
  <section class="panel">
    <div class="panel-head">
      <h2 id="metro-name">__ROI_NAME__</h2>
      <div class="kpis">
        <span class="kpi"><span class="kpi-label">Department</span> <span class="kpi-val" id="metro-meta">—</span></span>
        <span class="kpi"><span class="kpi-label">28-day YoY</span> <span class="kpi-val" id="current-yoy">—</span> <span class="dot" id="current-dot"></span></span>
        <span class="kpi"><span class="kpi-label">7-day YoY</span> <span class="kpi-val" id="current-yoy-7d" style="color:var(--muted)">—</span></span>
      </div>
    </div>
  </section>

  <section class="detail-grid">
    <div class="panel">
      <h2>Weekly NO₂ level</h2>
      <div class="chart-wrap"><canvas id="lvl-chart"></canvas></div>
      <p class="caption">28-day rolling mean (mol/m²). Thin gray = 7-day raw, for context.</p>
    </div>
    <div class="panel">
      <h2>Year-on-year anomaly</h2>
      <div class="chart-wrap"><canvas id="yoy-chart"></canvas></div>
      <p class="caption">log(NO₂_t) − log(NO₂_{t-365d}). Teal = 28-day rolling (headline), thin gray = 7-day raw. Dashed line = gasolinazo (2025-12-17).</p>
    </div>
  </section>

  <section class="panel">
    <h2>Last 12 weeks</h2>
    <table class="recent">
      <thead><tr><th>Week ending</th><th>NO₂ 28-day (mol/m²)</th><th>YoY 28-day</th><th>YoY 7-day</th><th>Status</th></tr></thead>
      <tbody id="recent-tbody"></tbody>
    </table>
  </section>
</main>

<script>window.ROI_ID = "__ROI_ID__";</script>
<script src="../metro.js"></script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
