"""Discover recurring air pollution patterns in Mumbai monitoring data.

Detects three operational patterns across stations:
1. Diurnal hourly peak (peak hour vs. overall median).
2. Calm wind episodes (stagnation periods below lower quartile wind speed).
3. Persistent worst stations (highest % of hours exceeding 60 µg/m³ threshold).
Also builds a station-by-hour-of-day heatmap and saves patterns.json and heatmap.parquet.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config import OUTPUTS_DIR, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


def evening_peak(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate median PM2.5 by hour of day and identify diurnal peak.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned observations with 'timestamp' and 'pm25'.

    Returns
    -------
    Dict[str, Any]
        Dictionary with title, sentence, supporting numeric values,
        data_window, and weak flag.
    """
    valid = df[df["pm25"].notna()].copy()
    if valid.empty:
        return {
            "title": "Diurnal Peak Concentration",
            "sentence": "Insufficient PM2.5 observations to evaluate hourly diurnal patterns.",
            "peak_hour": None,
            "peak_median": None,
            "overall_median": None,
            "percentage_difference": None,
            "sample_size": 0,
            "data_window": {"start": None, "end": None, "days": 0},
            "weak": True,
        }

    # Extract hour from timestamp
    hour_series = valid["timestamp"].dt.hour
    hourly_medians = valid.groupby(hour_series)["pm25"].median()

    peak_hour = int(hourly_medians.idxmax())
    peak_median = float(round(hourly_medians.max(), 1))
    overall_median = float(round(valid["pm25"].median(), 1))

    if overall_median > 0:
        pct_diff = float(round(100.0 * (peak_median - overall_median) / overall_median, 1))
    else:
        pct_diff = 0.0

    t_min = valid["timestamp"].min().strftime("%Y-%m-%d")
    t_max = valid["timestamp"].max().strftime("%Y-%m-%d")
    days = int((valid["timestamp"].max() - valid["timestamp"].min()).total_seconds() // 86400) + 1

    # Weak if uplift < 5% or sample size < 100
    is_weak = (pct_diff < 5.0) or (len(valid) < 100)

    sentence = (
        f"Across Mumbai monitoring stations, PM2.5 concentrations typically peak at {peak_hour:02d}:00 "
        f"with a median of {peak_median:.1f} µg/m³, which is {pct_diff:.1f}% higher than the "
        f"overall median of {overall_median:.1f} µg/m³."
    )
    if is_weak:
        sentence += " (Pattern marked weak due to modest diurnal variation under 5% or limited observations)."

    return {
        "title": "Diurnal Peak Concentration",
        "sentence": sentence,
        "peak_hour": peak_hour,
        "peak_median": peak_median,
        "overall_median": overall_median,
        "percentage_difference": pct_diff,
        "sample_size": int(len(valid)),
        "data_window": {"start": t_min, "end": t_max, "days": days},
        "weak": bool(is_weak),
    }


def calm_wind_episodes(df: pd.DataFrame) -> Dict[str, Any]:
    """Identify calm-wind stagnation episodes and measure PM2.5 uplift.

    Calculates lower quartile (Q1) of wind speeds, identifies episodes of >=3
    consecutive hours below Q1, and compares PM2.5 during episodes vs other hours.
    """
    valid_weather = df[df["wind_speed"].notna()].copy()
    valid_pm25 = df[df["pm25"].notna()].copy()

    if valid_weather.empty or valid_pm25.empty:
        return {
            "title": "Calm-Wind Stagnation Uplift",
            "sentence": "Insufficient wind speed or PM2.5 observations to identify stagnation episodes.",
            "q1_wind_speed": None,
            "episode_hours": 0,
            "calm_mean_pm25": None,
            "other_mean_pm25": None,
            "percentage_difference": None,
            "sample_size": 0,
            "data_window": {"start": None, "end": None, "days": 0},
            "weak": True,
        }

    # Dedup timeline to evaluate unique weather slots
    w_timeline = df.drop_duplicates(subset=["timestamp"])[["timestamp", "wind_speed"]].sort_values("timestamp").copy()
    valid_ws = w_timeline["wind_speed"].dropna()

    if len(valid_ws) < 24:
        return {
            "title": "Calm-Wind Stagnation Uplift",
            "sentence": "Insufficient continuous wind speed measurements to identify stagnation episodes.",
            "q1_wind_speed": None,
            "episode_hours": 0,
            "calm_mean_pm25": None,
            "other_mean_pm25": None,
            "percentage_difference": None,
            "sample_size": int(len(valid_pm25)),
            "data_window": {"start": None, "end": None, "days": 0},
            "weak": True,
        }

    q1_threshold = float(round(valid_ws.quantile(0.25), 2))

    # Identify episodes of >=3 consecutive hours below Q1
    below_q1 = w_timeline["wind_speed"] <= q1_threshold
    diff = (below_q1 != below_q1.shift()) | (~below_q1)
    run_id = diff.cumsum()
    run_len = below_q1.groupby(run_id).transform(lambda x: len(x) if x.iloc[0] else 0)
    is_episode = below_q1 & (run_len >= 3)
    w_timeline["is_calm_episode"] = is_episode

    episode_timeline_hours = int(is_episode.sum())

    # Map back to station observations
    df_merged = pd.merge(df, w_timeline[["timestamp", "is_calm_episode"]], on="timestamp", how="left")

    calm_obs = df_merged[df_merged["is_calm_episode"] & df_merged["pm25"].notna()]["pm25"]
    other_obs = df_merged[(~df_merged["is_calm_episode"]) & df_merged["pm25"].notna()]["pm25"]

    t_min = df["timestamp"].min().strftime("%Y-%m-%d")
    t_max = df["timestamp"].max().strftime("%Y-%m-%d")
    days = int((df["timestamp"].max() - df["timestamp"].min()).total_seconds() // 86400) + 1

    if len(calm_obs) < 10 or len(other_obs) < 10:
        return {
            "title": "Calm-Wind Stagnation Uplift",
            "sentence": f"Fewer than 10 observations during calm wind episodes (<= {q1_threshold} km/h).",
            "q1_wind_speed": q1_threshold,
            "episode_hours": episode_timeline_hours,
            "calm_mean_pm25": None,
            "other_mean_pm25": None,
            "percentage_difference": None,
            "sample_size": int(len(calm_obs) + len(other_obs)),
            "data_window": {"start": t_min, "end": t_max, "days": days},
            "weak": True,
        }

    calm_mean = float(round(calm_obs.mean(), 1))
    other_mean = float(round(other_obs.mean(), 1))

    if other_mean > 0:
        pct_diff = float(round(100.0 * (calm_mean - other_mean) / other_mean, 1))
    else:
        pct_diff = 0.0

    # Mark weak if uplift is negligible (< 5%) or episodes are few (< 12 hours)
    is_weak = (pct_diff < 5.0) or (episode_timeline_hours < 12)

    sentence = (
        f"During calm-wind stagnation episodes (wind speed <= {q1_threshold:.1f} km/h lasting at least 3 hours), "
        f"average PM2.5 rises to {calm_mean:.1f} µg/m³ compared to {other_mean:.1f} µg/m³ during ventilated periods "
        f"({pct_diff:+.1f}% difference across {len(calm_obs)} episode observations)."
    )
    if is_weak:
        sentence += " (Pattern marked weak due to negligible uplift under 5% or limited episode duration)."

    return {
        "title": "Calm-Wind Stagnation Uplift",
        "sentence": sentence,
        "q1_wind_speed": q1_threshold,
        "episode_hours": episode_timeline_hours,
        "calm_mean_pm25": calm_mean,
        "other_mean_pm25": other_mean,
        "percentage_difference": pct_diff,
        "sample_size": int(len(calm_obs) + len(other_obs)),
        "data_window": {"start": t_min, "end": t_max, "days": days},
        "weak": bool(is_weak),
    }


def persistent_worst_stations(df: pd.DataFrame, threshold: float = 60.0) -> Dict[str, Any]:
    """Rank stations by percentage of valid observation hours exceeding threshold.

    Parameters
    ----------
    df : pd.DataFrame
        Observations with 'station_id', 'station_name', 'pm25'.
    threshold : float
        PM2.5 exceedance threshold (default 60 µg/m³ for Unhealthy).
    """
    valid = df[df["pm25"].notna()].copy()
    if valid.empty:
        return {
            "title": "Persistent Worst Stations",
            "sentence": "No valid observations to rank station exceedance frequencies.",
            "top_stations": [],
            "sample_size": 0,
            "data_window": {"start": None, "end": None, "days": 0},
            "weak": True,
        }

    station_records = []
    for st_id, sdf in valid.groupby("station_id"):
        st_name = str(sdf["station_name"].iloc[0])
        n_valid = len(sdf)
        n_exceed = int((sdf["pm25"] > threshold).sum())
        pct = float(round(100.0 * n_exceed / n_valid, 1)) if n_valid > 0 else 0.0

        station_records.append(
            {
                "station_id": int(st_id),
                "station_name": st_name,
                "valid_hours": int(n_valid),
                "exceedance_hours": int(n_exceed),
                "exceedance_percentage": pct,
            }
        )

    rank_df = pd.DataFrame(station_records).sort_values("exceedance_percentage", ascending=False)
    top_3 = rank_df.head(3).to_dict(orient="records")

    t_min = valid["timestamp"].min().strftime("%Y-%m-%d")
    t_max = valid["timestamp"].max().strftime("%Y-%m-%d")
    days = int((valid["timestamp"].max() - valid["timestamp"].min()).total_seconds() // 86400) + 1

    is_weak = len(top_3) < 3 or all(st["exceedance_hours"] == 0 for st in top_3)

    if top_3:
        st1, st2, st3 = top_3[0], top_3[1], top_3[2] if len(top_3) > 2 else top_3[-1]
        sentence = (
            f"Over the last {days} days, the stations with the most frequent Unhealthy air (>60 µg/m³) were "
            f"{st1['station_name']} ({st1['exceedance_percentage']}% of {st1['valid_hours']} valid hours), "
            f"{st2['station_name']} ({st2['exceedance_percentage']}% of {st2['valid_hours']} valid hours), and "
            f"{st3['station_name']} ({st3['exceedance_percentage']}% of {st3['valid_hours']} valid hours)."
        )
    else:
        sentence = "No stations exceeded the threshold."

    return {
        "title": "Persistent Worst Stations",
        "sentence": sentence,
        "threshold_ug_m3": float(threshold),
        "top_stations": top_3,
        "sample_size": int(len(valid)),
        "data_window": {"start": t_min, "end": t_max, "days": days},
        "weak": bool(is_weak),
    }


def build_station_hour_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """Build station-by-hour-of-day heatmap DataFrame with median PM2.5.

    Returns DataFrame with columns:
    ['station_id', 'station_name', 'hour', 'median_pm25']
    Preserves missing combinations as missing (NaN).
    """
    df = df.copy()
    df["hour"] = df["timestamp"].dt.hour

    stations = df[["station_id", "station_name"]].drop_duplicates().sort_values("station_id")
    hours = list(range(24))

    # Create full cross-product grid
    grid = []
    for _, st in stations.iterrows():
        for h in hours:
            grid.append({"station_id": int(st["station_id"]), "station_name": str(st["station_name"]), "hour": h})
    full_grid = pd.DataFrame(grid)

    valid = df[df["pm25"].notna()]
    grouped = valid.groupby(["station_id", "hour"])["pm25"].median().reset_index()
    grouped.rename(columns={"pm25": "median_pm25"}, inplace=True)
    grouped["median_pm25"] = grouped["median_pm25"].round(1)

    heatmap_df = pd.merge(full_grid, grouped, on=["station_id", "hour"], how="left")
    return heatmap_df.sort_values(["station_id", "hour"]).reset_index(drop=True)


def render_heatmap_chart(heatmap_df: pd.DataFrame, output_path: Path) -> Path:
    """Render Plotly heatmap using single-hue sequential colour scale."""
    pivot = heatmap_df.pivot(index="station_name", columns="hour", values="median_pm25")
    # Sort stations alphabetically or by median
    pivot = pivot.sort_index(ascending=False)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[f"{h:02d}:00" for h in pivot.columns],
            y=pivot.index.tolist(),
            colorscale="Blues",  # Single-hue sequential colour scale
            colorbar=dict(title=dict(text="Median PM2.5 (µg/m³)", side="right")),
            hovertemplate="Station: %{y}<br>Hour: %{x}<br>Median PM2.5: %{z:.1f} µg/m³<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(
            text="<b>Mumbai Diurnal Pollution Pattern by Station</b><br><sup>Hourly Median PM2.5 Concentrations (Single-Hue Sequential Scale)</sup>",
            font=dict(size=17, family="-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, sans-serif"),
        ),
        xaxis=dict(title="Hour of Day (IST)", tickangle=0),
        yaxis=dict(title="", tickfont=dict(size=11)),
        template="plotly_white",
        margin=dict(l=220, r=40, t=80, b=60),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    logger.info(f"Saved diurnal heatmap HTML to {output_path}")
    return output_path


def main() -> None:
    """Execute pattern discovery on actual cleaned data and export outputs."""
    print("=" * 80)
    print("CityPulse Step 5: Discover Recurring Pollution Patterns")
    print("=" * 80)

    clean_path = PROCESSED_DATA_DIR / "clean.parquet"
    if not clean_path.exists():
        print(f"BLOCKER: Input file {clean_path} does not exist.")
        return

    df_clean = pd.read_parquet(clean_path)
    print(f"Loaded {len(df_clean)} hourly records across {df_clean['station_id'].nunique()} stations.")

    # Use the latest 60–90 days of actual observations
    max_ts = df_clean["timestamp"].max()
    window_days = 90
    start_ts = max_ts - pd.Timedelta(days=window_days)
    df_window = df_clean[df_clean["timestamp"] >= start_ts].copy()
    print(f"Analysis window: {df_window['timestamp'].min()} to {df_window['timestamp'].max()} ({window_days} days, {len(df_window)} rows)")

    # 1. Pattern 1: Evening/Diurnal Peak
    p1 = evening_peak(df_window)

    # 2. Pattern 2: Calm Wind Episodes
    p2 = calm_wind_episodes(df_window)

    # 3. Pattern 3: Persistent Worst Stations
    p3 = persistent_worst_stations(df_window, threshold=60.0)

    patterns_output = {
        "generated_at_utc": pd.Timestamp.now("UTC").isoformat(),
        "analysis_window": {
            "start": p1["data_window"]["start"],
            "end": p1["data_window"]["end"],
            "days": window_days,
            "total_observations": int(df_window["pm25"].notna().sum()),
        },
        "patterns": {
            "evening_peak": p1,
            "calm_wind_episodes": p2,
            "persistent_worst_stations": p3,
        },
    }

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    patterns_json_path = OUTPUTS_DIR / "patterns.json"
    patterns_json_path.write_text(json.dumps(patterns_output, indent=2), encoding="utf-8")
    print(f"\n[Saved] Patterns JSON: {patterns_json_path}")

    # 4. Station-by-Hour Heatmap
    heatmap_df = build_station_hour_heatmap(df_window)
    heatmap_parquet_path = OUTPUTS_DIR / "heatmap.parquet"
    heatmap_df.to_parquet(heatmap_parquet_path, index=False)
    print(f"[Saved] Heatmap Parquet: {heatmap_parquet_path} ({len(heatmap_df)} rows)")

    # 5. Render Heatmap Visualization
    heatmap_html_path = OUTPUTS_DIR / "heatmap.html"
    render_heatmap_chart(heatmap_df, heatmap_html_path)
    print(f"[Generated] Heatmap HTML: {heatmap_html_path}")

    # 6. Print Pattern Report
    print("\n" + "=" * 80)
    print("DISCOVERED OPERATIONAL PATTERNS REPORT")
    print("=" * 80)

    print("\n[Pattern 1] Diurnal Peak Concentration:")
    print(f"  Sentence : {p1['sentence']}")
    print(f"  Peak Hour: {p1['peak_hour']:02d}:00 IST | Peak Median: {p1['peak_median']} µg/m³ | Overall Median: {p1['overall_median']} µg/m³")
    print(f"  Uplift   : {p1['percentage_difference']:+.1f}% | Weak: {p1['weak']} | Sample size: {p1['sample_size']}")

    print("\n[Pattern 2] Calm-Wind Stagnation Uplift:")
    print(f"  Sentence : {p2['sentence']}")
    print(f"  Threshold: Q1 <= {p2['q1_wind_speed']} km/h | Stagnation Hours: {p2['episode_hours']}")
    print(f"  PM2.5    : Calm = {p2['calm_mean_pm25']} µg/m³ vs Other = {p2['other_mean_pm25']} µg/m³ ({p2['percentage_difference']:+.1f}%) | Weak: {p2['weak']}")

    print("\n[Pattern 3] Persistent Worst Stations (>60 µg/m³):")
    print(f"  Sentence : {p3['sentence']}")
    for idx, st in enumerate(p3["top_stations"], 1):
        print(f"  #{idx}: {st['station_name']} -> {st['exceedance_percentage']}% exceedance ({st['exceedance_hours']}/{st['valid_hours']} hrs)")
    print(f"  Weak: {p3['weak']} | Total Valid Sample: {p3['sample_size']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
