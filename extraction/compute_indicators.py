#!/usr/bin/env python3
"""
Compute the paper's recession indicator + weekly early-warning supplement.

CRITICAL DESIGN DECISION:
  The paper's pre-extracted monthly data (data/paper/s5p_no2_monthly.csv)
  uses rectangular ROIs and specific QA filtering that produce different
  absolute NO₂ values than the daily GEE backfill (which uses circular
  buffers). To reproduce the paper's figures exactly, we use the paper's
  monthly CSV as the authoritative source for the historical period
  (Jul 2018 through its last month). The daily backfill is used ONLY
  for months beyond the paper's coverage, aggregated to monthly means
  with the same min-valid-days threshold.

Reads:
  data/paper/s5p_no2_monthly.csv    ← THE PAPER'S ACTUAL DATA (authoritative)
  data/raw/tropomi_daily_*.csv      ← daily backfill (for new months only)

Writes:
  data/monthly/monthly_no2.csv
  data/monthly/centered_12m.csv
  data/weekly/weekly_28d.csv
  data/national/national_monthly.csv
  data/national/national_weekly.csv
"""
import json, glob, os
import pandas as pd
import numpy as np

# ── Config ──────────────────────────────────────────────────────────
with open("config.json") as f:
    cfg = json.load(f)

POP = {r["id"]: r["pop"] for r in cfg["rois"]}
ROI_IDS = list(POP.keys())
MIN_DAYS_MONTH = 15
MIN_DAYS_28D = 10
REF_YEAR = 2019

for d in ["data/monthly", "data/weekly", "data/national"]:
    os.makedirs(d, exist_ok=True)

# ── 1. Load the paper's monthly data (authoritative) ────────────────
paper_path = "data/paper/s5p_no2_monthly.csv"
paper = pd.read_csv(paper_path, parse_dates=["date"])
paper = paper[paper.roi.isin(ROI_IDS)].copy()
paper = paper.rename(columns={"no2_tropos_col_mol_m2": "no2_mean"})
paper["month"] = paper.date.dt.to_period("M")
paper_last_month = paper.date.max()
print(f"Paper monthly data: {len(paper)} obs, {paper.date.min().date()} to {paper_last_month.date()}")

# ── 2. Load daily backfill for months AFTER the paper ───────────────
frames = []
for path in sorted(glob.glob("data/raw/tropomi_daily_*.csv")):
    df = pd.read_csv(path, parse_dates=["date"])
    frames.append(df)

new_monthly = pd.DataFrame()
if frames:
    daily = pd.concat(frames, ignore_index=True)
    daily = daily[daily.roi.isin(ROI_IDS)].copy()
    daily = daily.dropna(subset=["no2_mol_m2"])
    # Only keep days AFTER the paper's last month
    daily = daily[daily.date > paper_last_month].copy()

    if len(daily) > 0:
        daily["month"] = daily.date.dt.to_period("M")
        new_monthly = (
            daily.groupby(["month", "roi"])
            .agg(no2_mean=("no2_mol_m2", "mean"), n_days=("no2_mol_m2", "count"))
            .reset_index()
        )
        new_monthly = new_monthly[new_monthly.n_days >= MIN_DAYS_MONTH].copy()
        new_monthly["date"] = new_monthly.month.dt.to_timestamp()
        print(f"New months from daily backfill: {len(new_monthly)} ROI-months "
              f"({new_monthly.date.min().date()} to {new_monthly.date.max().date()})")
    else:
        print("No daily data beyond paper's coverage yet.")
else:
    print("No daily backfill files found.")

# ── 3. Combine: paper (authoritative) + new months ──────────────────
paper_slim = paper[["date", "roi", "no2_mean", "month"]].copy()
if len(new_monthly) > 0:
    new_slim = new_monthly[["date", "roi", "no2_mean", "month"]].copy()
    monthly = pd.concat([paper_slim, new_slim], ignore_index=True)
else:
    monthly = paper_slim.copy()

monthly = monthly.sort_values(["roi", "date"]).reset_index(drop=True)
monthly.to_csv("data/monthly/monthly_no2.csv", index=False)
print(f"Combined monthly: {len(monthly)} ROI-months")

# ── 4. National pop-weighted monthly ────────────────────────────────
def pop_weighted_monthly(monthly_df):
    rows = []
    for date, g in monthly_df.groupby("date"):
        avail = g[g.roi.isin(POP)].dropna(subset=["no2_mean"])
        if len(avail) == 0:
            continue
        w = np.array([POP[r] for r in avail.roi])
        w = w / w.sum()
        rows.append({
            "date": date,
            "no2": np.sum(w * avail.no2_mean.values),
            "n_rois": len(avail),
        })
    return pd.DataFrame(rows).set_index("date").sort_index()

natl_m = pop_weighted_monthly(monthly)

# ── 5. Centered 12-month rolling = THE PAPER'S INDICATOR ───────────
ref_2019 = natl_m.loc["2019":"2019", "no2"].mean()
print(f"Reference 2019 national NO2: {ref_2019:.6e} mol/m2")

natl_m["log_no2"] = np.log(natl_m.no2)

# CRITICAL: reference must be mean(log(NO2)) not log(mean(NO2))
# Jensen's inequality: log(mean(x)) > mean(log(x)) for any variable x
# Using log(mean) shifts ALL readings by ~6.6 log points
ref_log_2019 = natl_m.loc["2019":"2019", "log_no2"].mean()
print(f"Reference log(NO2) 2019: {ref_log_2019:.6f} [mean of log, not log of mean]")

natl_m["centered_12m"] = natl_m.log_no2.rolling(12, center=True, min_periods=12).mean()
natl_m["log_dev_2019"] = (natl_m.centered_12m - ref_log_2019) * 100
natl_m["centered_yoy"] = (natl_m.centered_12m - natl_m.centered_12m.shift(12)) * 100

# Trailing 12-month
natl_m["trailing_12m"] = natl_m.log_no2.rolling(12, min_periods=12).mean()
natl_m["trailing_12m_dev"] = (natl_m.trailing_12m - ref_log_2019) * 100
natl_m["trailing_yoy"] = (natl_m.trailing_12m - natl_m.trailing_12m.shift(12)) * 100

natl_m.to_csv("data/national/national_monthly.csv")

last_c12 = natl_m.log_dev_2019.dropna()
last_trail = natl_m.trailing_12m_dev.dropna()
peak = last_c12.idxmax()
print(f"National monthly: {len(natl_m)} months")
print(f"  Centered-12m peak: {peak.strftime('%Y-%m')} at {last_c12.max():+.1f} log pts")
print(f"  Last centered-12m: {last_c12.iloc[-1]:+.1f} at {last_c12.index[-1].strftime('%Y-%m')}")
print(f"  Last trailing-12m dev: {last_trail.iloc[-1]:+.1f}")

# ── 6. Per-metro centered 12-month ──────────────────────────────────
c12_rows = []
for roi in ROI_IDS:
    sub = monthly[monthly.roi == roi].set_index("date").sort_index()
    if len(sub) < 12:
        continue
    ref_roi = sub.loc["2019":"2019", "no2_mean"].mean()
    if np.isnan(ref_roi) or ref_roi <= 0:
        continue
    log_s = np.log(sub.no2_mean)
    # CRITICAL: mean(log) not log(mean) — same Jensen fix as national
    ref_log_roi = log_s.loc["2019":"2019"].mean()
    c12 = log_s.rolling(12, center=True, min_periods=12).mean()
    dev = (c12 - ref_log_roi) * 100
    c12_yoy = (c12 - c12.shift(12)) * 100
    t12 = log_s.rolling(12, min_periods=12).mean()
    t12_yoy = (t12 - t12.shift(12)) * 100
    for i, (date, row_val) in enumerate(sub.iterrows()):
        c12_rows.append({
            "date": date, "roi": roi,
            "log_dev_2019": float(dev.iloc[i]) if not np.isnan(dev.iloc[i]) else np.nan,
            "centered_yoy": float(c12_yoy.iloc[i]) if not np.isnan(c12_yoy.iloc[i]) else np.nan,
            "trailing_yoy": float(t12_yoy.iloc[i]) if not np.isnan(t12_yoy.iloc[i]) else np.nan,
            "no2_monthly": float(row_val.no2_mean),
        })

pd.DataFrame(c12_rows).to_csv("data/monthly/centered_12m.csv", index=False)
print(f"Per-metro centered-12m: {len(c12_rows)} ROI-months")

# ── 7. Weekly 28-day rolling supplement ─────────────────────────────
# For the weekly supplement, we use the daily backfill (ALL of it,
# not just post-paper months) because we need daily granularity.
# The weekly supplement is clearly labeled as "early warning" and
# is not the headline indicator.
if frames:
    daily_all = pd.concat(frames, ignore_index=True)
    daily_all = daily_all[daily_all.roi.isin(ROI_IDS)].copy()
    daily_all = daily_all.dropna(subset=["no2_mol_m2"])

    # National daily
    daily_nat = []
    for date, g in daily_all.groupby("date"):
        avail = g[g.roi.isin(POP)]
        if len(avail) == 0:
            continue
        w = np.array([POP[r] for r in avail.roi])
        w = w / w.sum()
        daily_nat.append({"date": date, "no2": np.sum(w * avail.no2_mol_m2.values)})
    daily_nat = pd.DataFrame(daily_nat).set_index("date").sort_index()

    daily_nat["roll_28d"] = daily_nat.no2.rolling(28, min_periods=MIN_DAYS_28D).mean()
    daily_nat["log_28d"] = np.log(daily_nat.roll_28d)
    daily_nat["log_28d_lag52w"] = daily_nat.log_28d.shift(364)
    daily_nat["yoy_28d"] = (daily_nat.log_28d - daily_nat.log_28d_lag52w) * 100

    weekly = daily_nat.resample("W-SUN").last().dropna(subset=["roll_28d"])
    weekly.to_csv("data/national/national_weekly.csv")

    # Per-metro weekly
    wk_rows = []
    for roi in ROI_IDS:
        sub = daily_all[daily_all.roi == roi].set_index("date").sort_index()
        if len(sub) < 28:
            continue
        sub_no2 = sub.no2_mol_m2
        roll = sub_no2.rolling(28, min_periods=MIN_DAYS_28D).mean()
        log_roll = np.log(roll)
        yoy = (log_roll - log_roll.shift(364)) * 100
        wk = pd.DataFrame({"no2_28d": roll, "yoy_28d": yoy}).resample("W-SUN").last().dropna(subset=["no2_28d"])
        for date, row in wk.iterrows():
            wk_rows.append({"date": date, "roi": roi,
                            "no2_28d": float(row.no2_28d),
                            "yoy_28d": float(row.yoy_28d)})

    pd.DataFrame(wk_rows).to_csv("data/weekly/weekly_28d.csv", index=False)
    print(f"Weekly 28-day rolling: {len(weekly)} national weeks")
    print(f"  Last weekly YoY: {weekly.yoy_28d.iloc[-1]:+.1f}%")
else:
    print("No daily data — skipping weekly supplement.")

print("\nDone.")
