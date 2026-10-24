"""Unit tests for BMC Ward Action Directive memo generator."""

from __future__ import annotations

import pandas as pd
import pytest

from aera.directives import generate_bmc_action_directive
from aera.simulations import simulate_countermeasure


def test_generate_bmc_action_directive():
    """Verify generated directive contains required executive memorandum fields and mandates."""
    station_row = pd.Series({
        "station_name": "Kherwadi_Bandra East, Mumbai - MPCB",
        "predicted_pm25": 92.4,
        "predicted_class": "Unhealthy",
        "lower": 78.0,
        "upper": 112.5,
        "driver_1_text": "Nocturnal Temperature Inversion",
        "driver_2_text": "Road Dust Resuspension",
        "as_of": "2026-02-28 23:30:00 IST",
    })

    directive = generate_bmc_action_directive(
        station_id=3409486,
        station_row=station_row,
    )

    full_text = directive["full_text"]

    # Verify official memorandum header
    assert "MEMORANDUM | MUNICIPAL CORPORATION OF GREATER MUMBAI (BMC)" in full_text
    assert "Ward H/East" in directive["ward_code"] or "H/East" in full_text
    assert "ALERT LEVEL" in full_text
    assert "PRIMARY DRIVER" in full_text
    assert "Nocturnal Temperature Inversion + Road Dust Resuspension" in full_text

    # Verify mandated directives under MMC Act
    assert "MMC ACT, 1888" in full_text
    assert len(directive["directives"]) >= 3
    assert any("mechanical sweepers" in d.lower() or "mist cannons" in d.lower() for d in directive["directives"])
    assert any("concrete batching" in d.lower() or "halt" in d.lower() for d in directive["directives"])
    assert any("freight" in d.lower() or "divert" in d.lower() for d in directive["directives"])


def test_directive_with_simulation_context():
    """Verify directive includes countermeasure simulation impact when simulation active."""
    station_row = pd.Series({
        "station_name": "Mindspace-Malad West, Mumbai - MPCB",
        "predicted_pm25": 75.0,
        "predicted_class": "Unhealthy",
        "as_of": "2026-02-28 23:30:00 IST",
    })

    sim = simulate_countermeasure(
        station_id=3409479,
        station_row=station_row,
        intervention_key="sprinklers",
        compliance_pct=90.0,
    )

    directive = generate_bmc_action_directive(
        station_id=3409479,
        station_row=station_row,
        simulation_result=sim,
    )

    full_text = directive["full_text"]
    assert "PREDICTED SIMULATION IMPACT" in full_text
    assert "Citizens Spared" in full_text or "Residents Spared" in full_text
    assert "Hours of Peak" in full_text or "Averted" in full_text
