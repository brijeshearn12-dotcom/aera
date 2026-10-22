"""Streamlit entry point for the CityPulse pollution-risk dashboard."""

from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="CityPulse - Mumbai PM2.5 Risk",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load global stylesheet safely
css_path = Path(__file__).resolve().parent / "ui" / "styles.css"
if css_path.exists():
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass

# Header section
st.title("CityPulse")
st.caption("Version v0.1.0")
st.subheader("PM2.5 risk for Mumbai, next 24 hours")

# Prominent placeholder warning
st.warning(
    "⚠️ **Placeholder, not real data** — The values below are mock, illustrative figures "
    "used strictly for deployment readiness testing. Air quality feeds, data cleaning, and "
    "forecasting models are scheduled for subsequent implementation steps.",
    icon="⚠️",
)

# Illustrative station table
st.markdown("### Illustrative Monitoring Stations")
st.caption("Placeholder, not real data")

placeholder_data = pd.DataFrame(
    [
        {"Station Name": "Bandra (Illustrative)", "Illustrative PM2.5 (µg/m³)": 45, "Risk Category": "Good"},
        {"Station Name": "Colaba (Illustrative)", "Illustrative PM2.5 (µg/m³)": 82, "Risk Category": "Unhealthy"},
        {"Station Name": "Andheri (Illustrative)", "Illustrative PM2.5 (µg/m³)": 135, "Risk Category": "Unhealthy"},
        {"Station Name": "Kurla (Illustrative)", "Illustrative PM2.5 (µg/m³)": 270, "Risk Category": "Severe"},
        {"Station Name": "Worli (Illustrative)", "Illustrative PM2.5 (µg/m³)": 52, "Risk Category": "Good"},
    ]
)

st.dataframe(
    placeholder_data,
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.markdown(
    "<small style='color: #6E6E73;'>CityPulse v0.1.0 • Mumbai Decision Support • Early Deployment Smoke Test (S2)</small>",
    unsafe_allow_html=True,
)
