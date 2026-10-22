"""Unit tests for feature engineering, causal leakage prevention, and splits."""

import numpy as np
import pandas as pd
import pytest

from config import GOOD_MAX, UNHEALTHY_MAX
from citypulse.features import (
    classify_pm25,
    compute_features,
    filter_modeling_dataset,
    get_feature_columns,
)
from citypulse.train import split_time


@pytest.fixture
def synthetic_timeseries() -> pd.DataFrame:
    """Generate a clean synthetic 120-hour hourly station timeline."""
    n_hours = 120
    timestamps = pd.date_range("2026-01-01 00:30:00+05:30", periods=n_hours, freq="1h")
    # Base synthetic values
    np.random.seed(42)
    pm25_vals = 30.0 + 20.0 * np.sin(np.linspace(0, 10, n_hours)) + np.random.normal(0, 2, n_hours)
    wind_speed = 10.0 + 5.0 * np.cos(np.linspace(0, 5, n_hours))
    wind_dir = np.linspace(0, 350, n_hours)
    rain = np.zeros(n_hours)
    rain[10:15] = 2.5

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "station_id": 999001,
            "station_name": "Synthetic Station 1",
            "lat": 19.0,
            "lon": 72.8,
            "pm25": pm25_vals,
            "pm25_filled": False,
            "flag_gap": False,
            "flag_stuck": False,
            "flag_impossible": False,
            "temperature": 25.0,
            "relative_humidity": 65.0,
            "rainfall": rain,
            "wind_speed": wind_speed,
            "wind_direction": wind_dir,
            "boundary_layer_height": 500.0,
        }
    )
    return df


def test_classify_pm25_thresholds():
    """Verify standard risk tier classification and boundary conditions."""
    assert classify_pm25(0.0) == "Good"
    assert classify_pm25(GOOD_MAX) == "Good"
    assert classify_pm25(GOOD_MAX + 0.01) == "Unhealthy"
    assert classify_pm25(UNHEALTHY_MAX) == "Unhealthy"
    assert classify_pm25(UNHEALTHY_MAX + 0.01) == "Severe"
    assert classify_pm25(1000.0) == "Severe"
    assert classify_pm25(np.nan) is None
    assert classify_pm25(None) is None


def test_feature_leakage_future_perturbation(synthetic_timeseries):
    """Verify that perturbing future observations does NOT leak into historical features at t."""
    df_orig = synthetic_timeseries.copy()
    feat_orig = compute_features(df_orig)

    # Perturb future observations starting at index 60 (hour 60)
    perturb_idx = 60
    df_perturbed = synthetic_timeseries.copy()
    df_perturbed.loc[perturb_idx:, "pm25"] = df_perturbed.loc[perturb_idx:, "pm25"] + 500.0

    feat_perturbed = compute_features(df_perturbed)

    # Core historical predictor features that must NOT be influenced by t' >= 60
    historical_features = [
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
    ]

    # For all rows strictly before the perturbation index (t < 60), features must be identical
    slice_orig = feat_orig.iloc[:perturb_idx][historical_features]
    slice_perturbed = feat_perturbed.iloc[:perturb_idx][historical_features]

    pd.testing.assert_frame_equal(
        slice_orig,
        slice_perturbed,
        check_exact=False,
        rtol=1e-5,
        atol=1e-5,
        obj="Historical features before perturbation index",
    )

    # Verify that the perturbation was actually detected in targets (at t = perturb_idx - 24)
    target_check_idx = perturb_idx - 24
    assert (
        feat_perturbed.loc[target_check_idx, "target_pm25"]
        > feat_orig.loc[target_check_idx, "target_pm25"] + 400.0
    ), "Target should reflect future PM2.5 changes"


def test_forecast_standins_calculation(synthetic_timeseries):
    """Verify next-24h forecast stand-ins look ahead exactly [t+1 to t+24]."""
    feat_df = compute_features(synthetic_timeseries)

    # For row index 10:
    # Expected forecast wind speed is mean of wind_speed for rows 11 through 34 (24 hours)
    expected_wind_mean = synthetic_timeseries.loc[11:34, "wind_speed"].mean()
    actual_wind_mean = feat_df.loc[10, "forecast_wind_speed_mean_24h"]
    assert np.isclose(expected_wind_mean, actual_wind_mean, atol=1e-4)

    # Expected rainfall sum for rows 11 through 34
    expected_rain_sum = synthetic_timeseries.loc[11:34, "rainfall"].sum()
    actual_rain_sum = feat_df.loc[10, "forecast_rainfall_sum_24h"]
    assert np.isclose(expected_rain_sum, actual_rain_sum, atol=1e-4)


def test_split_time_strictly_chronological(synthetic_timeseries):
    """Verify split_time performs strictly chronological partitioning with no overlap."""
    feat_df = compute_features(synthetic_timeseries)
    split_cutoff = "2026-01-03 12:30:00+05:30"

    train_df, test_df = split_time(feat_df, test_start=split_cutoff)

    assert not train_df.empty, "Train split is empty"
    assert not test_df.empty, "Test split is empty"

    train_max = train_df["timestamp"].max()
    test_min = test_df["timestamp"].min()

    assert train_max < pd.to_datetime(split_cutoff), f"Train max {train_max} >= cutoff {split_cutoff}"
    assert test_min >= pd.to_datetime(split_cutoff), f"Test min {test_min} < cutoff {split_cutoff}"
    assert train_max < test_min, f"Train max {train_max} is not strictly earlier than test min {test_min}"


def test_filter_modeling_dataset_drops_missing_target(synthetic_timeseries):
    """Verify filter_modeling_dataset excludes rows where target or current PM2.5 is null."""
    feat_df = compute_features(synthetic_timeseries)
    filtered = filter_modeling_dataset(feat_df)

    assert filtered["target_pm25"].isna().sum() == 0
    assert filtered["target_class"].isna().sum() == 0
    assert filtered["pm25"].isna().sum() == 0
    # Must drop the last 24 rows because they don't have t+24h target
    assert len(filtered) <= len(feat_df) - 24
