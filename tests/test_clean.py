"""Unit tests for AERA data cleaning and QA/QC quality flagging.

All tests utilize clearly labelled synthetic fixtures—never real observations—
to verify the five contractual cleaning requirements:
1. A 2-hour gap is interpolated.
2. A 5-hour gap remains missing.
3. Six consecutive equal values are flagged and removed.
4. Values -5 and 1500 are flagged and removed.
5. Timestamps are strictly hourly with no duplicates.
"""

import numpy as np
import pandas as pd
import pytest

from aera.clean import clean


def _make_synthetic_weather(timestamps: pd.DatetimeIndex) -> pd.DataFrame:
    """Helper to generate matching synthetic weather DataFrame."""
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "temperature": np.full(len(timestamps), 25.0),
            "relative_humidity": np.full(len(timestamps), 60.0),
            "rainfall": np.full(len(timestamps), 0.0),
            "wind_speed": np.full(len(timestamps), 10.0),
            "wind_direction": np.full(len(timestamps), 180.0),
            "boundary_layer_height": np.full(len(timestamps), 500.0),
        }
    )


def test_two_hour_gap_is_interpolated():
    """Requirement 1: A 2-hour gap is interpolated and marked with pm25_filled=True."""
    # 4 hourly slots: t0 (10.0), t1 (missing), t2 (missing), t3 (40.0)
    idx = pd.date_range("2026-01-01 00:00:00+05:30", periods=4, freq="1h")
    df_pm25 = pd.DataFrame(
        {
            "timestamp": [idx[0], idx[3]],
            "station_id": [1, 1],
            "station_name": ["Synthetic Station", "Synthetic Station"],
            "lat": [19.0, 19.0],
            "lon": [72.8, 72.8],
            "pm25": [10.0, 40.0],
        }
    )
    df_weather = _make_synthetic_weather(idx)

    cleaned = clean(df_pm25, df_weather)

    assert len(cleaned) == 4, f"Expected 4 hourly rows, found {len(cleaned)}"

    # Check that t1 and t2 were filled
    row_t1 = cleaned[cleaned["timestamp"] == idx[1]].iloc[0]
    row_t2 = cleaned[cleaned["timestamp"] == idx[2]].iloc[0]

    assert row_t1["pm25_filled"] is True or row_t1["pm25_filled"] == 1
    assert row_t2["pm25_filled"] is True or row_t2["pm25_filled"] == 1
    assert row_t1["flag_gap"] is True or row_t1["flag_gap"] == 1
    assert row_t2["flag_gap"] is True or row_t2["flag_gap"] == 1

    # Linear interpolation between 10.0 and 40.0 yields 20.0 and 30.0
    assert np.isclose(row_t1["pm25"], 20.0), f"Expected 20.0, got {row_t1['pm25']}"
    assert np.isclose(row_t2["pm25"], 30.0), f"Expected 30.0, got {row_t2['pm25']}"

    # Verify bounding observed rows were not marked filled
    assert not cleaned[cleaned["timestamp"] == idx[0]]["pm25_filled"].iloc[0]
    assert not cleaned[cleaned["timestamp"] == idx[3]]["pm25_filled"].iloc[0]


def test_five_hour_gap_remains_missing():
    """Requirement 2: A 5-hour gap remains missing (not interpolated, pm25_filled=False)."""
    # 7 hourly slots: t0 (10.0), t1..t5 (missing 5 hours), t6 (70.0)
    idx = pd.date_range("2026-01-01 00:00:00+05:30", periods=7, freq="1h")
    df_pm25 = pd.DataFrame(
        {
            "timestamp": [idx[0], idx[6]],
            "station_id": [1, 1],
            "station_name": ["Synthetic Station", "Synthetic Station"],
            "lat": [19.0, 19.0],
            "lon": [72.8, 72.8],
            "pm25": [10.0, 70.0],
        }
    )
    df_weather = _make_synthetic_weather(idx)

    cleaned = clean(df_pm25, df_weather)

    assert len(cleaned) == 7, f"Expected 7 hourly rows, found {len(cleaned)}"

    # All 5 intermediate hours must remain NaN and not filled
    for t in idx[1:6]:
        row = cleaned[cleaned["timestamp"] == t].iloc[0]
        assert pd.isna(row["pm25"]), f"Hour {t} was interpolated but should remain NaN"
        assert not row["pm25_filled"], f"Hour {t} has pm25_filled=True but gap was >3 hours"
        assert row["flag_gap"], f"Hour {t} should have flag_gap=True"


def test_six_consecutive_equal_values_flagged_and_removed():
    """Requirement 3: Six consecutive equal values are flagged with flag_stuck and set to NaN."""
    # 10 hourly slots with a stuck run of 6 consecutive equal values (30.0)
    idx = pd.date_range("2026-01-01 00:00:00+05:30", periods=10, freq="1h")
    values = [50.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 60.0, 70.0, 80.0]
    df_pm25 = pd.DataFrame(
        {
            "timestamp": idx,
            "station_id": [1] * 10,
            "station_name": ["Synthetic Station"] * 10,
            "lat": [19.0] * 10,
            "lon": [72.8] * 10,
            "pm25": values,
        }
    )
    df_weather = _make_synthetic_weather(idx)

    cleaned = clean(df_pm25, df_weather)

    assert len(cleaned) == 10

    # The 6 stuck slots (indices 1 to 6) must have flag_stuck=True and pm25 is NaN
    for i in range(1, 7):
        row = cleaned[cleaned["timestamp"] == idx[i]].iloc[0]
        assert row["flag_stuck"], f"Hour {idx[i]} should be flagged as stuck"
        assert pd.isna(row["pm25"]), f"Hour {idx[i]} stuck value was not removed (set to NaN)"

    # Non-stuck slots must remain intact
    for i in [0, 7, 8, 9]:
        row = cleaned[cleaned["timestamp"] == idx[i]].iloc[0]
        assert not row["flag_stuck"], f"Hour {idx[i]} should not be flagged as stuck"
        assert np.isclose(row["pm25"], values[i]), f"Hour {idx[i]} value altered unexpectedly"


def test_impossible_values_flagged_and_removed():
    """Requirement 4: Values -5 and 1500 are flagged with flag_impossible and set to NaN."""
    idx = pd.date_range("2026-01-01 00:00:00+05:30", periods=5, freq="1h")
    values = [50.0, -5.0, 60.0, 1500.0, 70.0]
    df_pm25 = pd.DataFrame(
        {
            "timestamp": idx,
            "station_id": [1] * 5,
            "station_name": ["Synthetic Station"] * 5,
            "lat": [19.0] * 5,
            "lon": [72.8] * 5,
            "pm25": values,
        }
    )
    df_weather = _make_synthetic_weather(idx)

    cleaned = clean(df_pm25, df_weather)

    assert len(cleaned) == 5

    # Index 1 (-5.0)
    row_neg = cleaned[cleaned["timestamp"] == idx[1]].iloc[0]
    assert row_neg["flag_impossible"], "Value -5.0 was not flagged as impossible"
    assert pd.isna(row_neg["pm25"]), "Value -5.0 was not removed (set to NaN)"

    # Index 3 (1500.0)
    row_high = cleaned[cleaned["timestamp"] == idx[3]].iloc[0]
    assert row_high["flag_impossible"], "Value 1500.0 was not flagged as impossible"
    assert pd.isna(row_high["pm25"]), "Value 1500.0 was not removed (set to NaN)"

    # Valid values preserved
    assert np.isclose(cleaned[cleaned["timestamp"] == idx[0]]["pm25"].iloc[0], 50.0)
    assert np.isclose(cleaned[cleaned["timestamp"] == idx[2]]["pm25"].iloc[0], 60.0)
    assert np.isclose(cleaned[cleaned["timestamp"] == idx[4]]["pm25"].iloc[0], 70.0)


def test_timestamps_strictly_hourly_no_duplicates():
    """Requirement 5: Timestamps are strictly hourly with no duplicates."""
    idx = pd.date_range("2026-01-01 00:00:00+05:30", periods=5, freq="1h")
    # Unsorted input with duplicate timestamp and missing hour
    df_pm25 = pd.DataFrame(
        {
            "timestamp": [idx[2], idx[0], idx[0], idx[4]],  # duplicate idx[0], missing idx[1], idx[3]
            "station_id": [1, 1, 1, 1],
            "station_name": ["Synthetic Station"] * 4,
            "lat": [19.0] * 4,
            "lon": [72.8] * 4,
            "pm25": [30.0, 10.0, 10.0, 50.0],
        }
    )
    df_weather = _make_synthetic_weather(idx)

    cleaned = clean(df_pm25, df_weather)

    # Output must have exactly 5 hours: idx[0] to idx[4]
    assert len(cleaned) == 5, f"Expected 5 hourly rows, got {len(cleaned)}"

    # Check zero duplicates on (station_id, timestamp)
    dups = cleaned.duplicated(subset=["station_id", "timestamp"]).sum()
    assert dups == 0, f"Found {dups} duplicate timestamps"

    # Strictly hourly step
    diffs = cleaned["timestamp"].diff().dropna().unique()
    assert len(diffs) == 1, f"Expected 1 unique time diff, got {diffs}"
    assert diffs[0] == pd.Timedelta(hours=1), f"Expected 1h time diff, got {diffs[0]}"

    # Timezone check
    assert cleaned["timestamp"].dt.tz is not None
    assert str(cleaned["timestamp"].dt.tz) == "Asia/Kolkata"
