"""Compute weekly means, YoY anomalies, national aggregate, traffic-light status.

Reads data/raw/tropomi_daily_*.csv → writes data/weekly/, data/anomalies/,
data/national/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_config, repo_root


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

    # ---------- daily collapse (multiple orbits per day) ----------
    daily = (
        df.groupby(["roi", "name", "dept", "altitude", "date"], as_index=False)
        .agg(no2_mol_m2=("no2_mol_m2", "mean"),
             n_valid_pixels=("n_valid_pixels", "sum"))
    )

    # ---------- weekly 7-day rolling mean, week-ending Sunday ----------
    weekly_rows = []
    min_days = cfg["min_valid_days_per_week"]
    for roi, g in daily.groupby("roi"):
        g = g.set_index("date").sort_index()
        idx = pd.date_range(g.index.min(), g.index.max(), freq="D")
        g = g.reindex(idx)
        # Week ending each Sunday — use 7-day window ending Sunday.
        valid = g["no2_mol_m2"].notna().astype(int)
        roll_mean = g["no2_mol_m2"].rolling("7D", min_periods=min_days).mean()
        roll_valid = valid.rolling("7D").sum()
        sundays = pd.date_range(g.index.min(), g.index.max(), freq="W-SUN")
        sub = pd.DataFrame({
            "week_ending": sundays,
            "roi": roi,
            "name": g["name"].dropna().iloc[0] if g["name"].notna().any() else roi,
            "dept": g["dept"].dropna().iloc[0] if g["dept"].notna().any() else None,
            "altitude": g["altitude"].dropna().iloc[0] if g["altitude"].notna().any() else None,
            "no2_weekly_mean": roll_mean.reindex(sundays).values,
            "n_valid_days": roll_valid.reindex(sundays).values,
        })
        sub.loc[sub["n_valid_days"] < min_days, "no2_weekly_mean"] = np.nan
        sub["log_no2"] = np.log(sub["no2_weekly_mean"])
        weekly_rows.append(sub)
    weekly = pd.concat(weekly_rows, ignore_index=True)
    weekly_out = repo_root() / "data" / "weekly" / "weekly_no2.csv"
    weekly_out.parent.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(weekly_out, index=False, date_format="%Y-%m-%d")
    print(f"[indicators] wrote {weekly_out.name} ({len(weekly):,} rows)")

    # ---------- YoY anomaly (log diff vs 52 weeks prior) ----------
    anomaly_rows = []
    for roi, g in weekly.groupby("roi"):
        g = g.sort_values("week_ending").reset_index(drop=True)
        g["log_no2_52w_ago"] = g["log_no2"].shift(52)
        g["yoy_anomaly_pct"] = (g["log_no2"] - g["log_no2_52w_ago"]) * 100
        g["status"] = g["yoy_anomaly_pct"].apply(_status)
        anomaly_rows.append(g[["week_ending", "roi", "log_no2",
                                 "log_no2_52w_ago", "yoy_anomaly_pct", "status"]])
    anomalies = pd.concat(anomaly_rows, ignore_index=True)
    anom_out = repo_root() / "data" / "anomalies" / "yoy_anomalies.csv"
    anom_out.parent.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(anom_out, index=False, date_format="%Y-%m-%d")
    print(f"[indicators] wrote {anom_out.name} ({len(anomalies):,} rows)")

    # ---------- national pop-weighted aggregate ----------
    pop = {r["id"]: r["pop"] for r in cfg["rois"]}
    weekly["pop"] = weekly["roi"].map(pop)
    weekly["wval"] = weekly["no2_weekly_mean"] * weekly["pop"]
    nat = (
        weekly.dropna(subset=["no2_weekly_mean"])
        .groupby("week_ending", as_index=False)
        .agg(wsum=("wval", "sum"), w=("pop", "sum"))
    )
    nat["no2_national"] = nat["wsum"] / nat["w"]
    nat["log_no2"] = np.log(nat["no2_national"])
    nat = nat[["week_ending", "no2_national", "log_no2"]].sort_values("week_ending").reset_index(drop=True)
    nat["log_no2_52w_ago"] = nat["log_no2"].shift(52)
    nat["yoy_anomaly_pct"] = (nat["log_no2"] - nat["log_no2_52w_ago"]) * 100
    nat["status"] = nat["yoy_anomaly_pct"].apply(_status)
    # 12-month trailing means.
    nat["trailing_12m_log"] = nat["log_no2"].rolling(52, min_periods=26).mean()
    nat["trailing_12m_yoy"] = (
        nat["trailing_12m_log"] - nat["trailing_12m_log"].shift(52)
    ) * 100
    nat_out = repo_root() / "data" / "national" / "national_aggregate.csv"
    nat_out.parent.mkdir(parents=True, exist_ok=True)
    nat[["week_ending", "no2_national", "yoy_anomaly_pct", "status",
         "trailing_12m_log", "trailing_12m_yoy"]].to_csv(nat_out, index=False, date_format="%Y-%m-%d")
    print(f"[indicators] wrote {nat_out.name} ({len(nat):,} rows)")
    if nat["yoy_anomaly_pct"].notna().any():
        last = nat.dropna(subset=["yoy_anomaly_pct"]).iloc[-1]
        print(f"[indicators] latest national YoY: {last['yoy_anomaly_pct']:+.2f}%  status={last['status']}  week={last['week_ending'].date()}")


if __name__ == "__main__":
    main()
