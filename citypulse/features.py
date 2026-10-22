"""Feature engineering module for CityPulse PM2.5 forecasting.

Generates temporal lags, rolling aggregations, calendar features, weather encodings,
and forward-looking weather forecast stand-ins for 24-hour horizon forecasting.

Strictly enforces causal feature construction:
For each station and hour t, all features are computed using only information available
at or before t, with the explicit documented exception of the next-24-hour weather forecast
stand-ins (mean wind speed and total rainfall) derived from weather data as proxies for
production numerical weather prediction (NWP) forecasts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from config import (
    FORECAST_HORIZON_HOURS,
    GOOD_MAX,
    PROCESSED_DATA_DIR,
    UNHEALTHY_MAX,
)

logger = logging.getLogger(__name__)

# Feature column definitions
FEATURE_COLUMNS: List[str] = [
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
]

TARGET_COLUMNS: List[str] = [
    "target_pm25",
    "target_class",
]

METADATA_COLUMNS: List[str] = [
    "timestamp",
    "station_id",
    "station_name",
    "lat",
    "lon",
    "pm25_filled",
    "flag_gap",
    "flag_stuck",
    "flag_impossible",
]


def classify_pm25(val: float | int | None) -> str | None:
    """Classify PM2.5 concentration into standard risk tiers.

    Tiers (defined in config.py):
    - Good: <= 60 µg/m³
    - Unhealthy: > 60 and <= 250 µg/m³
    - Severe: > 250 µg/m³

    Returns None if value is NaN or missing.
    """
    if pd.isna(val):
        return None
    val_f = float(val)
    if val_f <= GOOD_MAX:
        return "Good"
    elif val_f <= UNHEALTHY_MAX:
        return "Unhealthy"
    else:
        return "Severe"


def compute_station_features(df_st: pd.DataFrame) -> pd.DataFrame:
    """Compute causal features, forecast stand-ins, and targets for a single station.

    Requirements:
    - Input must have a regular hourly timestamp and be sorted chronologically.
    - Uses only past/present observations for historical features.
    - Forecast stand-ins use [t+1, t+24] weather.
    - Target is pm25 at t+24.
    """
    st = df_st.copy().sort_values("timestamp").reset_index(drop=True)

    # 1. Historical PM2.5 Lags (strictly t - k)
    for lag in [1, 3, 6, 12, 24]:
        st[f"pm25_lag_{lag}"] = st["pm25"].shift(lag)

    # 2. Historical Rolling Aggregations over past hours (inclusive of t)
    # 6-hour rolling statistics
    st["pm25_roll_mean_6h"] = st["pm25"].rolling(window=6, min_periods=1).mean()
    st["pm25_roll_max_6h"] = st["pm25"].rolling(window=6, min_periods=1).max()

    # 24-hour rolling statistics
    st["pm25_roll_mean_24h"] = st["pm25"].rolling(window=24, min_periods=1).mean()
    st["pm25_roll_max_24h"] = st["pm25"].rolling(window=24, min_periods=1).max()

    # 3. 24-hour Historical Rainfall Sum (inclusive of t)
    if "rainfall" in st.columns:
        st["rainfall_sum_24h"] = st["rainfall"].rolling(window=24, min_periods=1).sum()
    else:
        st["rainfall_sum_24h"] = np.nan

    # 4. Next-24-hour Weather Forecast Stand-ins [t+1 to t+24]
    # Note: Derived from weather observations as stand-ins for operational NWP forecasts.
    if "wind_speed" in st.columns:
        rev_wind = st["wind_speed"].iloc[::-1]
        st["forecast_wind_speed_mean_24h"] = (
            rev_wind.rolling(window=24, min_periods=1).mean().iloc[::-1].shift(-1)
        )
    else:
        st["forecast_wind_speed_mean_24h"] = np.nan

    if "rainfall" in st.columns:
        rev_rain = st["rainfall"].iloc[::-1]
        st["forecast_rainfall_sum_24h"] = (
            rev_rain.rolling(window=24, min_periods=1).sum().iloc[::-1].shift(-1)
        )
    else:
        st["forecast_rainfall_sum_24h"] = np.nan

    # 5. Targets (t + 24h)
    st["target_pm25"] = st["pm25"].shift(-FORECAST_HORIZON_HOURS)
    st["target_class"] = st["target_pm25"].apply(classify_pm25)

    return st


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute features and targets across all stations in a cleaned DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned observation DataFrame containing hourly records for one or more stations.

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame with engineered features, forecast stand-ins, targets, and metadata.
    """
    if df.empty:
        return pd.DataFrame(columns=METADATA_COLUMNS + FEATURE_COLUMNS + TARGET_COLUMNS)

    # Process station by station
    station_dfs: List[pd.DataFrame] = []
    if "station_id" in df.columns:
        for _, group in df.groupby("station_id", as_index=False):
            station_dfs.append(compute_station_features(group))
    else:
        station_dfs.append(compute_station_features(df))

    result = pd.concat(station_dfs, ignore_index=True)

    # Calendar features from Asia/Kolkata timestamps
    ts = pd.to_datetime(result["timestamp"])
    result["hour"] = ts.dt.hour
    result["weekday"] = ts.dt.weekday
    result["month"] = ts.dt.month

    # Cyclical encoding of wind direction
    if "wind_direction" in result.columns:
        rad = np.radians(result["wind_direction"].fillna(0))
        result["sin_wind_dir"] = np.where(result["wind_direction"].notna(), np.sin(rad), np.nan)
        result["cos_wind_dir"] = np.where(result["wind_direction"].notna(), np.cos(rad), np.nan)
    else:
        result["sin_wind_dir"] = np.nan
        result["cos_wind_dir"] = np.nan

    # Ensure required weather columns exist
    for col in ["wind_speed", "temperature", "relative_humidity", "boundary_layer_height"]:
        if col not in result.columns:
            result[col] = np.nan

    # Reorder columns: metadata, features, targets
    all_cols = []
    for c in METADATA_COLUMNS:
        if c in result.columns and c not in all_cols:
            all_cols.append(c)
    for c in FEATURE_COLUMNS:
        if c in result.columns and c not in all_cols:
            all_cols.append(c)
    for c in TARGET_COLUMNS:
        if c in result.columns and c not in all_cols:
            all_cols.append(c)

    # Add any remaining columns
    for c in result.columns:
        if c not in all_cols:
            all_cols.append(c)

    return result[all_cols].sort_values(["station_id", "timestamp"]).reset_index(drop=True)


def filter_modeling_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Filter DataFrame to valid training/evaluation rows.

    Excludes rows where:
    - Target PM2.5 at t+24h is missing.
    - Target risk class is missing.
    - Current PM2.5 observation at hour t is missing.
    """
    valid_mask = df["target_pm25"].notna() & df["target_class"].notna() & df["pm25"].notna()
    return df[valid_mask].copy().reset_index(drop=True)


def get_feature_columns() -> List[str]:
    """Return the list of predictor feature column names."""
    return list(FEATURE_COLUMNS)


def main() -> None:
    """Run feature engineering on processed clean data and save output."""
    print("=" * 80)
    print("CityPulse Step 6: Feature Engineering")
    print("=" * 80)

    clean_path = PROCESSED_DATA_DIR / "clean.parquet"
    if not clean_path.exists():
        print(f"BLOCKER: {clean_path} does not exist.")
        return

    df_clean = pd.read_parquet(clean_path)
    print(f"Loaded {len(df_clean)} cleaned hourly rows across {df_clean['station_id'].nunique()} stations.")

    feat_df = compute_features(df_clean)
    out_path = PROCESSED_DATA_DIR / "features.parquet"
    feat_df.to_parquet(out_path, index=False)
    print(f"[Saved] Full features dataset: {out_path} ({len(feat_df)} rows, {len(feat_df.columns)} columns)")

    modeling_df = filter_modeling_dataset(feat_df)
    print(f"Valid modeling rows (valid t and t+24h PM2.5): {len(modeling_df)}")
    print(f"Target distribution across valid rows:")
    print(modeling_df["target_class"].value_counts(dropna=False).to_string())
    print("=" * 80)


if __name__ == "__main__":
    main()
