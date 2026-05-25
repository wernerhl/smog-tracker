"""Incremental TROPOMI NO₂ extract — last 14 days, all ROIs.

Runs weekly via GitHub Actions. Uses getInfo() (synchronous) since the
payload is tiny (14 days × 11 ROIs × a few orbits each ≈ a few hundred
features). Appends/upserts into data/raw/tropomi_daily_<YEAR>.csv.

The TROPOMI publication lag is ~2 days, so we extract dates ending
yesterday-1 and back-fill 14 days to catch reprocessed obs.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import init_ee, load_config, repo_root, roi_buffer

WINDOW_DAYS = 14
LAG_DAYS = 2


def main() -> None:
    cfg = load_config()
    init_ee()
    import ee

    end_day = date.today() - timedelta(days=LAG_DAYS)
    start_day = end_day - timedelta(days=WINDOW_DAYS)
    # EE filterDate is end-exclusive — extend by one day.
    end_str = (end_day + timedelta(days=1)).isoformat()
    start_str = start_day.isoformat()
    print(f"[extract] window {start_str} .. {end_str} (exclusive)")

    ic = (
        ee.ImageCollection(cfg["tropomi_collection"])
        .filterDate(start_str, end_str)
        .select(cfg["tropomi_band"])
    )

    rows = []
    for roi in cfg["rois"]:
        buf = roi_buffer(roi)
        sub = ic.filterBounds(buf)

        def _per_image(img):
            d = ee.Date(img.get("system:time_start"))
            r = img.reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
                geometry=buf,
                scale=1113,
                maxPixels=1e8,
            )
            return ee.Feature(None, {
                "date": d.format("YYYY-MM-dd"),
                "no2_mol_m2": r.get(f"{cfg['tropomi_band']}_mean"),
                "n_valid_pixels": r.get(f"{cfg['tropomi_band']}_count"),
            })

        feats = sub.map(_per_image).getInfo()
        for f in feats["features"]:
            p = f["properties"]
            rows.append({
                "date": p["date"],
                "roi": roi["id"],
                "name": roi["name"],
                "dept": roi["dept"],
                "altitude": roi["altitude"],
                "no2_mol_m2": p.get("no2_mol_m2"),
                "n_valid_pixels": p.get("n_valid_pixels"),
            })
        print(f"  {roi['id']:18s} {len(feats['features']):3d} image-days")

    if not rows:
        print("[extract] no rows fetched")
        return

    new = pd.DataFrame(rows)
    new["year"] = pd.to_datetime(new["date"]).dt.year.astype(int)

    raw_dir = repo_root() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for y, sub in new.groupby("year"):
        out = raw_dir / f"tropomi_daily_{y}.csv"
        if out.exists():
            old = pd.read_csv(out)
            merged = pd.concat([old, sub.drop(columns=["year"])], ignore_index=True)
            merged = merged.drop_duplicates(subset=["date", "roi"], keep="last")
            merged = merged.sort_values(["date", "roi"])
        else:
            merged = sub.drop(columns=["year"]).sort_values(["date", "roi"])
        merged.to_csv(out, index=False)
        print(f"[extract] wrote {out.name} ({len(merged):,} rows)")


if __name__ == "__main__":
    main()
