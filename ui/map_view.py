"""Geospatial Folium map rendering module for CityPulse monitoring stations.

Features:
- Folium map centred on Mumbai with CartoDB Positron light tile styling.
- Circle markers for each monitoring station with risk-tier color coding:
  * Good (<=60 µg/m³): Green (#34C759)
  * Unhealthy (>60–250 µg/m³): Amber (#FF9500)
  * Severe (>250 µg/m³): Red (#FF3B30)
- Text label in every tooltip and popup (never colour alone).
- Visual highlight for selected station.
- Interactive click integration with Streamlit session state and selectbox fallback.
"""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

import folium
import pandas as pd

MUMBAI_CENTER = [19.0760, 72.8777]
DEFAULT_ZOOM = 11

RISK_COLOR_MAP = {
    "Good": "#34C759",
    "Unhealthy": "#FF9500",
    "Severe": "#FF3B30",
}


def create_station_map(
    stations_df: pd.DataFrame,
    selected_station_id: Optional[int] = None,
) -> folium.Map:
    """Build an interactive Folium map with station circle markers.

    Parameters
    ----------
    stations_df : pd.DataFrame
        DataFrame containing station_id, station_name, lat, lon, predicted_class,
        predicted_pm25, lower, upper, quality_label.
    selected_station_id : int, optional
        ID of currently selected station to highlight with an accent ring.

    Returns
    -------
    folium.Map
        Configured Folium map object.
    """
    m = folium.Map(
        location=MUMBAI_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
    )

    for _, row in stations_df.iterrows():
        lat = row.get("lat")
        lon = row.get("lon")
        if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
            continue
        lat = float(lat)
        lon = float(lon)
        st_id = int(row.get("station_id", 0))
        st_name = str(row.get("station_name", "Station"))
        pred_cls = str(row.get("predicted_class", "Good"))
        pred_val = float(row.get("predicted_pm25", 0.0))
        lower = float(row.get("lower", 0.0))
        upper = float(row.get("upper", 0.0))
        q_label = str(row.get("quality_label", "Fair"))

        marker_color = RISK_COLOR_MAP.get(pred_cls, "#34C759")
        is_selected = (selected_station_id is not None) and (st_id == int(selected_station_id))

        # Tooltip text (always includes station name and text risk class)
        tooltip_html = (
            f"<div style='font-family: -apple-system, sans-serif; font-size: 12px; padding: 2px;'>"
            f"<strong>{html.escape(st_name.split(',')[0])}</strong><br>"
            f"Forecast: <b>{pred_val:.1f} µg/m³</b> ({pred_cls})<br>"
            f"Quality: {q_label}"
            f"</div>"
        )

        # Popup card with rich station details
        popup_html = (
            f"<div style='font-family: -apple-system, sans-serif; font-size: 12px; width: 220px; line-height: 1.4;'>"
            f"<div style='font-weight: 700; font-size: 13px; margin-bottom: 4px;'>{html.escape(st_name.split(',')[0])}</div>"
            f"<div style='color: #6E6E73; font-size: 10px; margin-bottom: 6px;'>Station ID: {st_id}</div>"
            f"<div style='margin-bottom: 4px;'>"
            f"Forecast PM2.5: <strong>{pred_val:.1f} µg/m³</strong> "
            f"<span style='background: {marker_color}22; color: {marker_color}; padding: 1px 6px; border-radius: 4px; font-weight: 600; font-size: 11px;'>{pred_cls}</span>"
            f"</div>"
            f"<div style='color: #6E6E73; font-size: 11px; margin-bottom: 4px;'>80% Band: [{lower:.1f} – {upper:.1f}] µg/m³</div>"
            f"<div style='color: #6E6E73; font-size: 11px;'>Telemetry: <strong>{q_label}</strong></div>"
            f"</div>"
        )

        # Selected marker styling vs default marker
        radius = 13 if is_selected else 9
        border_color = "#0071E3" if is_selected else "#FFFFFF"
        weight = 3 if is_selected else 2

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color=border_color,
            weight=weight,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.9,
            tooltip=folium.Tooltip(tooltip_html, sticky=True),
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(m)

    return m
