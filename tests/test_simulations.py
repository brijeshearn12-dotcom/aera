"""Unit tests for municipal countermeasure intervention simulations."""

from __future__ import annotations

import pandas as pd
import pytest

from aera.simulations import (
    INTERVENTIONS,
    build_forward_baseline_trajectory,
    simulate_countermeasure,
)


def test_intervention_catalog_specs():
    """Verify standard interventions match required empirical reduction targets."""
    assert "sprinklers" in INTERVENTIONS
    assert INTERVENTIONS["sprinklers"]["reduction_pct"] == 12.0
    assert "Anti-Smog Water Sprinklers" in INTERVENTIONS["sprinklers"]["name"]

    assert "construction" in INTERVENTIONS
    assert INTERVENTIONS["construction"]["reduction_pct"] == 18.0
    assert "Construction Dust" in INTERVENTIONS["construction"]["name"]

    assert "freight" in INTERVENTIONS
    assert INTERVENTIONS["freight"]["reduction_pct"] == 15.0
    assert "Commercial Vehicle" in INTERVENTIONS["freight"]["name"]


def test_build_forward_baseline_trajectory():
    """Verify forward trajectory generates 24 hours of hourly projections."""
    as_of = pd.Timestamp("2026-02-28 23:30:00+05:30")
    traj = build_forward_baseline_trajectory(
        as_of=as_of,
        latest_pm25=45.0,
        pred_24h_pm25=55.0,
    )
    assert len(traj) == 24
    assert "timestamp" in traj.columns
    assert "hour" in traj.columns
    assert "baseline_pm25" in traj.columns
    assert (traj["baseline_pm25"] > 0).all()


def test_simulate_countermeasure_impact():
    """Verify simulation calculates counterfactual endpoint, averted hours, and citizens spared."""
    station_row = pd.Series({
        "predicted_pm25": 85.0,
        "predicted_class": "Unhealthy",
        "as_of": "2026-02-28 23:30:00+05:30",
    })

    sim = simulate_countermeasure(
        station_id=3409486,
        station_row=station_row,
        intervention_key="construction",
        compliance_pct=80.0,
    )

    # 18% base * 0.8 compliance = 14.4% effective reduction
    assert sim["effective_reduction_pct"] == 14.4
    assert sim["counterfactual_endpoint"] < 85.0
    assert sim["absolute_drop_pm25"] > 0.0
    assert sim["citizens_spared"] > 0
    assert sim["hours_averted"] > 0.0
    assert "trajectory_df" in sim
    assert len(sim["trajectory_df"]) == 24
    assert "counterfactual_pm25" in sim["trajectory_df"].columns
