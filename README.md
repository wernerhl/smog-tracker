# 🏭 Smog Tracker — Bolivia Economic Activity Monitor

Weekly tropospheric NO₂ over 11 Bolivian metropolitan areas, updated
automatically every Sunday from ESA Sentinel-5P TROPOMI. Operational
companion to:

> Hernani-Limarino, W. & Eid, A. (2026). *Smog, Not Lights. Tracking
> Bolivia's 2024–2026 Recession from Space.* SSRN.

## Dashboard

**[wernerhl.github.io/smog-tracker](https://wernerhl.github.io/smog-tracker)**

- 🟢 NO₂ > +5 % YoY (activity expanding)
- 🟡 within ±5 % (stable)
- 🔴 NO₂ < −5 % YoY (contracting)

## What this measures

Tropospheric NO₂ from satellite is a near-direct proxy for fossil-fuel
combustion. When transport halts, factories close, or fuel becomes
unavailable, NO₂ drops within days. Weekly YoY anomalies isolate
changes in metropolitan activity from the seasonal cycle.

## Data

| | |
|---|---|
| Source | Copernicus Sentinel-5P TROPOMI OFFL L3 NO₂ (`COPERNICUS/S5P/OFFL/L3_NO2`) |
| Coverage | 11 Bolivian metropolitan areas — see `config.json` |
| Frequency | Weekly, 7-day rolling mean (≥ 3 valid days required) |
| Lag | ~2 days (TROPOMI publication delay) |
| Update | Every Sunday 06:00 UTC via GitHub Actions |
| Earliest | 2018-07-01 (TROPOMI L3 NO₂ start) |

## Repository layout

```
smog-tracker/
├── config.json                       11 ROIs + thresholds + collection IDs
├── extraction/
│   ├── extract_tropomi.py            incremental last-14-days pull
│   ├── backfill.py                   one-shot 2018-07 → today
│   ├── compute_indicators.py         weekly means, YoY anomalies, national agg
│   ├── generate_dashboard_json.py    docs/data/dashboard.json
│   └── requirements.txt
├── data/
│   ├── raw/tropomi_daily_YYYY.csv    daily by ROI, one file per year
│   ├── weekly/weekly_no2.csv         7-day rolling means
│   ├── anomalies/yoy_anomalies.csv   YoY anomalies + status
│   └── national/national_aggregate.csv  pop-weighted national
├── docs/                             GitHub Pages
│   ├── index.html                    main dashboard
│   ├── style.css
│   ├── app.js
│   ├── data/dashboard.json           dashboard payload
│   └── metros/<id>.html              per-metro detail
└── .github/workflows/weekly_update.yml
```

## Methodology (summary)

1. **Daily NO₂ per ROI** — spatial mean of `tropospheric_NO2_column_number_density`
   over a circular buffer around each city centroid. The L3 OFFL product is
   already quality-filtered upstream; weeks with fewer than 3 valid days
   are flagged as "insufficient data."

2. **Weekly aggregation** — 7-day rolling mean ending each Sunday.

3. **YoY anomaly** — `log(NO₂_t) − log(NO₂_{t-52w})` (×100 for %).

4. **National aggregate** — population-weighted mean across all 11 ROIs.

5. **Traffic-light status** — green > +5 %, yellow within ±5 %, red < −5 %.

6. **12-month trailing** — the paper's smoothed indicator that's robust to
   short-term volatility.

## Local setup

```bash
git clone https://github.com/wernerhl/smog-tracker.git
cd smog-tracker
python -m venv .venv && source .venv/bin/activate
pip install -r extraction/requirements.txt

# Authenticate Earth Engine (service-account JSON for production)
export GEE_SERVICE_ACCOUNT_EMAIL="…@…iam.gserviceaccount.com"
export GEE_SERVICE_ACCOUNT_KEY="$(cat /path/to/key.json)"

# One-time backfill
python extraction/backfill.py

# Incremental (what GH Actions runs weekly)
python extraction/extract_tropomi.py
python extraction/compute_indicators.py
python extraction/generate_dashboard_json.py
```

## GitHub Secrets (production)

| Secret | Value |
|---|---|
| `GEE_SERVICE_ACCOUNT_EMAIL` | `…@…iam.gserviceaccount.com` |
| `GEE_SERVICE_ACCOUNT_KEY` | Full contents of the service-account JSON file |
| `GCP_PROJECT_ID` | The GCP project the service account belongs to |

## Limitations

- TROPOMI overpass ~13:30 local → measures daytime activity (commute peak).
- Wet season (Nov–Mar) in the highlands frequently has < 3 valid days/week
  due to cloud cover; those weeks show "insufficient data."
- The 12-month trailing mean is the headline indicator. Single-week
  readings have high noise.
- **We do not back out PIB-implied values.** The dashboard shows combustion
  activity proxy only — applying the paper's annual β=0.53 to weekly
  readings would be misleading.

## License

Data CC-BY 4.0 · Code MIT.

## Citation

> Hernani-Limarino, W. & Eid, A. (2026). *Smog, Not Lights. Tracking
> Bolivia's 2024–2026 Recession from Space.* SSRN.
