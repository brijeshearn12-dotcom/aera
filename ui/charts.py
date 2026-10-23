"""Plotly time-series and diagnostic chart components for AERA.

Adheres strictly to project UX constraints:
- D5: 24h chart displays last 24h actual observations + single forecast point with 80% band
  (never an invented hourly curve).
- Reference lines at 60 µg/m³ (Good) and 250 µg/m³ (Severe).
- Maximum 3 charts on screen at any time.
- Honest missing-data states ("Insufficient data" annotation) without fabricating values.
- Flat Apple/Linear styling: clean grid, no gradients or glass effects.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config import GOOD_MAX, UNHEALTHY_MAX

FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, system-ui, sans-serif"


def render_station_forecast_chart(
    clean_history: Optional[pd.DataFrame],
    station_row: pd.Series,
    hours_history: int = 24,
) -> go.Figure:
    """Render the official 24h historical actuals + t+24h forecast point chart.

    Parameters
    ----------
    clean_history : pd.DataFrame, optional
        Cleaned observation timeline for the selected station.
    station_row : pd.Series
        Current station row containing predicted_pm25, lower, upper, predicted_class, as_of.
    hours_history : int
        Number of prior hours of ground observations to plot (default: 24).

    Returns
    -------
    go.Figure
        Plotly Figure object.
    """
    fig = go.Figure()

    pred_val = float(station_row.get("predicted_pm25", np.nan))
    lower = float(station_row.get("lower", np.nan))
    upper = float(station_row.get("upper", np.nan))
    as_of_str = str(station_row.get("as_of", ""))

    # Insufficient data check
    if pd.isna(pred_val) or pd.isna(lower) or pd.isna(upper):
        fig.add_annotation(
            text="Insufficient data to compute 24-hour ahead forecast band.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="#6E6E73", family=FONT_FAMILY),
        )
        fig.update_layout(template="plotly_white", height=320)
        return fig

    # Parse as_of timestamp
    try:
        as_of_dt = pd.to_datetime(as_of_str)
    except Exception:
        as_of_dt = pd.Timestamp.now(tz="Asia/Kolkata")

    forecast_dt = as_of_dt + pd.Timedelta(hours=24)

    # 1. Historical Actual Observations (Past 24 Hours)
    has_history = False
    if clean_history is not None and not clean_history.empty:
        # Filter to prior hours up to as_of
        ts_col = clean_history["timestamp"]
        hist_window = (ts_col <= as_of_dt) & (ts_col >= (as_of_dt - pd.Timedelta(hours=hours_history)))
        hist_df = clean_history[hist_window].sort_values("timestamp")

        if not hist_df.empty:
            has_history = True
            fig.add_trace(
                go.Scatter(
                    x=hist_df["timestamp"],
                    y=hist_df["pm25"],
                    mode="lines+markers",
                    name="Observed PM2.5 (Past 24h)",
                    line=dict(color="#1D1D1F", width=2.2),
                    marker=dict(size=5, color="#1D1D1F"),
                    hovertemplate="<b>Observed:</b> %{y:.1f} µg/m³<br>%{x|%b %d, %H:%M IST}<extra></extra>",
                )
            )

    # 2. Forecast Point at t+24h with 80% Conformal Prediction Band
    err_plus = [max(0.0, upper - pred_val)]
    err_minus = [max(0.0, pred_val - lower)]

    fig.add_trace(
        go.Scatter(
            x=[forecast_dt],
            y=[pred_val],
            mode="markers",
            name="Forecast at t+24h (with 80% Conformal Band)",
            marker=dict(size=12, color="#0071E3", symbol="diamond"),
            error_y=dict(
                type="data",
                symmetric=False,
                array=err_plus,
                arrayminus=err_minus,
                color="#0071E3",
                thickness=2.5,
                width=10,
            ),
            hovertemplate=(
                f"<b>24h Forecast:</b> {pred_val:.1f} µg/m³<br>"
                f"80% Interval: [{lower:.1f} – {upper:.1f}] µg/m³<br>"
                f"Target Time: %{{x|%b %d, %H:%M IST}}<extra></extra>"
            ),
        )
    )

    # Threshold horizontal reference lines
    fig.add_hline(
        y=GOOD_MAX,
        line_dash="dot",
        line_color="#34C759",
        annotation_text="Good (<=60)",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=UNHEALTHY_MAX,
        line_dash="dash",
        line_color="#FF3B30",
        annotation_text="Severe (>250)",
        annotation_position="top right",
    )

    max_y = max(upper * 1.15, 80.0)
    fig.update_layout(
        title=dict(
            text="<b>24-Hour Observed Air Quality & Forward Forecast Point</b>",
            font=dict(size=14, family=FONT_FAMILY),
        ),
        xaxis=dict(
            title="Timeline (Asia/Kolkata IST)",
            showgrid=True,
            gridcolor="#E5E5EA",
            zeroline=False,
        ),
        yaxis=dict(
            title="PM2.5 (µg/m³)",
            showgrid=True,
            gridcolor="#E5E5EA",
            zeroline=False,
            range=[0, max_y],
        ),
        template="plotly_white",
        height=320,
        margin=dict(l=45, r=30, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
    )

    return fig


def render_diurnal_heatmap(heatmap_df: pd.DataFrame) -> go.Figure:
    """Render diurnal station-by-hour median PM2.5 heatmap using single-hue blue scale."""
    fig = go.Figure()

    if heatmap_df.empty:
        fig.add_annotation(text="Insufficient heatmap data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(template="plotly_white", height=350)
        return fig

    # Pivot: index = station_name, columns = hour, values = median_pm25
    pivot = heatmap_df.pivot(index="station_name", columns="hour", values="median_pm25")
    # Clean station names
    clean_names = [s.split(",")[0] for s in pivot.index]

    fig.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=[f"{h:02d}:00" for h in pivot.columns],
            y=clean_names,
            colorscale="Blues",
            colorbar=dict(title=dict(text="PM2.5 (µg/m³)", side="right"), len=0.8),
            hovertemplate="<b>%{y}</b><br>Time: %{x} IST<br>Median: %{z:.1f} µg/m³<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(
            text="<b>Diurnal Station-by-Hour PM2.5 Profile (90-Day Baseline)</b>",
            font=dict(size=14, family=FONT_FAMILY),
        ),
        xaxis=dict(title="Hour of Day (IST)", tickangle=-45),
        yaxis=dict(title=""),
        template="plotly_white",
        height=360,
        margin=dict(l=140, r=40, t=50, b=50),
    )

    return fig
