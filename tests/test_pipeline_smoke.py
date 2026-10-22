"""Smoke tests for the end-to-end CityPulse data and modeling pipeline."""

import json
from pathlib import Path
import pandas as pd
import pytest

from config import PROCESSED_DATA_DIR, SAMPLE_DATA_DIR, OUTPUTS_DIR


def test_processed_pm25_contract():
    """Verify processed PM2.5 Parquet meets contract requirements."""
    pm25_file = PROCESSED_DATA_DIR / "pm25_observed.parquet"
    assert pm25_file.exists(), "Processed PM2.5 Parquet file does not exist."

    df = pd.read_parquet(pm25_file)
    required_cols = [
        "timestamp_utc",
        "timestamp_ist",
        "station_id",
        "station_name",
        "lat",
        "lon",
        "pm25",
        "units",
        "source",
        "raw_obs_count",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"

    # Station count: >= 8 stations
    n_stations = df["station_id"].nunique()
    assert n_stations >= 8, f"Expected at least 8 stations, found {n_stations}"

    # Historical coverage: >= 90 days
    t_min = df["timestamp_utc"].min()
    t_max = df["timestamp_utc"].max()
    days_coverage = (t_max - t_min).total_seconds() / 86400
    assert days_coverage >= 90, f"Expected at least 90 days coverage, found {days_coverage:.1f}"

    # No duplicate station/timestamps
    dups = df.duplicated(subset=["station_id", "timestamp_utc"]).sum()
    assert dups == 0, f"Found {dups} duplicate timestamp records"

    # Units and source populated
    assert df["units"].str.contains("g/m").all(), "Unexpected units found in PM2.5 dataset"
    assert df["source"].str.contains("OpenAQ").all(), "Missing or invalid source provenance"


def test_processed_weather_contract():
    """Verify processed weather Parquet meets contract requirements."""
    weather_file = PROCESSED_DATA_DIR / "weather_observed.parquet"
    assert weather_file.exists(), "Processed weather Parquet file does not exist."

    df = pd.read_parquet(weather_file)
    required_cols = [
        "timestamp_utc",
        "timestamp_ist",
        "lat",
        "lon",
        "temperature",
        "relative_humidity",
        "rainfall",
        "wind_speed",
        "wind_direction",
        "boundary_layer_height",
        "source",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required weather column: {col}"

    assert len(df) >= 2160, f"Expected at least 90 days (2160 hrs) of weather, found {len(df)}"
    # Boundary layer height must not be silently null or fabricated
    assert not df["boundary_layer_height"].isna().all(), "Boundary layer height is completely missing"


def test_sample_dataset_contract():
    """Verify cached real 3-station sample dataset and metadata."""
    pm25_sample_file = SAMPLE_DATA_DIR / "pm25_sample.parquet"
    weather_sample_file = SAMPLE_DATA_DIR / "weather_sample.parquet"
    meta_file = SAMPLE_DATA_DIR / "metadata.json"

    assert pm25_sample_file.exists(), "Sample PM2.5 file does not exist."
    assert weather_sample_file.exists(), "Sample weather file does not exist."
    assert meta_file.exists(), "Sample metadata file does not exist."

    df_pm25 = pd.read_parquet(pm25_sample_file)
    df_weather = pd.read_parquet(weather_sample_file)

    assert df_pm25["station_id"].nunique() == 3, f"Expected 3 stations in sample, found {df_pm25['station_id'].nunique()}"
    assert len(df_pm25) > 0, "Sample PM2.5 is empty"
    assert len(df_weather) > 0, "Sample weather is empty"

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert "sources" in meta, "Sources missing in sample metadata"
    assert len(meta["stations"]) == 3, "Metadata stations count mismatch"


def test_visual_check_output():
    """Verify Plotly visual inspection HTML was created."""
    chart_file = OUTPUTS_DIR / "s3_check.html"
    assert chart_file.exists(), "s3_check.html output file does not exist."
    assert chart_file.stat().st_size > 10000, "s3_check.html is suspiciously small or empty."
