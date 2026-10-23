"""Unit tests for AERA recurring pattern discovery (patterns.py).

All tests utilize clearly labelled synthetic fixtures to verify:
1. Required output keys and JSON serialization.
2. Detection of a known synthetic evening spike.
3. Correct percentage calculations.
4. Weak-pattern handling for negligible uplift or insufficient data.
5. Correct station ranking and missing-value handling.
"""

import json
import numpy as np
import pandas as pd
import pytest

from aera.patterns import (
    build_station_hour_heatmap,
    calm_wind_episodes,
    evening_peak,
    persistent_worst_stations,
)


def _make_synthetic_dataset(n_days: int = 10, base_pm: float = 40.0) -> pd.DataFrame:
    """Helper to create synthetic hourly dataset for 2 stations."""
    idx = pd.date_range("2026-01-01 00:00:00+05:30", periods=n_days * 24, freq="1h")
    records = []
    for st_id, st_name in [(1, "Station A"), (2, "Station B")]:
        for t in idx:
            records.append(
                {
                    "timestamp": t,
                    "station_id": st_id,
                    "station_name": st_name,
                    "lat": 19.0 + st_id * 0.05,
                    "lon": 72.8 + st_id * 0.05,
                    "pm25": float(base_pm),
                    "pm25_filled": False,
                    "flag_gap": False,
                    "flag_stuck": False,
                    "flag_impossible": False,
                    "temperature": 25.0,
                    "relative_humidity": 60.0,
                    "rainfall": 0.0,
                    "wind_speed": 10.0,
                    "wind_direction": 180.0,
                    "boundary_layer_height": 500.0,
                }
            )
    return pd.DataFrame(records)


def test_required_output_keys_and_json_serialization():
    """Requirement 1: Functions return required keys and serialize cleanly to JSON."""
    df = _make_synthetic_dataset(n_days=5)

    p1 = evening_peak(df)
    p2 = calm_wind_episodes(df)
    p3 = persistent_worst_stations(df)

    for p in [p1, p2, p3]:
        assert "title" in p, "Missing 'title' key"
        assert "sentence" in p, "Missing 'sentence' key"
        assert "data_window" in p, "Missing 'data_window' key"
        assert "weak" in p, "Missing 'weak' key"
        assert isinstance(p["weak"], bool), f"'weak' must be bool, got {type(p['weak'])}"

        # Must serialize cleanly to JSON without errors
        serialized = json.dumps(p)
        assert len(serialized) > 0


def test_known_synthetic_evening_spike():
    """Requirement 2: Detection of a known synthetic evening spike."""
    # Synthetic dataset where 20:00 (8 PM) has a distinct high spike
    df = _make_synthetic_dataset(n_days=10, base_pm=40.0)
    # Inject 100.0 µg/m³ at 20:00 IST
    df.loc[df["timestamp"].dt.hour == 20, "pm25"] = 100.0

    p1 = evening_peak(df)

    assert p1["peak_hour"] == 20, f"Expected peak at 20:00, found {p1['peak_hour']}"
    assert np.isclose(p1["peak_median"], 100.0), f"Expected peak median 100.0, got {p1['peak_median']}"
    assert p1["percentage_difference"] > 0, "Expected positive uplift"
    assert p1["weak"] is False, "Pattern should not be marked weak for a 150% spike"
    assert "20:00" in p1["sentence"]


def test_correct_percentage_calculations():
    """Requirement 3: Mathematical accuracy of reported percentage differences."""
    df = _make_synthetic_dataset(n_days=10, base_pm=50.0)
    # Set hour 12 to 75.0 (50% uplift over 50.0)
    df.loc[df["timestamp"].dt.hour == 12, "pm25"] = 75.0

    p1 = evening_peak(df)
    expected_pct = round(100.0 * (75.0 - 50.0) / 50.0, 1)  # 50.0%
    assert np.isclose(p1["percentage_difference"], expected_pct, atol=0.1)


def test_weak_pattern_handling():
    """Requirement 4: Weak-pattern handling for negligible uplift and insufficient data."""
    # 1. Flatline data with 0% uplift -> weak is True
    df_flat = _make_synthetic_dataset(n_days=5, base_pm=50.0)
    p1_flat = evening_peak(df_flat)
    assert p1_flat["weak"] is True, "Flatline diurnal pattern must be flagged as weak"

    # 2. Insufficient observations (<100 rows)
    df_small = df_flat.head(20).copy()
    p1_small = evening_peak(df_small)
    assert p1_small["weak"] is True, "Insufficient sample must be flagged as weak"

    # 3. Calm wind pattern with uplift < 5% -> weak is True
    df_calm = _make_synthetic_dataset(n_days=10, base_pm=50.0)
    # Set alternating wind speed: 2 km/h for 4 hours, 15 km/h otherwise
    # But keep PM2.5 equal during both (50.0 vs 50.0)
    df_calm.loc[df_calm["timestamp"].dt.hour < 4, "wind_speed"] = 2.0
    p2_calm = calm_wind_episodes(df_calm)
    assert p2_calm["weak"] is True, "Calm wind episode with no PM2.5 uplift must be flagged as weak"

    # 4. Empty dataframe
    df_empty = pd.DataFrame(columns=["timestamp", "pm25", "wind_speed", "station_id"])
    assert evening_peak(df_empty)["weak"] is True
    assert calm_wind_episodes(df_empty)["weak"] is True
    assert persistent_worst_stations(df_empty)["weak"] is True


def test_station_ranking_and_missing_values():
    """Requirement 5: Correct station ranking and missing-value exclusion from denominator."""
    idx = pd.date_range("2026-01-01 00:00:00+05:30", periods=10, freq="1h")

    # Station 1: 8 valid, 4 > 60 -> 50%
    st1 = pd.DataFrame(
        {
            "timestamp": idx,
            "station_id": 1,
            "station_name": "Station High",
            "pm25": [70.0, 80.0, 90.0, 100.0, 30.0, 40.0, 50.0, 50.0, np.nan, np.nan],
        }
    )

    # Station 2: 10 valid, 8 > 60 -> 80% (Highest rank)
    st2 = pd.DataFrame(
        {
            "timestamp": idx,
            "station_id": 2,
            "station_name": "Station Highest",
            "pm25": [70.0, 80.0, 90.0, 100.0, 70.0, 80.0, 90.0, 100.0, 30.0, 40.0],
        }
    )

    # Station 3: 10 valid, 1 > 60 -> 10% (Lowest rank)
    st3 = pd.DataFrame(
        {
            "timestamp": idx,
            "station_id": 3,
            "station_name": "Station Low",
            "pm25": [70.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    )

    df = pd.concat([st1, st2, st3], ignore_index=True)
    p3 = persistent_worst_stations(df, threshold=60.0)

    top_stations = p3["top_stations"]
    assert len(top_stations) == 3

    # Ranking must be Station 2 (80%) > Station 1 (50%) > Station 3 (10%)
    assert top_stations[0]["station_id"] == 2
    assert np.isclose(top_stations[0]["exceedance_percentage"], 80.0)

    assert top_stations[1]["station_id"] == 1
    # Check that missing values were excluded from Station 1 denominator: 4 / 8 = 50.0%, NOT 4 / 10 = 40.0%
    assert top_stations[1]["valid_hours"] == 8
    assert np.isclose(top_stations[1]["exceedance_percentage"], 50.0)

    assert top_stations[2]["station_id"] == 3
    assert np.isclose(top_stations[2]["exceedance_percentage"], 10.0)


def test_heatmap_dataframe_structure():
    """Verify build_station_hour_heatmap returns expected schema and grid."""
    df = _make_synthetic_dataset(n_days=2)
    heatmap_df = build_station_hour_heatmap(df)

    assert "station_id" in heatmap_df.columns
    assert "station_name" in heatmap_df.columns
    assert "hour" in heatmap_df.columns
    assert "median_pm25" in heatmap_df.columns

    # 2 stations * 24 hours = 48 rows
    assert len(heatmap_df) == 48
    assert set(heatmap_df["hour"].unique()) == set(range(24))
