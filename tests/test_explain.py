"""Unit tests for model explainability, SHAP driver extraction, and prediction intervals."""

import numpy as np
import pandas as pd
import pytest

from config import OUTPUTS_DIR
from aera.explain import FEATURE_PHRASE_MAP
from aera.features import get_feature_columns


def test_explanations_parquet_contract():
    """Verify explanations.parquet meets S8 schema and quality contracts."""
    expl_file = OUTPUTS_DIR / "explanations.parquet"
    assert expl_file.exists(), "explanations.parquet does not exist."

    df = pd.read_parquet(expl_file)
    assert len(df) == 9, f"Expected 9 stations, got {len(df)}"

    required_cols = [
        "station_id",
        "station_name",
        "predicted_class",
        "predicted_pm25",
        "driver_1_text",
        "driver_1_dir",
        "driver_2_text",
        "driver_2_dir",
        "driver_3_text",
        "driver_3_dir",
        "lower",
        "upper",
        "quality_label",
        "notes",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column in explanations: {col}"


def test_driver_count_and_raw_name_exclusion():
    """Verify that every station has 3 drivers with valid directions and zero raw column names."""
    expl_file = OUTPUTS_DIR / "explanations.parquet"
    df = pd.read_parquet(expl_file)

    raw_feature_names = set(get_feature_columns())
    valid_directions = {"raises risk", "lowers risk"}

    for _, row in df.iterrows():
        # Check directions
        assert row["driver_1_dir"] in valid_directions
        assert row["driver_2_dir"] in valid_directions
        assert row["driver_3_dir"] in valid_directions

        # Check driver texts are non-empty and mapped to human phrases
        for d in [row["driver_1_text"], row["driver_2_text"], row["driver_3_text"]]:
            assert isinstance(d, str) and len(d) > 0
            # Strict raw name exclusion
            assert d not in raw_feature_names, f"Raw feature name leaked into explanation: {d}"
            assert "_" not in d or "PM2.5" in d, f"Suspicious underscore found in plain driver text: {d}"


def test_interval_bounds_containment():
    """Verify prediction intervals are physically valid and strictly contain the point forecast."""
    expl_file = OUTPUTS_DIR / "explanations.parquet"
    df = pd.read_parquet(expl_file)

    for _, row in df.iterrows():
        lower = row["lower"]
        upper = row["upper"]
        point = row["predicted_pm25"]

        assert lower >= 0.0, f"Lower bound is negative ({lower}) at station {row['station_id']}"
        assert lower <= upper, f"Lower bound ({lower}) exceeds upper ({upper}) at station {row['station_id']}"
        assert (
            lower <= point <= upper
        ), f"Point prediction {point} not within [{lower}, {upper}] at station {row['station_id']}"


def test_station_coverage_and_quality_labels():
    """Verify all 9 stations have assigned standard quality labels (Good, Fair, Low)."""
    expl_file = OUTPUTS_DIR / "explanations.parquet"
    df = pd.read_parquet(expl_file)

    valid_labels = {"Good", "Fair", "Low"}
    assert set(df["quality_label"].unique()).issubset(valid_labels)
    assert df["station_id"].nunique() == 9
