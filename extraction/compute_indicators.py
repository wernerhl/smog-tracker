#!/usr/bin/env python3
"""
Compute the paper's recession indicator + weekly early-warning supplement.

Reads:  data/raw/tropomi_daily_*.csv
Writes: data/monthly/monthly_no2.csv          (monthly means by ROI)
        data/monthly/centered_12m.csv          (the paper's indicator)
        data/weekly/weekly_28d.csv             (28-day rolling weekly supplement)
        data/national/national_monthly.csv     (pop-weighted national monthly)
        data/national/national_weekly.csv      (pop-weighted national weekly)
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

# Ensure output dirs
for d in ["data/monthly", "data/weekly", "data/national"]:
    os.makedirs(d, exist_ok=True)

# ── Load daily data ─────────────────────────────────────────────────
frames = []
for path in sorted(glob.glob("data/raw/tropomi_daily_*.csv")):
    df = pd.read_csv(path, parse_dates=["date"])
    frames.append(df)
daily = pd.concat(frames, ignore_index=True)
daily = daily[daily.roi.isin(ROI_IDS)].copy()
daily = daily.dropna(subset=["no2_mol_m2"])
daily["month"] = daily.date.dt.to_period("M")
print(f"Loaded {len(daily)} daily obs, {daily.date.min().date()} to {daily.date.max().date()}")

# ── 1. Monthly means by ROI ────────────────────────────────────────
monthly = (
    daily.groupby(["month", "roi"])
    .agg(no2_mean=("no2_mol_m2", "mean"), n_days=("no2_mol_m2", "count"))
    .reset_index()
)
monthly = monthly[monthly.n_days >= MIN_DAYS_MONTH].copy()
monthly["date"] = monthly.month.dt.to_timestamp()
monthly.to_csv("data/monthly/monthly_no2.csv", index=False)
print(f"Monthly means: {len(monthly)} ROI-months")

# ── 2. National pop-weighted monthly ────────────────────────────────
def pop_weighted_monthly(monthly_df):
    rows = []
    for date, g in monthly_df.groupby("date"):
        avail = g[g.roi.isin(POP)]
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

# ── 3. Centered 12-month rolling = THE PAPER'S INDICATOR ───────────
#    log(centered_12m / ref_2019) × 100 = log deviation in percent
ref_2019 = natl_m.loc["2019":"2019", "no2"].mean()
print(f"Reference 2019 national NO2: {ref_2019:.6e} mol/m2")

natl_m["log_no2"] = np.log(natl_m.no2)
natl_m["centered_12m"] = natl_m.log_no2.rolling(12, center=True, min_periods=12).mean()
natl_m["log_dev_2019"] = (natl_m.centered_12m - np.log(ref_2019)) * 100

# Trailing 12-month (for growth rates, recession dating)
natl_m["trailing_12m"] = natl_m.log_no2.rolling(12, min_periods=12).mean()
natl_m["trailing_12m_dev"] = (natl_m.trailing_12m - np.log(ref_2019)) * 100

# YoY trailing growth
natl_m["trailing_yoy"] = (natl_m.trailing_12m - natl_m.trailing_12m.shift(12)) * 100

natl_m.to_csv("data/national/national_monthly.csv")
print(f"National monthly: {len(natl_m)} months")
print(f"  Last centered-12m: {natl_m.log_dev_2019.dropna().iloc[-1]:+.1f} log pts "
      f"at {natl_m.log_dev_2019.dropna().index[-1].strftime('%Y-%m')}")
print(f"  Trailing-12m peak: {natl_m.trailing_12m_dev.dropna().idxmax().strftime('%Y-%m')} "
      f"at {natl_m.trailing_12m_dev.dropna().max():+.1f}")

# ── 4. Per-metro centered 12-month ──────────────────────────────────
c12_rows = []
for roi in ROI_IDS:
    sub = monthly[monthly.roi == roi].set_index("date").sort_index()
    if len(sub) < 12:
        continue
    ref_roi = sub.loc["2019":"2019", "no2_mean"].mean()
    if np.isnan(ref_roi) or ref_roi <= 0:
        continue
    log_s = np.log(sub.no2_mean)
    c12 = log_s.rolling(12, center=True, min_periods=12).mean()
    dev = (c12 - np.log(ref_roi)) * 100
    t12 = log_s.rolling(12, min_periods=12).mean()
    t12_yoy = (t12 - t12.shift(12)) * 100
    for date in sub.index:
        c12_rows.append({
            "date": date, "roi": roi,
            "log_dev_2019": float(dev.get(date, np.nan)),
            "trailing_yoy": float(t12_yoy.get(date, np.nan)),
            "no2_monthly": float(sub.loc[date, "no2_mean"]),
        })

pd.DataFrame(c12_rows).to_csv("data/monthly/centered_12m.csv", index=False)
print(f"Per-metro centered-12m: {len(c12_rows)} ROI-months")

# ── 5. Weekly 28-day rolling supplement ─────────────────────────────
daily_nat = []
for date, g in daily.groupby("date"):
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
    sub = daily[daily.roi == roi].set_index("date").sort_index()
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
print("Done.")
