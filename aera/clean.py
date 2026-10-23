"""Data cleaning, validation, and quality flagging module for AERA.

Applies QA/QC validation to PM2.5 measurements:
- Reindexes each station to a regular hourly timeline in Asia/Kolkata timezone.
- Identifies and flags impossible values (<0 or >1000 µg/m³), setting them to missing.
- Identifies and flags stuck sensor runs (>=6 consecutive identical values), setting them to missing.
- Identifies transmission gaps and interpolates 1-3 hour gaps using time interpolation (pm25_filled=True).
- Leaves gaps >3 hours missing.
- Performs an exact 1-to-1 hourly join with matching meteorological variables.
- Calculates 30-day valid-hour quality summaries (Good >=90%, Fair 70-90%, Low <70%).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config import (
    GAP_FILL_LIMIT_HOURS,
    OUTPUTS_DIR,
    PROCESSED_DATA_DIR,
    STUCK_VALUE_RUN_LENGTH,
)

logger = logging.getLogger(__name__)


def _normalize_timestamp_series(s: pd.Series) -> pd.Series:
    """Ensure timestamp series is datetime64 with Asia/Kolkata timezone."""
    dt_s = pd.to_datetime(s)
    if dt_s.dt.tz is None:
        return dt_s.dt.tz_localize("Asia/Kolkata")
    return dt_s.dt.tz_convert("Asia/Kolkata")


def clean_station(df_s: pd.DataFrame, hourly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Clean and quality-flag observations for a single monitoring station.

    Order of operations:
    1. Deduplicate by timestamp if duplicate observations exist.
    2. Flag impossible values (pm25 < 0 or > 1000) using flag_impossible.
    3. Flag stuck runs (>=6 consecutive identical non-null values) using flag_stuck.
    4. Replace impossible and stuck values with missing (NaN).
    5. Reindex to full regular hourly timeline.
    6. Record missing-gap flags (flag_gap=True for unrecorded slots).
    7. Interpolate transmission gaps of 1-3 consecutive hours using time interpolation.
       Mark filled slots with pm25_filled=True. Gaps >3 hours remain missing.
    """
    df_s = df_s.copy()

    # Determine timestamp column
    if "timestamp" in df_s.columns:
        ts_col = "timestamp"
    elif "timestamp_ist" in df_s.columns:
        ts_col = "timestamp_ist"
    elif "timestamp_utc" in df_s.columns:
        ts_col = "timestamp_utc"
    else:
        raise ValueError("No recognizable timestamp column found in PM2.5 dataframe.")

    df_s["timestamp"] = _normalize_timestamp_series(df_s[ts_col])
    # Deduplicate on timestamp
    df_s = df_s.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

    st_id = df_s["station_id"].iloc[0] if "station_id" in df_s.columns else 0
    st_name = df_s["station_name"].iloc[0] if "station_name" in df_s.columns else f"Station {st_id}"
    lat = float(df_s["lat"].iloc[0]) if "lat" in df_s.columns else np.nan
    lon = float(df_s["lon"].iloc[0]) if "lon" in df_s.columns else np.nan

    # 1. Flag impossible values (<0 or >1000 µg/m³)
    flag_impossible = (df_s["pm25"] < 0) | (df_s["pm25"] > 1000)
    df_s["flag_impossible"] = flag_impossible

    # 2. Flag stuck sensor runs (>= 6 consecutive identical valid values)
    pm = df_s["pm25"]
    not_na = pm.notna() & (~flag_impossible)
    diff = (pm != pm.shift()) | (~not_na)
    run_id = diff.cumsum()
    run_len = not_na.groupby(run_id).transform(lambda x: len(x) if x.iloc[0] else 0)
    flag_stuck = not_na & (run_len >= STUCK_VALUE_RUN_LENGTH)
    df_s["flag_stuck"] = flag_stuck

    # Replace impossible and stuck values with NaN (removed)
    df_s.loc[flag_impossible | flag_stuck, "pm25"] = np.nan

    # 3. Reindex to full regular hourly timeline
    df_reindexed = df_s.set_index("timestamp").reindex(hourly_index)
    df_reindexed["station_id"] = st_id
    df_reindexed["station_name"] = st_name
    df_reindexed["lat"] = lat
    df_reindexed["lon"] = lon

    # Restore boolean flags
    df_reindexed["flag_impossible"] = (df_reindexed["flag_impossible"] == True)
    df_reindexed["flag_stuck"] = (df_reindexed["flag_stuck"] == True)

    # flag_gap is True for genuine unrecorded slots
    df_reindexed["flag_gap"] = (
        df_reindexed["pm25"].isna() & (~df_reindexed["flag_impossible"]) & (~df_reindexed["flag_stuck"])
    )

    # 4. Interpolate gaps of 1-3 consecutive hours
    is_na = df_reindexed["pm25"].isna()
    gap_group = (~is_na).cumsum()
    gap_size = is_na.groupby(gap_group).transform("sum")

    # Time interpolation
    pm_interp = df_reindexed["pm25"].interpolate(method="time")

    can_fill = (
        is_na
        & (gap_size >= 1)
        & (gap_size <= GAP_FILL_LIMIT_HOURS)
        & df_reindexed["pm25"].ffill().notna()
        & df_reindexed["pm25"].bfill().notna()
        & df_reindexed["flag_gap"]  # Only fill transmission gaps, not bad readings
    )

    df_reindexed["pm25_filled"] = can_fill
    df_reindexed.loc[can_fill, "pm25"] = pm_interp[can_fill].round(2)

    df_out = df_reindexed.reset_index().rename(columns={"index": "timestamp"})
    return df_out


def clean(
    df_pm25: pd.DataFrame,
    df_weather: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Clean PM2.5 observations, apply QA/QC flags, and join weather variables.

    Parameters
    ----------
    df_pm25 : pd.DataFrame
        Raw or processed station PM2.5 observations.
    df_weather : Optional[pd.DataFrame]
        Matching weather observations.

    Returns
    -------
    pd.DataFrame
        Cleaned dataset matching schema:
        `['timestamp', 'station_id', 'station_name', 'lat', 'lon', 'pm25',
          'pm25_filled', 'flag_gap', 'flag_stuck', 'flag_impossible',
          (weather columns)]`
    """
    if df_pm25.empty:
        raise ValueError("Input PM2.5 dataframe is empty.")

    # Determine timestamp column and normalize to Asia/Kolkata
    if "timestamp" in df_pm25.columns:
        ts_col = "timestamp"
    elif "timestamp_ist" in df_pm25.columns:
        ts_col = "timestamp_ist"
    elif "timestamp_utc" in df_pm25.columns:
        ts_col = "timestamp_utc"
    else:
        raise ValueError("PM2.5 dataframe must contain 'timestamp', 'timestamp_ist', or 'timestamp_utc'.")

    df_pm25_norm = df_pm25.copy()
    df_pm25_norm["timestamp"] = _normalize_timestamp_series(df_pm25_norm[ts_col])

    # Establish full regular hourly index across the entire dataset span
    global_start = df_pm25_norm["timestamp"].min()
    global_end = df_pm25_norm["timestamp"].max()
    hourly_index = pd.date_range(start=global_start, end=global_end, freq="1h")

    # Clean per station
    cleaned_stations = []
    for _, st_df in df_pm25_norm.groupby("station_id"):
        st_clean = clean_station(st_df, hourly_index)
        cleaned_stations.append(st_clean)

    cleaned_df = pd.concat(cleaned_stations, ignore_index=True)

    # Join weather if provided
    weather_cols = [
        "temperature",
        "relative_humidity",
        "rainfall",
        "wind_speed",
        "wind_direction",
        "boundary_layer_height",
    ]

    if df_weather is not None and not df_weather.empty:
        w_df = df_weather.copy()
        if "timestamp" in w_df.columns:
            w_ts_col = "timestamp"
        elif "timestamp_ist" in w_df.columns:
            w_ts_col = "timestamp_ist"
        elif "timestamp_utc" in w_df.columns:
            w_ts_col = "timestamp_utc"
        else:
            w_ts_col = w_df.columns[0]

        w_df["timestamp"] = _normalize_timestamp_series(w_df[w_ts_col])
        avail_w_cols = [c for c in weather_cols if c in w_df.columns]
        w_subset = w_df[["timestamp"] + avail_w_cols].drop_duplicates(subset=["timestamp"])

        merged = pd.merge(cleaned_df, w_subset, on="timestamp", how="left")
        if len(merged) != len(cleaned_df):
            logger.warning("Weather merge produced unexpected row count; deduplicating.")
            merged = merged.drop_duplicates(subset=["station_id", "timestamp"])
        cleaned_df = merged
    else:
        # If no weather provided, populate weather columns as NaN
        for col in weather_cols:
            cleaned_df[col] = np.nan

    out_cols = [
        "timestamp",
        "station_id",
        "station_name",
        "lat",
        "lon",
        "pm25",
        "pm25_filled",
        "flag_gap",
        "flag_stuck",
        "flag_impossible",
    ] + [c for c in weather_cols if c in cleaned_df.columns]

    return cleaned_df[out_cols].sort_values(["station_id", "timestamp"]).reset_index(drop=True)


def compute_quality_summary(df_cleaned: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """Compute per-station valid-hour data quality over the latest N days.

    Quality standards:
    - Good: >= 90%
    - Fair: >= 70% and < 90%
    - Low:  < 70%
    """
    if df_cleaned.empty:
        return pd.DataFrame(
            columns=["station_id", "station_name", "valid_hours", "total_hours", "data_quality_pct", "quality_label", "notes"]
        )

    max_time = df_cleaned["timestamp"].max()
    start_time = max_time - pd.Timedelta(days=days) + pd.Timedelta(hours=1)
    df_window = df_cleaned[(df_cleaned["timestamp"] >= start_time) & (df_cleaned["timestamp"] <= max_time)]

    expected_hours = days * 24

    rows = []
    for st_id, sdf in df_window.groupby("station_id"):
        st_name = sdf["station_name"].iloc[0]
        actual_slots = len(sdf)
        valid_hours = int(sdf["pm25"].notna().sum())

        # If station has fewer slots than expected, record explicitly
        total_slots = max(actual_slots, expected_hours)
        pct = round(100.0 * valid_hours / total_slots, 2) if total_slots > 0 else 0.0

        if pct >= 90.0:
            label = "Good"
        elif pct >= 70.0:
            label = "Fair"
        else:
            label = "Low"

        notes = ""
        if actual_slots < expected_hours:
            notes = f"Insufficient historical coverage: {actual_slots}/{expected_hours} hours available"

        rows.append(
            {
                "station_id": int(st_id),
                "station_name": str(st_name),
                "valid_hours": valid_hours,
                "total_hours": total_slots,
                "data_quality_pct": pct,
                "quality_label": label,
                "notes": notes,
            }
        )

    summary_df = pd.DataFrame(rows).sort_values("data_quality_pct", ascending=False).reset_index(drop=True)
    return summary_df


def generate_clean_comparison_chart(
    raw_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    station_id: int,
    output_path: Path,
) -> Path:
    """Create a Plotly before/after time-series comparison chart for one station."""
    # Normalize timestamps
    raw_st = raw_df[raw_df["station_id"] == station_id].copy()
    if "timestamp_ist" in raw_st.columns:
        raw_st["timestamp"] = _normalize_timestamp_series(raw_st["timestamp_ist"])
    elif "timestamp" in raw_st.columns:
        raw_st["timestamp"] = _normalize_timestamp_series(raw_st["timestamp"])
    raw_st = raw_st.sort_values("timestamp")

    clean_st = clean_df[clean_df["station_id"] == station_id].sort_values("timestamp").copy()

    st_name = clean_st["station_name"].iloc[0] if not clean_st.empty else f"Station {station_id}"
    date_min = clean_st["timestamp"].min().strftime("%Y-%m-%d")
    date_max = clean_st["timestamp"].max().strftime("%Y-%m-%d")

    fig = go.Figure()

    # Raw observations
    fig.add_trace(
        go.Scatter(
            x=raw_st["timestamp"],
            y=raw_st["pm25"],
            mode="lines",
            line=dict(color="#FF9500", width=1, dash="dot"),
            connectgaps=False,
            name="Raw Observed PM2.5",
            opacity=0.7,
            hovertemplate="Raw PM2.5: %{y:.1f} µg/m³<extra></extra>",
        )
    )

    # Cleaned observations
    fig.add_trace(
        go.Scatter(
            x=clean_st["timestamp"],
            y=clean_st["pm25"],
            mode="lines",
            line=dict(color="#0071E3", width=1.5),
            connectgaps=False,
            name="Cleaned PM2.5 (QA/QC Applied)",
            hovertemplate="Cleaned PM2.5: %{y:.1f} µg/m³<extra></extra>",
        )
    )

    # Highlight interpolated filled points
    filled_st = clean_st[clean_st["pm25_filled"]].copy()
    if not filled_st.empty:
        fig.add_trace(
            go.Scatter(
                x=filled_st["timestamp"],
                y=filled_st["pm25"],
                mode="markers",
                marker=dict(size=4, color="#34C759", symbol="circle"),
                name="Interpolated (1–3h Gap Filled)",
                hovertemplate="Filled: %{y:.1f} µg/m³<extra></extra>",
            )
        )

    # Threshold horizontal guides
    fig.add_hline(
        y=60,
        line_dash="dot",
        line_color="#34C759",
        annotation_text="Good (<=60)",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=250,
        line_dash="dash",
        line_color="#FF3B30",
        annotation_text="Severe (>250)",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(
            text=f"<b>Before vs. After QA/QC Cleaning Comparison</b><br><sup>Station: {st_name} (ID: {station_id}) | {date_min} to {date_max} IST</sup>",
            font=dict(size=17, family="-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, sans-serif"),
        ),
        xaxis=dict(title="Observation Timestamp (IST - Asia/Kolkata)", showgrid=True, gridcolor="#E5E5EA"),
        yaxis=dict(
            title="Hourly PM2.5 Concentration (µg/m³)",
            showgrid=True,
            gridcolor="#E5E5EA",
            range=[0, min(500, clean_st["pm25"].max() * 1.1 if clean_st["pm25"].notna().any() else 500)],
        ),
        template="plotly_white",
        margin=dict(l=60, r=40, t=80, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    logger.info(f"Saved cleaning comparison chart to {output_path}")
    return output_path


def main() -> None:
    """Execute cleaning pipeline on actual processed S3 data and produce quality summaries."""
    print("=" * 80)
    print("AERA Step 4: Data Cleaning & Quality Flagging")
    print("=" * 80)

    pm25_path = PROCESSED_DATA_DIR / "pm25_observed.parquet"
    weather_path = PROCESSED_DATA_DIR / "weather_observed.parquet"

    if not pm25_path.exists():
        print(f"BLOCKER: Input file {pm25_path} does not exist.")
        return

    df_pm25 = pd.read_parquet(pm25_path)
    df_weather = pd.read_parquet(weather_path) if weather_path.exists() else None

    print(f"Loaded {len(df_pm25)} raw PM2.5 observations across {df_pm25['station_id'].nunique()} stations.")
    if df_weather is not None:
        print(f"Loaded {len(df_weather)} weather observations.")

    # 1. Clean dataset
    df_clean = clean(df_pm25, df_weather)
    clean_output_path = PROCESSED_DATA_DIR / "clean.parquet"
    df_clean.to_parquet(clean_output_path, index=False)
    print(f"\n[Saved] Cleaned observations: {clean_output_path} ({len(df_clean)} hourly records)")

    # 2. Quality summary over latest 30 days
    summary_df = compute_quality_summary(df_clean, days=30)
    summary_output_path = OUTPUTS_DIR / "quality_summary.parquet"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_parquet(summary_output_path, index=False)
    print(f"[Saved] Quality summary: {summary_output_path}")

    # 3. Print per-station cleaning and flag audit
    print("\n" + "=" * 80)
    print("PER-STATION CLEANING AUDIT & QA/QC FLAGS")
    print("=" * 80)
    header = (
        f"{'ID':<8} | {'Station Name':<32} | {'Total Hrs':<9} | {'Gap Flags':<9} | "
        f"{'Filled':<6} | {'Stuck':<5} | {'Impos':<5} | {'30d Valid%':<10} | {'Quality'}"
    )
    print(header)
    print("-" * len(header))

    # Merge flag counts with quality summary
    for st_id, sdf in df_clean.groupby("station_id"):
        st_name = sdf["station_name"].iloc[0]
        total_hrs = len(sdf)
        gap_count = sdf["flag_gap"].sum()
        filled_count = sdf["pm25_filled"].sum()
        stuck_count = sdf["flag_stuck"].sum()
        impos_count = sdf["flag_impossible"].sum()

        st_sum = summary_df[summary_df["station_id"] == st_id]
        if not st_sum.empty:
            pct = st_sum["data_quality_pct"].iloc[0]
            label = st_sum["quality_label"].iloc[0]
        else:
            pct, label = 0.0, "N/A"

        print(
            f"{st_id:<8} | {st_name[:32]:<32} | {total_hrs:<9} | {gap_count:<9} | "
            f"{filled_count:<6} | {stuck_count:<5} | {impos_count:<5} | {pct:<9.1f}% | {label}"
        )

    # 4. Generate visual comparison chart
    chart_path = OUTPUTS_DIR / "s4_clean_comparison.html"
    generate_clean_comparison_chart(df_pm25, df_clean, station_id=3409482, output_path=chart_path)
    print(f"\n[Generated] Cleaning comparison HTML: {chart_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
