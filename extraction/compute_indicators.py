"""Compute weekly NO₂ indicators + 28-day rolling YoY anomalies.

Two rolling windows:
  * 7-day  rolling mean → weekly raw signal (noisy, kept for transparency)
  * 28-day rolling mean → headline YoY (≥14 valid days required; cloud-robust)

YoY = log(rolling_t) − log(rolling_{t−365d}).

Outputs:
  data/weekly/weekly_no2.csv          muni × week, 7d + 28d means + valid-day counts
  data/anomalies/yoy_anomalies.csv    muni × week, yoy_7d + yoy_28d + status
  data/national/national_aggregate.csv national pop-weighted, 7d + 28d + trailing_12m
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_config, repo_root

ROLL_SMOOTH = 28      # days — headline smoothing window
ROLL_NOISY = 7        # days — raw weekly for context line
MIN_VALID_28D = 14    # ≥ this many valid days within the 28-day window
MIN_VALID_7D = 3      # ≥ this many valid days within the 7-day window
YOY_DAYS = 365        # YoY = today vs ~52 weeks prior


def _status(yoy_pct: float | None) -> str | None:
    if yoy_pct is None or pd.isna(yoy_pct):
        return None
    if yoy_pct > 5:
        return "green"
    if yoy_pct < -5:
        return "red"
    return "yellow"


def main() -> None:
    cfg = load_config()
    raw_dir = repo_root() / "data" / "raw"
    files = sorted(raw_dir.glob("tropomi_daily_*.csv"))
    if not files:
        print(f"[indicators] no raw files in {raw_dir} — run backfill.py first")
        return
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["roi", "date"])
    print(f"[indicators] read {len(df):,} rows from {len(files)} files, "
          f"date range {df['date'].min().date()}..{df['date'].max().date()}")

    # ---------- daily collapse (multiple TROPOMI orbits per day) ----------
    daily = (
        df.groupby(["roi", "name", "dept", "altitude", "date"], as_index=False)
        .agg(no2_mol_m2=("no2_mol_m2", "mean"),
             n_valid_pixels=("n_valid_pixels", "sum"))
    )

    # ---------- per-ROI: rolling 7d + 28d, then YoY, then weekly resample ----------
    weekly_chunks, anom_chunks = [], []
    for roi, g in daily.groupby("roi"):
        g = g.set_index("date").sort_index()
        idx = pd.date_range(g.index.min(), g.index.max(), freq="D")
        g = g.reindex(idx)

        valid = g["no2_mol_m2"].notna().astype(int)
        roll7  = g["no2_mol_m2"].rolling(f"{ROLL_NOISY}D",  min_periods=MIN_VALID_7D).mean()
        roll28 = g["no2_mol_m2"].rolling(f"{ROLL_SMOOTH}D", min_periods=MIN_VALID_28D).mean()
        valid7  = valid.rolling(f"{ROLL_NOISY}D").sum()
        valid28 = valid.rolling(f"{ROLL_SMOOTH}D").sum()

        # Mask out windows below the min-valid threshold.
        roll7  = roll7.where(valid7  >= MIN_VALID_7D)
        roll28 = roll28.where(valid28 >= MIN_VALID_28D)

        log7  = np.log(roll7)
        log28 = np.log(roll28)
        # YoY: shift by 365 calendar days, daily-aligned (so D/D-365 comparison is exact).
        yoy7_daily  = (log7  - log7.shift(YOY_DAYS))  * 100
        yoy28_daily = (log28 - log28.shift(YOY_DAYS)) * 100

        # Sample to weekly (Sunday-ending) — the last available daily value per Sunday.
        sundays = pd.date_range(g.index.min(), g.index.max(), freq="W-SUN")

        name = g["name"].dropna().iloc[0] if g["name"].notna().any() else roi
        dept = g["dept"].dropna().iloc[0] if g["dept"].notna().any() else None
        altitude = g["altitude"].dropna().iloc[0] if g["altitude"].notna().any() else None

        weekly_chunks.append(pd.DataFrame({
            "week_ending": sundays,
            "roi": roi, "name": name, "dept": dept, "altitude": altitude,
            "no2_7d":  roll7.reindex(sundays).values,
            "no2_28d": roll28.reindex(sundays).values,
            "n_valid_days_7d":  valid7.reindex(sundays).values,
            "n_valid_days_28d": valid28.reindex(sundays).values,
        }))
        anom_chunks.append(pd.DataFrame({
            "week_ending": sundays,
            "roi": roi,
            "yoy_7d":  yoy7_daily.reindex(sundays).values,
            "yoy_28d": yoy28_daily.reindex(sundays).values,
        }))

    weekly = pd.concat(weekly_chunks, ignore_index=True)
    anom = pd.concat(anom_chunks, ignore_index=True)
    anom["status"] = anom["yoy_28d"].apply(_status)
    # Backwards-compat aliases for any legacy reader.
    weekly["no2_weekly_mean"] = weekly["no2_7d"]
    weekly["log_no2"] = np.log(weekly["no2_7d"])
    anom["yoy_anomaly_pct"] = anom["yoy_28d"]

    weekly_out = repo_root() / "data" / "weekly" / "weekly_no2.csv"
    weekly_out.parent.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(weekly_out, index=False, date_format="%Y-%m-%d")
    print(f"[indicators] wrote {weekly_out.name} ({len(weekly):,} rows)")

    anom_out = repo_root() / "data" / "anomalies" / "yoy_anomalies.csv"
    anom_out.parent.mkdir(parents=True, exist_ok=True)
    anom.to_csv(anom_out, index=False, date_format="%Y-%m-%d")
    print(f"[indicators] wrote {anom_out.name} ({len(anom):,} rows)")

    # ---------- national pop-weighted aggregate (on the 28-day smoothed series) ----------
    pop = {r["id"]: r["pop"] for r in cfg["rois"]}
    weekly["pop"] = weekly["roi"].map(pop)
    nat_rows = []
    for col_no2 in ("no2_28d", "no2_7d"):
        sub = weekly.dropna(subset=[col_no2]).copy()
        sub["wval"] = sub[col_no2] * sub["pop"]
        g = sub.groupby("week_ending", as_index=False).agg(
            wsum=("wval", "sum"), w=("pop", "sum"),
        )
        g["no2"] = g["wsum"] / g["w"]
        g["window"] = col_no2.split("_")[1]
        nat_rows.append(g[["week_ending", "window", "no2"]])
    nat_long = pd.concat(nat_rows, ignore_index=True)
    nat = nat_long.pivot_table(index="week_ending", columns="window", values="no2").reset_index()
    nat.columns.name = None
    nat = nat.rename(columns={"28d": "no2_national_28d", "7d": "no2_national_7d"})
    nat = nat.sort_values("week_ending").reset_index(drop=True)

    # YoY at the national level — log diff with the 52-week-prior week.
    for src, dst in (("no2_national_28d", "yoy_28d"),
                     ("no2_national_7d", "yoy_7d")):
        if src in nat.columns:
            nat[f"log_{src}"] = np.log(nat[src])
            nat[dst] = (nat[f"log_{src}"] - nat[f"log_{src}"].shift(52)) * 100

    nat["status"] = nat["yoy_28d"].apply(_status)
    # 12-month trailing on the 28-day smoothed log series.
    nat["trailing_12m_log"] = nat["log_no2_national_28d"].rolling(52, min_periods=26).mean()
    nat["trailing_12m_yoy"] = (
        nat["trailing_12m_log"] - nat["trailing_12m_log"].shift(52)
    ) * 100

    nat_out = repo_root() / "data" / "national" / "national_aggregate.csv"
    nat_out.parent.mkdir(parents=True, exist_ok=True)
    nat[["week_ending", "no2_national_28d", "no2_national_7d",
         "yoy_28d", "yoy_7d", "status",
         "trailing_12m_log", "trailing_12m_yoy"]].to_csv(
        nat_out, index=False, date_format="%Y-%m-%d")
    print(f"[indicators] wrote {nat_out.name} ({len(nat):,} rows)")

    last = nat.dropna(subset=["yoy_28d"]).iloc[-1] if nat["yoy_28d"].notna().any() else None
    if last is not None:
        print(f"[indicators] latest national YoY (28d): {last['yoy_28d']:+.2f}%  "
              f"7d: {last['yoy_7d']:+.2f}%  status={last['status']}  "
              f"trailing-12m: {last['trailing_12m_yoy']:+.2f}%  week={last['week_ending'].date()}")


if __name__ == "__main__":
    main()
