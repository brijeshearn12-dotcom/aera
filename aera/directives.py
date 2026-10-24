"""Official BMC Ward Action Directive executive order memo generator for AERA.

Produces high-impact, legally authoritative municipal executive memorandums
for ward commissioners under the Mumbai Municipal Corporation Act, 1888.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

from aera.vulnerability import get_ward_demographics


def generate_bmc_action_directive(
    station_id: int,
    station_row: pd.Series,
    simulation_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate official BMC Executive Action Directive memorandum.

    Parameters
    ----------
    station_id : int
        Station identifier.
    station_row : pd.Series
        Current station row.
    simulation_result : Dict[str, Any], optional
        Active countermeasure simulation results if simulated.

    Returns
    -------
    Dict[str, Any]
        Structured memo with title, memo_text, plain_text, metadata.
    """
    ward_info = get_ward_demographics(station_id)
    ward_code = str(ward_info.get("ward_code", "K/East"))
    ward_name = str(ward_info.get("ward_name", "Andheri"))
    officer_title = str(ward_info.get("officer_title", f"Ward Officer (Ward {ward_code} - {ward_name})"))
    arterial = str(ward_info.get("primary_arterial", "Western Express Highway (WEH)"))
    dust_zones = ward_info.get("high_dust_zones", ["Active Infrastructure Corridor"])

    pred_val = float(station_row.get("predicted_pm25", 50.0))
    pred_cls = str(station_row.get("predicted_class", "Unhealthy"))
    as_of = str(station_row.get("as_of", "2026-02-28 23:30:00 IST"))

    # Alert Level & Window
    if pred_cls == "Severe" or pred_val >= 90.0:
        alert_level = "CRITICAL CONCENTRATION BREACH EXPECTED (05:00 - 09:00 IST)"
    elif pred_cls == "Unhealthy" or pred_val >= 45.0:
        alert_level = "SEVERE CONCENTRATION BREACH EXPECTED (05:00 - 09:00 IST)"
    else:
        alert_level = "ELEVATED PREVENTIVE CAUTION ADVISORY (05:00 - 09:00 IST)"

    # Atmospheric Drivers
    d1 = str(station_row.get("driver_1_text", "Nocturnal Temperature Inversion"))
    d2 = str(station_row.get("driver_2_text", "Road Dust Resuspension"))
    primary_driver = f"{d1} + {d2}"

    # Generate tailored ward-specific mandates
    zone_str = dust_zones[0] if dust_zones else "High-density worksites"
    mandate_1 = f"Deploy 3 mechanical sweepers & mist cannons along {arterial} by 04:00 IST."
    mandate_2 = f"Issue temporary halt to concrete batching plants & excavation within 2km radius of {zone_str}."
    
    if "Western" in arterial or "WEH" in arterial or "Link" in arterial:
        mandate_3 = "Divert heavy commercial diesel freight via Western Coastal Bypass / SV Road freight window."
    elif "Eastern" in arterial or "EEH" in arterial or "Freeway" in arterial or "Mankhurd" in arterial:
        mandate_3 = "Divert heavy diesel freight via Eastern Freeway corridor and restrict peak cargo entry."
    else:
        mandate_3 = "Enforce heavy commercial vehicle peak diversion onto designated ring bypass corridors."

    mandate_4 = f"Place Ward {ward_code} Health Posts on respiratory triage alert; report compliance log by 09:30 IST."

    timestamp_str = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    order_ref = f"BMC/ENV/AQM-2026/W-{ward_code.replace('/', '')}-DIR-{station_id % 1000:03d}"

    memo_lines = [
        "================================================================================",
        "MEMORANDUM | MUNICIPAL CORPORATION OF GREATER MUMBAI (BMC)",
        "OFFICE OF THE MUNICIPAL COMMISSIONER & ENVIRONMENT SECRETARIAT",
        "--------------------------------------------------------------------------------",
        f"CIRCULAR REF: {order_ref}",
        f"DATE/TIME   : {timestamp_str} (Effective Immediately)",
        f"TO          : {officer_title}",
        f"MONITORING  : {station_row.get('station_name', 'Mumbai Station')} (Station #{station_id})",
        f"FORECAST    : {pred_val:.1f} µg/m³ ({pred_cls}) | 80% CI: [{station_row.get('lower', 0.0):.1f} – {station_row.get('upper', 0.0):.1f}] µg/m³",
        "--------------------------------------------------------------------------------",
        f"ALERT LEVEL   : {alert_level}",
        f"PRIMARY DRIVER: {primary_driver}",
        "--------------------------------------------------------------------------------",
        "MANDATED DIRECTIVES (UNDER SECTIONS 368 & 434, MMC ACT, 1888):",
        f"  1. {mandate_1}",
        f"  2. {mandate_2}",
        f"  3. {mandate_3}",
        f"  4. {mandate_4}",
    ]

    if simulation_result:
        eff_drop = simulation_result.get("absolute_drop_pm25", 0.0)
        spared = simulation_result.get("citizens_spared", 0)
        hrs = simulation_result.get("hours_averted", 0.0)
        interv_name = simulation_result.get("intervention", {}).get("name", "Countermeasure")
        memo_lines.extend([
            "--------------------------------------------------------------------------------",
            "PREDICTED SIMULATION IMPACT OF MANDATED COUNTERMEASURES:",
            f"  • Selected Protocol : {interv_name}",
            f"  • Expected Abatement: -{eff_drop:.1f} µg/m³ PM2.5 at target receptor",
            f"  • Exposure Averted  : ~{spared:,} Ward Residents Spared Severe Exposure",
            f"  • Breach Averted    : {hrs:.1f} Hours of Peak Severe Stagnation Prevented",
        ])

    memo_lines.extend([
        "--------------------------------------------------------------------------------",
        "ENFORCEMENT AUTHORITY: BMC Air Quality Management Cell & Mumbai Traffic Police",
        "COMPLIANCE DISPATCH  : Mandatory telemetry compliance report due within 4 hours.",
        "================================================================================",
    ])

    directive_text = "\n".join(memo_lines)

    return {
        "order_ref": order_ref,
        "ward_code": ward_code,
        "ward_name": ward_name,
        "officer_title": officer_title,
        "alert_level": alert_level,
        "primary_driver": primary_driver,
        "directives": [mandate_1, mandate_2, mandate_3, mandate_4],
        "full_text": directive_text,
    }
