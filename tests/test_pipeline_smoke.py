"""Smoke tests for the end-to-end CityPulse data and modeling pipeline."""

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from config import PROCESSED_DATA_DIR, SAMPLE_DATA_DIR, OUTPUTS_DIR, MODELS_DIR


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


def test_clean_parquet_contract():
    """Verify clean.parquet exists and meets S4 schema and regularity contract."""
    clean_file = PROCESSED_DATA_DIR / "clean.parquet"
    assert clean_file.exists(), "clean.parquet file does not exist."

    df = pd.read_parquet(clean_file)
    expected_cols = [
        "timestamp",
        "station_id",
        "station_name",
        "lat",
        "lon",
        "pm25",
        "pm25_filled",
        "flag_gap",
        "flag_stuck",
        "flag_impossible",
        "temperature",
        "relative_humidity",
        "rainfall",
        "wind_speed",
        "wind_direction",
        "boundary_layer_height",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing expected column in clean.parquet: {col}"

    # Verify timezone is Asia/Kolkata
    assert df["timestamp"].dt.tz is not None, "Timestamp must be timezone-aware"
    assert str(df["timestamp"].dt.tz) == "Asia/Kolkata", f"Expected Asia/Kolkata, got {df['timestamp'].dt.tz}"

    # Verify regular hourly steps per station
    for st_id, sdf in df.groupby("station_id"):
        diffs = sdf["timestamp"].diff().dropna().unique()
        assert len(diffs) == 1, f"Station {st_id} timeline not strictly regular: {diffs}"
        assert diffs[0] == pd.Timedelta(hours=1), f"Station {st_id} step not 1h: {diffs[0]}"
        dups = sdf.duplicated(subset=["timestamp"]).sum()
        assert dups == 0, f"Station {st_id} has duplicate timestamps"


def test_quality_summary_contract():
    """Verify quality_summary.parquet exists and matches contract requirements."""
    summary_file = OUTPUTS_DIR / "quality_summary.parquet"
    assert summary_file.exists(), "quality_summary.parquet file does not exist."

    df = pd.read_parquet(summary_file)
    assert len(df) >= 8, f"Expected at least 8 stations in summary, found {len(df)}"

    required_cols = ["station_id", "station_name", "valid_hours", "total_hours", "data_quality_pct", "quality_label"]
    for col in required_cols:
        assert col in df.columns, f"Missing column in quality_summary: {col}"

    # Verify quality labels are within Good, Fair, Low
    valid_labels = {"Good", "Fair", "Low"}
    assert set(df["quality_label"].unique()).issubset(valid_labels), f"Invalid quality labels: {df['quality_label'].unique()}"

    # Verify percentage logic matches thresholds
    for _, row in df.iterrows():
        pct = row["data_quality_pct"]
        lbl = row["quality_label"]
        if pct >= 90.0:
            assert lbl == "Good"
        elif pct >= 70.0:
            assert lbl == "Fair"
        else:
            assert lbl == "Low"


def test_patterns_and_heatmap_contract():
    """Verify patterns.json and heatmap.parquet meet S5 contract."""
    patterns_file = OUTPUTS_DIR / "patterns.json"
    heatmap_file = OUTPUTS_DIR / "heatmap.parquet"
    heatmap_html = OUTPUTS_DIR / "heatmap.html"

    assert patterns_file.exists(), "patterns.json does not exist."
    assert heatmap_file.exists(), "heatmap.parquet does not exist."
    assert heatmap_html.exists(), "heatmap.html does not exist."

    patterns_data = json.loads(patterns_file.read_text(encoding="utf-8"))
    assert "patterns" in patterns_data, "patterns key missing in patterns.json"
    p_dict = patterns_data["patterns"]
    assert "evening_peak" in p_dict
    assert "calm_wind_episodes" in p_dict
    assert "persistent_worst_stations" in p_dict

    # Check each pattern has title, sentence, data_window, weak
    for p_name, p_val in p_dict.items():
        assert "title" in p_val, f"title missing in {p_name}"
        assert "sentence" in p_val, f"sentence missing in {p_name}"
        assert "data_window" in p_val, f"data_window missing in {p_name}"
        assert isinstance(p_val["weak"], bool), f"weak must be bool in {p_name}"

    df_heatmap = pd.read_parquet(heatmap_file)
    expected_cols = ["station_id", "station_name", "hour", "median_pm25"]
    for col in expected_cols:
        assert col in df_heatmap.columns, f"Missing column in heatmap: {col}"

    # 9 stations * 24 hours = 216 rows
    assert len(df_heatmap) == 216, f"Expected 216 heatmap rows, got {len(df_heatmap)}"


def test_features_parquet_contract():
    """Verify features.parquet meets S6 schema and causal feature requirements."""
    feat_file = PROCESSED_DATA_DIR / "features.parquet"
    assert feat_file.exists(), "features.parquet does not exist."

    df = pd.read_parquet(feat_file)
    expected_cols = [
        "pm25",
        "pm25_lag_1",
        "pm25_lag_3",
        "pm25_lag_6",
        "pm25_lag_12",
        "pm25_lag_24",
        "pm25_roll_mean_6h",
        "pm25_roll_max_6h",
        "pm25_roll_mean_24h",
        "pm25_roll_max_24h",
        "hour",
        "weekday",
        "month",
        "wind_speed",
        "sin_wind_dir",
        "cos_wind_dir",
        "temperature",
        "relative_humidity",
        "rainfall_sum_24h",
        "boundary_layer_height",
        "forecast_wind_speed_mean_24h",
        "forecast_rainfall_sum_24h",
        "target_pm25",
        "target_class",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing feature column: {col}"

    # Station count: 9 stations
    assert df["station_id"].nunique() == 9, f"Expected 9 stations, got {df['station_id'].nunique()}"


def test_baseline_metrics_contract():
    """Verify baseline_metrics.json exists and contains Persistence and 24h Moving Avg."""
    baseline_file = OUTPUTS_DIR / "baseline_metrics.json"
    assert baseline_file.exists(), "baseline_metrics.json does not exist."

    data = json.loads(baseline_file.read_text(encoding="utf-8"))
    assert "persistence" in data, "persistence key missing in baseline_metrics.json"
    assert "moving_average_24h" in data, "moving_average_24h key missing in baseline_metrics.json"
    assert "test_period" in data, "test_period missing in baseline_metrics.json"

    p = data["persistence"]
    ma = data["moving_average_24h"]
    assert "mae" in p and "f1_unhealthy_or_worse" in p
    assert "mae" in ma and "f1_unhealthy_or_worse" in ma
    assert p["mae"] > 0 and ma["mae"] > 0


def test_model_artifacts_and_metrics_contract():
    """Verify trained models and model_metrics.json meet S7 contract."""
    reg_file = MODELS_DIR / "reg.joblib"
    clf_file = MODELS_DIR / "clf.joblib"
    metrics_file = OUTPUTS_DIR / "model_metrics.json"

    assert reg_file.exists(), "reg.joblib does not exist."
    assert clf_file.exists(), "clf.joblib does not exist."
    assert metrics_file.exists(), "model_metrics.json does not exist."

    # Verify models can be unpickled
    reg = joblib.load(reg_file)
    clf = joblib.load(clf_file)
    assert hasattr(reg, "predict")
    assert hasattr(clf, "predict_proba")

    data = json.loads(metrics_file.read_text(encoding="utf-8"))
    assert "lightgbm_regressor" in data
    assert "lightgbm_classifier" in data
    assert "baselines" in data
    assert "comparison_summary" in data

    summary = data["comparison_summary"]
    assert "production_decision" in summary
    assert "decision_rationale" in summary


def test_predictions_parquet_contract():
    """Verify predictions.parquet contains required columns, valid probabilities, and all stations."""
    pred_file = OUTPUTS_DIR / "predictions.parquet"
    assert pred_file.exists(), "predictions.parquet does not exist."

    df = pd.read_parquet(pred_file)
    assert len(df) == 9, f"Expected 9 stations, got {len(df)}"

    required_cols = [
        "station_id",
        "predicted_class",
        "p_good",
        "p_unhealthy",
        "p_severe",
        "predicted_pm25",
        "as_of",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required predictions column: {col}"

    # Verify probabilities are valid and sum to 1.0
    prob_sums = df["p_good"] + df["p_unhealthy"] + df["p_severe"]
    for idx, s in enumerate(prob_sums):
        assert np.isclose(s, 1.0, atol=1e-3), f"Row {idx} probabilities sum to {s}, expected 1.0"

    # All probabilities in [0, 1]
    assert (df["p_good"] >= 0).all() and (df["p_good"] <= 1).all()
    assert (df["p_unhealthy"] >= 0).all() and (df["p_unhealthy"] <= 1).all()
    assert (df["p_severe"] >= 0).all() and (df["p_severe"] <= 1).all()

    # Predicted classes valid
    valid_classes = {"Good", "Unhealthy", "Severe"}
    assert set(df["predicted_class"].unique()).issubset(valid_classes)


def test_eval_comparison_chart_output():
    """Verify interactive evaluation comparison chart HTML was created."""
    chart_file = OUTPUTS_DIR / "s7_eval_comparison.html"
    assert chart_file.exists(), "s7_eval_comparison.html does not exist."
    assert chart_file.stat().st_size > 10000, "s7_eval_comparison.html is suspiciously small or empty."

