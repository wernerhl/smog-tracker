"""Shared helpers for the smog-tracker extraction pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def repo_root() -> Path:
    return REPO_ROOT


def init_ee() -> None:
    """Initialize Earth Engine.

    Production: service-account JSON in env var GEE_SERVICE_ACCOUNT_KEY +
    GEE_SERVICE_ACCOUNT_EMAIL + GCP_PROJECT_ID (set as GitHub secrets).
    Local fallback: file path in GOOGLE_APPLICATION_CREDENTIALS.
    """
    import ee
    project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("EE_PROJECT")
    key_json = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
    key_email = os.environ.get("GEE_SERVICE_ACCOUNT_EMAIL")
    key_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if key_json and key_email:
        # Production path — JSON content inline (GitHub Actions secret).
        creds = ee.ServiceAccountCredentials(key_email, key_data=key_json)
        ee.Initialize(credentials=creds, project=project)
    elif key_file and Path(key_file).exists():
        # Local path — service-account key file (mirrors whl.Coca/_common.init_ee).
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            key_file,
            scopes=[
                "https://www.googleapis.com/auth/earthengine",
                "https://www.googleapis.com/auth/cloud-platform",
            ],
        )
        ee.Initialize(credentials=creds, project=project)
    else:
        # Last-resort default (interactive auth).
        ee.Initialize(project=project) if project else ee.Initialize()


def roi_buffer(roi: dict):
    """Return an ee.Geometry for a config ROI (circular buffer in metres)."""
    import ee
    return ee.Geometry.Point([roi["lon"], roi["lat"]]).buffer(roi["buffer_km"] * 1000)
