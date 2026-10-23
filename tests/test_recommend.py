"""Unit tests for municipal recommendation rules, ranking math, and briefing outputs."""

import pandas as pd
import pytest

from config import OUTPUTS_DIR
from aera.brief import generate_brief
from aera.recommend import (
    calculate_severity_weight,
    determine_action,
    rank_stations,
)


def test_action_rules_all_conditions():
    """Verify deterministic rules assign expected actions across all 5 standard tiers."""
    # 1. Severe
    act_sev = determine_action("Severe", ["Current PM2.5 level", "Surface wind speed ventilation"])
    assert "health advisory" in act_sev.lower()
    assert "suspend" in act_sev.lower()

    # 2. Unhealthy + low wind
    act_unh_wind = determine_action(
        "Unhealthy", ["Surface wind speed ventilation", "Projected 24-hour wind ventilation"]
    )
    assert "sprinklers" in act_unh_wind.lower() or "mist cannons" in act_unh_wind.lower()

    # 3. Unhealthy + persistent pollution driver
    act_unh_persist = determine_action(
        "Unhealthy", ["24-hour baseline PM2.5 average", "Same-time yesterday PM2.5 concentration"]
    )
    assert "point sources" in act_unh_persist.lower() or "industrial" in act_unh_persist.lower()

    # 4. Other Unhealthy
    act_unh_other = determine_action(
        "Unhealthy", ["Ambient temperature conditions", "Relative humidity"]
    )
    assert "road cleaning" in act_unh_other.lower() or "sweeping" in act_unh_other.lower()

    # 5. Good
    act_good = determine_action("Good", ["Surface wind speed ventilation"])
    assert "normal operations" in act_good.lower()


def test_severity_weight_calculation():
    """Verify explicit severity weights scale predictably across classes."""
    w_sev = calculate_severity_weight("Severe", 0.1, 0.8)
    assert w_sev == 2.0

    w_unh = calculate_severity_weight("Unhealthy", 0.7, 0.1)
    assert w_unh == 1.5

    w_good = calculate_severity_weight("Good", 0.2, 0.05)
    assert w_good >= 1.0 and w_good < 1.5


def test_rank_stations_top_five_truncation():
    """Verify ranking orders by risk_score and returns top 5 stations."""
    pred_path = OUTPUTS_DIR / "predictions.parquet"
    expl_path = OUTPUTS_DIR / "explanations.parquet"

    assert pred_path.exists() and expl_path.exists()
    pred_df = pd.read_parquet(pred_path)
    expl_df = pd.read_parquet(expl_path)

    ranked = rank_stations(pred_df, expl_df, top_n=5)
    assert len(ranked) == 5

    # Check monotonic decreasing risk_score
    scores = ranked["risk_score"].tolist()
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]


def test_low_quality_surfaced_as_warning():
    """Verify that Low data quality surfaces an explicit alert without adjusting scores."""
    pred_path = OUTPUTS_DIR / "predictions.parquet"
    expl_path = OUTPUTS_DIR / "explanations.parquet"

    pred_df = pd.read_parquet(pred_path)
    expl_df = pd.read_parquet(expl_path)

    ranked = rank_stations(pred_df, expl_df, top_n=9)
    low_q_rows = ranked[ranked["quality_label"] == "Low"]

    for _, row in low_q_rows.iterrows():
        assert len(row["warning"]) > 0
        assert "Low historical telemetry" in row["warning"]
        # Score calculation must follow the exact formula: (p_unhealthy + p_severe) * weight
        expected_score = round((row["p_unhealthy"] + row["p_severe"]) * row["severity_weight"], 4)
        assert abs(row["risk_score"] - expected_score) < 1e-4


def test_brief_html_generation_and_contract():
    """Verify brief.html contains all required governance and operational sections."""
    brief_file = OUTPUTS_DIR / "brief.html"
    generate_brief(output_path=brief_file)

    assert brief_file.exists()
    html_content = brief_file.read_text(encoding="utf-8")

    # Check key sections and terms
    assert "AERA Briefing" in html_content
    assert "Top-5 Prioritized Station Interventions" in html_content
    assert "Recurring Operational Pollution Patterns" in html_content
    assert "Predictive Model vs. Baseline Evaluation" in html_content
    assert "Governance, Provenance & Known Limitations" in html_content
    assert "Persistence Benchmark" in html_content
    assert "LightGBM" in html_content
