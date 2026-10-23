"""Recommendation and prioritization engine for AERA intervention actions.

Ranks monitoring stations using an explicit risk formula:
    risk_score = (p_unhealthy + p_severe) * severity_weight

Severity weights:
- Severe predicted class: 2.0
- Unhealthy predicted class: 1.5
- Good predicted class: 1.0 + (p_unhealthy * 0.5) + (p_severe * 1.0)

Low telemetry quality (<70% valid hours) is explicitly flagged as an operational warning;
scores are NEVER secretly inflated or discounted based on data quality.

Deterministic rule-based actions assign targeted, actionable city interventions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import OUTPUTS_DIR

logger = logging.getLogger(__name__)

TIME_WINDOW_DEFAULT = "Next 24 hours (diurnal peak 08:00 IST)"


def determine_action(
    pred_class: str,
    driver_texts: List[str],
    station_name: str = "",
) -> str:
    """Determine deterministic rule-based intervention action from risk and drivers.

    Rules:
    1. Severe:
       Issue health advisory and suspend nearby dust-generating work.
    2. Unhealthy + low wind:
       Deploy water sprinklers/mist cannons and inspect construction sites.
    3. Unhealthy + persistent pollution driver:
       Inspect local point sources and industrial emissions; traffic management.
    4. Other Unhealthy:
       Increase mechanized road cleaning and monitor hourly sensor trends.
    5. Good:
       Normal operations; no intervention needed.
    """
    if pred_class == "Severe":
        return "Issue health advisory; suspend nearby dust-generating construction and industrial operations."

    if pred_class == "Unhealthy":
        # Check drivers for calm wind or ventilation stagnation
        is_calm_wind = any("wind" in d.lower() or "ventilation" in d.lower() for d in driver_texts)
        # Check drivers for persistent historical pollution baseline
        is_persistent = any(
            "baseline" in d.lower() or "yesterday" in d.lower() or "24-hour" in d.lower()
            for d in driver_texts
        )

        if is_calm_wind:
            return "Deploy water mist cannons / sprinklers; inspect active construction sites for dust control."
        elif is_persistent:
            return "Inspect local pollution point sources and industrial emissions; enforce strict traffic diversion."
        else:
            return "Increase mechanized road cleaning and intensify hourly sensor monitoring."

    # Good class
    return "Normal operations; standard air quality maintenance with no intervention required."


def calculate_severity_weight(pred_class: str, p_unhealthy: float, p_severe: float) -> float:
    """Calculate explicit severity weight giving transparent priority to severe risk tiers."""
    if pred_class == "Severe":
        return 2.0
    elif pred_class == "Unhealthy":
        return 1.5
    else:
        # Base multiplier for Good class scaled by residual risk probability
        return float(np.round(1.0 + (p_unhealthy * 0.5) + (p_severe * 1.0), 4))


def rank_stations(
    pred_df: pd.DataFrame,
    expl_df: pd.DataFrame,
    top_n: int = 5,
) -> pd.DataFrame:
    """Rank stations by elevated pollution risk score and assign deterministic actions.

    Parameters
    ----------
    pred_df : pd.DataFrame
        Predictions table containing station_id, predicted_class, p_good, p_unhealthy, p_severe, predicted_pm25.
    expl_df : pd.DataFrame
        Explanations table containing station_id, driver texts, lower, upper, quality_label.
    top_n : int
        Number of top ranked stations to return (default: 5).

    Returns
    -------
    pd.DataFrame
        Ranked station actions DataFrame.
    """
    # Merge predictions with explanations
    merged = pd.merge(
        pred_df,
        expl_df[
            [
                "station_id",
                "driver_1_text",
                "driver_1_dir",
                "driver_2_text",
                "driver_2_dir",
                "driver_3_text",
                "driver_3_dir",
                "lower",
                "upper",
                "quality_label",
            ]
        ],
        on="station_id",
        how="inner",
        suffixes=("", "_expl"),
    )

    rows = []
    for _, row in merged.iterrows():
        st_id = int(row["station_id"])
        st_name = str(row["station_name"])
        p_unhealthy = float(row["p_unhealthy"])
        p_severe = float(row["p_severe"])
        pred_cls = str(row["predicted_class"])
        pred_pm25 = float(row["predicted_pm25"])
        q_label = str(row["quality_label"])

        # Explicit severity weight
        sev_weight = calculate_severity_weight(pred_cls, p_unhealthy, p_severe)
        base_risk_prob = p_unhealthy + p_severe
        risk_score = float(np.round(base_risk_prob * sev_weight, 4))

        # Warning logic: Low quality is surfaced as an explicit operational alert, never hidden
        warning = ""
        if q_label == "Low":
            warning = "[ALERT] Low historical telemetry coverage (<70%)"

        # Deterministic action
        drivers = [
            str(row["driver_1_text"]),
            str(row["driver_2_text"]),
            str(row["driver_3_text"]),
        ]
        action = determine_action(pred_cls, drivers, st_name)

        rows.append(
            {
                "station_id": st_id,
                "station_name": st_name,
                "predicted_class": pred_cls,
                "predicted_pm25": pred_pm25,
                "p_unhealthy": p_unhealthy,
                "p_severe": p_severe,
                "severity_weight": sev_weight,
                "risk_score": risk_score,
                "time_window": TIME_WINDOW_DEFAULT,
                "action": action,
                "warning": warning,
                "quality_label": q_label,
                "lower": float(row["lower"]),
                "upper": float(row["upper"]),
                "primary_driver": f"{row['driver_1_text']} ({row['driver_1_dir']})",
            }
        )

    df_ranked = pd.DataFrame(rows)
    # Sort descending by risk_score, break ties by predicted_pm25
    df_ranked = (
        df_ranked.sort_values(by=["risk_score", "predicted_pm25"], ascending=[False, False])
        .reset_index(drop=True)
    )
    df_ranked["rank"] = df_ranked.index + 1

    # Return top N stations
    top_stations = df_ranked.head(top_n).copy()
    return top_stations


def main() -> None:
    """Execute recommendation ranking and save ranked outputs."""
    print("=" * 80)
    print("AERA Step 9: Recommendation & Intervention Prioritization")
    print("=" * 80)

    pred_path = OUTPUTS_DIR / "predictions.parquet"
    expl_path = OUTPUTS_DIR / "explanations.parquet"

    if not pred_path.exists() or not expl_path.exists():
        print(f"BLOCKER: Inputs missing ({pred_path} or {expl_path}).")
        return

    pred_df = pd.read_parquet(pred_path)
    expl_df = pd.read_parquet(expl_path)

    ranked_df = rank_stations(pred_df, expl_df, top_n=5)
    out_path = OUTPUTS_DIR / "ranked_stations.parquet"
    ranked_df.to_parquet(out_path, index=False)
    print(f"[Saved] Ranked stations dataset: {out_path} ({len(ranked_df)} stations)")

    print("\n" + "=" * 80)
    print("TOP-5 ACTIONABLE INTERVENTION PRIORITIES (NEXT 24 HOURS)")
    print("=" * 80)
    for _, row in ranked_df.iterrows():
        warn_str = f" | {row['warning']}" if row["warning"] else ""
        print(f"Rank #{row['rank']}: {row['station_name']}")
        print(f"  Risk Tier: {row['predicted_class']} | Score: {row['risk_score']} (Weight: {row['severity_weight']})")
        print(f"  Forecast : {row['predicted_pm25']} ug/m3 [{row['lower']} to {row['upper']}] | Quality: {row['quality_label']}{warn_str}")
        print(f"  Window   : {row['time_window']}")
        print(f"  Action   : {row['action']}")
        print(f"  Driver   : {row['primary_driver']}\n")
    print("=" * 80)


if __name__ == "__main__":
    main()
