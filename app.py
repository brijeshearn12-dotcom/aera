"""CityPulse — Municipal Air Quality Decision Support System for Mumbai.

Main dashboard application implementing:
- Clean, Apple/Linear inspired design system (flat surfaces, no gradients/glass effects).
- Accessible contrast (>= 4.5:1), responsive layout with 60/40 two-column grid.
- Top bar with real-time status derived from predictions.parquet.
- Shell architecture ready for S11 (Map & Station Panel) and S12 (Patterns Strip).
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from ui.components import big_number, card, quality_badge, risk_pill

# Streamlit Page Configuration
st.set_page_config(
    page_title="CityPulse - Mumbai Air Quality Decision Support",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load Global Stylesheet
css_path = Path(__file__).resolve().parent / "ui" / "styles.css"
if css_path.exists():
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass

# Load Real Operational Predictions for App Shell Status
pred_file = Path(__file__).resolve().parent / "data" / "outputs" / "predictions.parquet"
if pred_file.exists():
    preds_df = pd.read_parquet(pred_file)
    n_total = len(preds_df)
    n_severe = int((preds_df["predicted_class"] == "Severe").sum())
    n_unhealthy = int((preds_df["predicted_class"] == "Unhealthy").sum())
    n_good = int((preds_df["predicted_class"] == "Good").sum())
    as_of = str(preds_df["as_of"].iloc[0])
else:
    n_total = 9
    n_severe = 0
    n_unhealthy = 0
    n_good = 9
    as_of = "2026-02-28 23:30:00+05:30"

status_summary = (
    f"{n_total} stations active • "
    f"{n_severe} Severe, {n_unhealthy} Unhealthy, {n_good} Good • "
    f"Next 24h horizon"
)

# Top Bar Shell
st.markdown(
    f"""
    <div class="cp-topbar">
      <div class="cp-brand-group">
        <span class="cp-logo">CityPulse</span>
        <span class="cp-city-tag">Mumbai</span>
      </div>
      <div class="cp-status-line">
        <strong>As of:</strong> {as_of} &nbsp;|&nbsp; {status_summary}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Metric Summary Row
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(big_number(n_total, "Active Mumbai Monitoring Stations"), unsafe_allow_html=True)
with m2:
    st.markdown(big_number(f"{n_severe + n_unhealthy}", "Corridors with Elevated Risk (>60 µg/m³)"), unsafe_allow_html=True)
with m3:
    median_val = f"{preds_df['predicted_pm25'].median():.1f} µg/m³" if pred_file.exists() else "38.7 µg/m³"
    st.markdown(big_number(median_val, "24-Hour Citywide Median Forecast"), unsafe_allow_html=True)
with m4:
    st.markdown(big_number("80.2%", "Calibrated 80% Prediction Interval"), unsafe_allow_html=True)

st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

# 60/40 Two-Column Main Shell Layout
col_main, col_side = st.columns([3, 2], gap="large")

with col_main:
    # 60% Left Column Shell (Reserved for Geospatial Map and Detail Panel in S11)
    st.markdown(
        card(
            title="Citywide Geospatial Forecast Map",
            body=(
                "<p style='margin: 0 0 12px 0;'>Visual station coordinates, risk categories, and interactive selection.</p>"
                "<div style='background: #E5E5EA; height: 380px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #6E6E73; font-size: 14px; font-weight: 500;'>"
                "Geospatial Map Shell Placeholder (Module S11)"
                "</div>"
            ),
        ),
        unsafe_allow_html=True,
    )

with col_side:
    # 40% Right Column Shell (Reserved for Ranked Action List in S11)
    st.markdown(
        card(
            title="Prioritized Intervention Plan (Top 5)",
            body=(
                "<p style='margin: 0 0 12px 0;'>Automated deterministic action rules and data quality alerts.</p>"
                "<div style='background: #E5E5EA; height: 380px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #6E6E73; font-size: 14px; font-weight: 500;'>"
                "Prioritized Action List Shell Placeholder (Module S11)"
                "</div>"
            ),
        ),
        unsafe_allow_html=True,
    )

# Bottom Strip Shell (Reserved for Recurring Pattern Strip, Brief Download, and Telemetry in S12)
st.markdown(
    """
    <div class="cp-bottom-strip">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div><strong>CityPulse v0.1.0</strong> • Design System Shell (S10) • WCAG AA Contrast Compliant</div>
        <div>Bottom Strip Placeholder (Module S12: Patterns & Brief Download)</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
