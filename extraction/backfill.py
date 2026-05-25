"""One-shot backfill: TROPOMI L3 NO₂ daily means, all ROIs, 2018-07 → today.

Submits a single Export.table.toCloudStorage to GCS, then downloads the CSV
and splits it into per-year files in data/raw/.

The L3 OFFL product is already quality-filtered upstream — we don't need a
per-pixel qa_value band (which doesn't exist on the L3 grid). The spec's
QA mask is implicit in the L3 processing.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import init_ee, load_config, repo_root, roi_buffer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=None,
                        help="ISO date; defaults to config.backfill_start")
    parser.add_argument("--end-date", default=None,
                        help="ISO date; defaults to today")
    parser.add_argument("--wait", action="store_true",
                        help="Block until the EE task completes; otherwise just submit")
    parser.add_argument("--skip-download", action="store_true",
                        help="Don't sync from GCS after the task completes")
    args = parser.parse_args()

    cfg = load_config()
    init_ee()
    import ee

    start = args.start_date or cfg["backfill_start"]
    end = args.end_date or date.today().isoformat()
    print(f"[backfill] {start} -> {end}, {len(cfg['rois'])} ROIs")

    ic = (
        ee.ImageCollection(cfg["tropomi_collection"])
        .filterDate(start, end)
        .select(cfg["tropomi_band"])
    )

    def _city_features(roi):
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
                "roi": roi["id"],
                "name": roi["name"],
                "dept": roi["dept"],
                "altitude": roi["altitude"],
                "date": d.format("YYYY-MM-dd"),
                "year": d.get("year"),
                "no2_mol_m2": r.get(f"{cfg['tropomi_band']}_mean"),
                "n_valid_pixels": r.get(f"{cfg['tropomi_band']}_count"),
            })

        return sub.map(_per_image)

    fcs = [_city_features(r) for r in cfg["rois"]]
    feats = ee.FeatureCollection(fcs).flatten()

    bucket = cfg["gee_export_bucket"]
    prefix = cfg["gee_export_prefix"]
    file_prefix = f"{prefix}/tropomi_backfill_{start}_{end}"
    selectors = ["roi", "name", "dept", "altitude", "date", "year",
                 "no2_mol_m2", "n_valid_pixels"]

    task = ee.batch.Export.table.toCloudStorage(
        collection=feats,
        description=f"smog_tropomi_backfill_{start}_{end}".replace("-", ""),
        bucket=bucket,
        fileNamePrefix=file_prefix,
        fileFormat="CSV",
        selectors=selectors,
    )
    task.start()
    print(f"[backfill] queued: task_id={task.id}  -> gs://{bucket}/{file_prefix}.csv")

    if args.wait:
        print("[backfill] waiting for EE task to complete…", flush=True)
        while True:
            s = task.status()
            st = s.get("state")
            print(f"  state={st}  updated={s.get('update_timestamp_ms')}", flush=True)
            if st in ("COMPLETED", "FAILED", "CANCELLED"):
                break
            time.sleep(60)
        if st != "COMPLETED":
            print(f"[backfill] task ended in state {st}: {s.get('error_message','')}")
            sys.exit(2)

    if args.skip_download:
        return

    # Download from GCS and split per-year. Will silently no-op if the task
    # hasn't finished yet — caller can rerun with --skip-download omitted later.
    _ingest_from_gcs(bucket, file_prefix)


def _ingest_from_gcs(bucket: str, file_prefix: str) -> None:
    from google.cloud import storage
    project = os.environ["GCP_PROJECT_ID"]
    client = storage.Client(project=project)
    blob = client.bucket(bucket).blob(f"{file_prefix}.csv")
    if not blob.exists():
        print(f"[backfill] {file_prefix}.csv not yet in gs://{bucket}/ — re-run after the task completes")
        return
    blob.reload()  # populate .size and .updated lazily
    staging = repo_root() / "data" / "raw" / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    local = staging / f"{Path(file_prefix).name}.csv"
    size_mb = (blob.size or 0) / 1e6
    print(f"[backfill] downloading {size_mb:.1f} MB -> {local}")
    blob.download_to_filename(str(local))

    df = pd.read_csv(local)
    print(f"[backfill] {len(df):,} rows, {df['roi'].nunique()} ROIs, "
          f"date range {df['date'].min()}..{df['date'].max()}")

    df["year"] = pd.to_datetime(df["date"]).dt.year.astype(int)
    raw_dir = repo_root() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for y, sub in df.groupby("year"):
        out = raw_dir / f"tropomi_daily_{y}.csv"
        sub.drop(columns=["year"]).sort_values(["date", "roi"]).to_csv(out, index=False)
        print(f"  wrote {out.name} ({len(sub):,} rows)")


if __name__ == "__main__":
    main()
