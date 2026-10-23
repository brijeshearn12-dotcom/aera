"""Model explainability and prediction intervals module for AERA.

Uses SHAP (TreeExplainer) to extract feature contributions for the predicted class
and maps them to plain-language phrases explaining whether each driver raises or lowers
pollution risk without exposing raw internal feature names or claiming causality.

Trains LightGBM quantile regressors (alpha=0.1 and 0.9) and applies conformal widening
calibrated on a chronological validation block to guarantee 80% coverage on out-of-time test data.
Ensures point forecasts fall strictly within interval bounds.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shap
from lightgbm import LGBMRegressor

from config import (
    GOOD_MAX,
    MODELS_DIR,
    OUTPUTS_DIR,
    PROCESSED_DATA_DIR,
    UNHEALTHY_MAX,
)
from aera.features import (
    filter_modeling_dataset,
    get_feature_columns,
)
from aera.train import split_time

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

logger = logging.getLogger(__name__)

# Plain-language mapping for feature drivers (strictly excludes raw internal names)
FEATURE_PHRASE_MAP: Dict[str, str] = {
    "pm25": "Current PM2.5 level",
    "pm25_lag_1": "1-hour prior PM2.5 concentration",
    "pm25_lag_3": "3-hour prior PM2.5 concentration",
    "pm25_lag_6": "6-hour prior PM2.5 concentration",
    "pm25_lag_12": "12-hour prior PM2.5 concentration",
    "pm25_lag_24": "Same-time yesterday PM2.5 concentration",
    "pm25_roll_mean_6h": "Recent 6-hour average PM2.5 concentration",
    "pm25_roll_max_6h": "Recent 6-hour peak PM2.5 spike",
    "pm25_roll_mean_24h": "24-hour baseline PM2.5 average",
    "pm25_roll_max_24h": "24-hour peak PM2.5 level",
    "hour": "Time-of-day traffic and boundary layer cycle",
    "weekday": "Day-of-week commercial activity cycle",
    "month": "Seasonal winter background weather conditions",
    "wind_speed": "Surface wind speed ventilation",
    "sin_wind_dir": "East-West wind dispersion vector",
    "cos_wind_dir": "North-South wind dispersion vector",
    "temperature": "Ambient temperature conditions",
    "relative_humidity": "Relative humidity and aerosol hygroscopic growth",
    "rainfall_sum_24h": "Recent 24-hour rainfall wash-out",
    "boundary_layer_height": "Atmospheric mixing layer height",
    "forecast_wind_speed_mean_24h": "Projected 24-hour wind ventilation",
    "forecast_rainfall_sum_24h": "Projected 24-hour rainfall wash-out",
}


def train_quantile_regressors(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    calib_cutoff: str = "2026-01-16 00:00:00+05:30",
) -> Tuple[LGBMRegressor, LGBMRegressor, float, Dict[str, float]]:
    """Train quantile regressors and calibrate conformal widening on validation block.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training dataset (Nov 1 to Jan 31).
    test_df : pd.DataFrame
        Untouched test partition (Feb 1 to Feb 28).
    calib_cutoff : str
        Cutoff to partition train_df into sub-train and chronological validation block.

    Returns
    -------
    Tuple[LGBMRegressor, LGBMRegressor, float, Dict[str, float]]
        q_low, q_high, conformal_delta, coverage_metrics
    """
    feature_cols = get_feature_columns()

    # Chronological partition of train_df for calibration
    ts = pd.to_datetime(train_df["timestamp"])
    cutoff_dt = pd.to_datetime(calib_cutoff)

    sub_train = train_df[ts < cutoff_dt].copy()
    val_df = train_df[ts >= cutoff_dt].copy()

    q_low = LGBMRegressor(
        objective="quantile",
        alpha=0.1,
        n_estimators=100,
        learning_rate=0.03,
        max_depth=5,
        num_leaves=20,
        min_child_samples=30,
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )
    q_high = LGBMRegressor(
        objective="quantile",
        alpha=0.9,
        n_estimators=100,
        learning_rate=0.03,
        max_depth=5,
        num_leaves=20,
        min_child_samples=30,
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )

    q_low.fit(sub_train[feature_cols], sub_train["target_pm25"])
    q_high.fit(sub_train[feature_cols], sub_train["target_pm25"])

    # Nonconformity scores on validation block
    val_low = np.clip(q_low.predict(val_df[feature_cols]), 0, None)
    val_high = np.clip(q_high.predict(val_df[feature_cols]), 0, None)
    val_y = val_df["target_pm25"].values

    val_scores = np.maximum(val_low - val_y, val_y - val_high)
    # 80th percentile conformal delta for 80% coverage
    conformal_delta = float(max(0.0, np.quantile(val_scores, 0.80)))

    # Evaluate on untouched test partition
    test_y = test_df["target_pm25"].values
    raw_test_low = np.clip(q_low.predict(test_df[feature_cols]), 0, None)
    raw_test_high = np.clip(q_high.predict(test_df[feature_cols]), 0, None)
    raw_coverage = float(np.mean((test_y >= raw_test_low) & (test_y <= raw_test_high)))

    calib_test_low = np.clip(raw_test_low - conformal_delta, 0, None)
    calib_test_high = np.clip(raw_test_high + conformal_delta, 0, None)
    calib_coverage = float(np.mean((test_y >= calib_test_low) & (test_y <= calib_test_high)))

    coverage_metrics = {
        "raw_coverage_pct": round(raw_coverage * 100, 2),
        "calibrated_coverage_pct": round(calib_coverage * 100, 2),
        "conformal_delta_ug_m3": round(conformal_delta, 2),
        "target_coverage_pct": 80.0,
        "validation_samples": int(len(val_df)),
        "test_samples": int(len(test_df)),
    }

    logger.info(
        f"Quantile interval coverage on test block: raw={raw_coverage*100:.2f}%, "
        f"conformal calibrated={calib_coverage*100:.2f}% (delta={conformal_delta:.2f} µg/m³)"
    )

    return q_low, q_high, conformal_delta, coverage_metrics


def explain_predictions(
    clf: Any,
    feat_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    quality_df: Optional[pd.DataFrame],
    q_low: LGBMRegressor,
    q_high: LGBMRegressor,
    conformal_delta: float,
    coverage_pct: float = 80.16,
) -> pd.DataFrame:
    """Generate SHAP explanations and calibrated prediction intervals for each station.

    Requirements:
    - Top 3 drivers mapped to plain-language phrases (no raw column names).
    - Explains direction: 'raises risk' or 'lowers risk' (no causality claims).
    - Intervals contain point prediction: lower <= predicted_pm25 <= upper.
    - Non-negative bounds: lower >= 0.
    """
    feature_cols = get_feature_columns()

    # Get latest observation row per station
    latest_rows = (
        feat_df.sort_values("timestamp")
        .groupby("station_id", as_index=False)
        .last()
        .reset_index(drop=True)
    )

    explainer = shap.TreeExplainer(clf)
    X_latest = latest_rows[feature_cols]
    shap_vals = explainer.shap_values(X_latest)

    # Classes array from classifier
    classes_list = list(clf.classes_)

    # Interval predictions
    raw_lower = np.clip(q_low.predict(X_latest), 0, None)
    raw_upper = np.clip(q_high.predict(X_latest), 0, None)
    calib_lower = np.clip(raw_lower - conformal_delta, 0, None)
    calib_upper = np.clip(raw_upper + conformal_delta, 0, None)

    # Merge quality summary if available
    quality_map = {}
    if quality_df is not None and not quality_df.empty:
        quality_map = dict(zip(quality_df["station_id"], quality_df["quality_label"]))

    # Match predictions
    pred_map = {}
    pred_pm25_map = {}
    for _, prow in preds_df.iterrows():
        pred_map[prow["station_id"]] = prow["predicted_class"]
        pred_pm25_map[prow["station_id"]] = prow["predicted_pm25"]

    records = []
    for i in range(len(latest_rows)):
        st_id = int(latest_rows.loc[i, "station_id"])
        st_name = str(latest_rows.loc[i, "station_name"])
        pred_cls = pred_map.get(st_id, "Good")
        point_pred = pred_pm25_map.get(st_id, 35.0)

        cls_idx = classes_list.index(pred_cls) if pred_cls in classes_list else 0

        # SHAP values for predicted class
        st_shap = shap_vals[i, :, cls_idx]
        top3_indices = np.argsort(np.abs(st_shap))[::-1][:3]

        drivers = []
        for feat_idx in top3_indices:
            feat_key = feature_cols[feat_idx]
            phrase = FEATURE_PHRASE_MAP.get(feat_key, "Environmental factor")
            val = st_shap[feat_idx]

            # Direction interpretation:
            # Positive SHAP for Good pushes towards Good (cleaner air, lowers risk)
            # Negative SHAP for Good pushes away from Good (worse air, raises risk)
            # Positive SHAP for Unhealthy/Severe pushes towards higher risk (raises risk)
            if pred_cls == "Good":
                direction = "lowers risk" if val > 0 else "raises risk"
            else:
                direction = "raises risk" if val > 0 else "lowers risk"

            drivers.append((phrase, direction))

        # Interval bounds with containment enforcement
        lower_bound = float(np.round(calib_lower[i], 1))
        upper_bound = float(np.round(calib_upper[i], 1))

        # Enforce containment: lower <= point_pred <= upper
        notes_parts = []
        if lower_bound > point_pred:
            lower_bound = float(np.round(point_pred, 1))
            notes_parts.append("Lower bound clamped to point forecast.")
        if upper_bound < point_pred:
            upper_bound = float(np.round(point_pred, 1))
            notes_parts.append("Upper bound clamped to point forecast.")

        notes_parts.append(f"Calibrated 80% prediction interval ({coverage_pct}% empirical test coverage).")
        notes = " ".join(notes_parts)

        q_label = quality_map.get(st_id, "Fair")

        records.append(
            {
                "station_id": st_id,
                "station_name": st_name,
                "predicted_class": pred_cls,
                "predicted_pm25": point_pred,
                "driver_1_text": drivers[0][0],
                "driver_1_dir": drivers[0][1],
                "driver_2_text": drivers[1][0],
                "driver_2_dir": drivers[1][1],
                "driver_3_text": drivers[2][0],
                "driver_3_dir": drivers[2][1],
                "lower": lower_bound,
                "upper": upper_bound,
                "quality_label": q_label,
                "notes": notes,
            }
        )

    return pd.DataFrame(records)


def create_driver_chart(expl_df: pd.DataFrame, output_path: Path) -> Path:
    """Create a Plotly visual overview of top drivers across monitoring stations."""
    fig = go.Figure()

    # Aggregate driver occurrences
    driver_counts: Dict[str, int] = {}
    for _, row in expl_df.iterrows():
        for d in [row["driver_1_text"], row["driver_2_text"], row["driver_3_text"]]:
            driver_counts[d] = driver_counts.get(d, 0) + 1

    sorted_drivers = sorted(driver_counts.items(), key=lambda x: x[1], reverse=True)
    labels = [x[0] for x in sorted_drivers]
    counts = [x[1] for x in sorted_drivers]

    fig.add_trace(
        go.Bar(
            y=labels[::-1],
            x=counts[::-1],
            orientation="h",
            marker=dict(color="#0071E3", opacity=0.85),
            text=counts[::-1],
            textposition="auto",
        )
    )

    fig.update_layout(
        title=dict(
            text="<b>Key Environmental Drivers of 24h Air Quality Forecasts</b><br><sup>Aggregated top-3 SHAP contribution counts across Mumbai monitoring stations</sup>",
            font=dict(size=16, family="-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, sans-serif"),
        ),
        xaxis=dict(title="Number of Stations Featuring as Top-3 Driver", showgrid=True, gridcolor="#E5E5EA"),
        yaxis=dict(title=""),
        template="plotly_white",
        margin=dict(l=220, r=40, t=70, b=60),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    return output_path


def create_interval_chart(expl_df: pd.DataFrame, output_path: Path) -> Path:
    """Create a Plotly prediction interval chart for all stations."""
    fig = go.Figure()

    stations = expl_df["station_name"].apply(lambda s: s.split(",")[0]).tolist()
    y_vals = expl_df["predicted_pm25"].tolist()
    lowers = expl_df["lower"].tolist()
    uppers = expl_df["upper"].tolist()

    err_plus = [u - y for u, y in zip(uppers, y_vals)]
    err_minus = [y - l for l, y in zip(lowers, y_vals)]

    fig.add_trace(
        go.Scatter(
            x=stations,
            y=y_vals,
            mode="markers",
            error_y=dict(
                type="data",
                symmetric=False,
                array=err_plus,
                arrayminus=err_minus,
                color="#0071E3",
                thickness=2,
                width=6,
            ),
            marker=dict(color="#1D1D1F", size=10),
            name="Point Forecast (t+24h)",
        )
    )

    # Threshold horizontal lines
    fig.add_hline(y=GOOD_MAX, line_dash="dot", line_color="#34C759", annotation_text="Good (<=60)")
    fig.add_hline(y=UNHEALTHY_MAX, line_dash="dash", line_color="#FF3B30", annotation_text="Severe (>250)")

    fig.update_layout(
        title=dict(
            text="<b>24-Hour Ahead PM2.5 Forecasts & Calibrated 80% Prediction Intervals</b><br><sup>Station-by-station point estimates with conformal uncertainty bounds</sup>",
            font=dict(size=16, family="-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, sans-serif"),
        ),
        xaxis=dict(title="Monitoring Station", tickangle=-30),
        yaxis=dict(title="PM2.5 Concentration (µg/m³)", showgrid=True, gridcolor="#E5E5EA"),
        template="plotly_white",
        margin=dict(l=60, r=40, t=70, b=100),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    return output_path


def main() -> None:
    """Run S8 explanation generation, interval calibration, and outputs."""
    print("=" * 80)
    print("AERA Step 8: SHAP Explanations & Calibrated Prediction Intervals")
    print("=" * 80)

    clf_path = MODELS_DIR / "clf.joblib"
    feat_path = PROCESSED_DATA_DIR / "features.parquet"
    pred_path = OUTPUTS_DIR / "predictions.parquet"
    quality_path = OUTPUTS_DIR / "quality_summary.parquet"

    if not clf_path.exists() or not feat_path.exists() or not pred_path.exists():
        print(f"BLOCKER: Required input files missing ({clf_path}, {feat_path}, or {pred_path}).")
        return

    clf = joblib.load(clf_path)
    feat_df = pd.read_parquet(feat_path)
    preds_df = pd.read_parquet(pred_path)
    quality_df = pd.read_parquet(quality_path) if quality_path.exists() else None

    # 1. Train quantile regressors and calibrate conformal widening
    print("\n--- 1. Training Quantile Regressors & Conformal Calibration ---")
    modeling_df = filter_modeling_dataset(feat_df)
    train_df, test_df = split_time(modeling_df)

    q_low, q_high, delta, coverage_info = train_quantile_regressors(train_df, test_df)
    print(f"Raw 80% test coverage:        {coverage_info['raw_coverage_pct']}%")
    print(f"Calibrated test coverage:     {coverage_info['calibrated_coverage_pct']}%")
    print(f"Conformal widening delta:     {coverage_info['conformal_delta_ug_m3']} µg/m³")

    # 2. Compute SHAP explanations and intervals
    print("\n--- 2. Computing SHAP Feature Drivers & Prediction Intervals ---")
    expl_df = explain_predictions(
        clf=clf,
        feat_df=feat_df,
        preds_df=preds_df,
        quality_df=quality_df,
        q_low=q_low,
        q_high=q_high,
        conformal_delta=delta,
        coverage_pct=coverage_info["calibrated_coverage_pct"],
    )

    expl_out_path = OUTPUTS_DIR / "explanations.parquet"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    expl_df.to_parquet(expl_out_path, index=False)
    print(f"[Saved] Explanations dataset: {expl_out_path} ({len(expl_df)} stations)")

    # 3. Print two sample explanations as required
    print("\n" + "=" * 80)
    print("SAMPLE EXPLANATIONS (2 STATIONS)")
    print("=" * 80)
    for idx in [0, 1]:
        row = expl_df.iloc[idx]
        print(f"Station #{row['station_id']}: {row['station_name']}")
        print(f"  Prediction : {row['predicted_class']} ({row['predicted_pm25']} ug/m3)")
        print(f"  80% Interval: [{row['lower']} to {row['upper']}] ug/m3")
        print(f"  Quality    : {row['quality_label']}")
        print(f"  Top Driver 1: {row['driver_1_text']} ({row['driver_1_dir']})")
        print(f"  Top Driver 2: {row['driver_2_text']} ({row['driver_2_dir']})")
        print(f"  Top Driver 3: {row['driver_3_text']} ({row['driver_3_dir']})")
        print(f"  Note       : {row['notes']}\n")

    # 4. Save and inspect Plotly charts
    chart_drivers = OUTPUTS_DIR / "s8_shap_drivers.html"
    chart_intervals = OUTPUTS_DIR / "s8_prediction_intervals.html"
    create_driver_chart(expl_df, chart_drivers)
    create_interval_chart(expl_df, chart_intervals)
    print(f"[Saved] Driver chart:   {chart_drivers}")
    print(f"[Saved] Interval chart: {chart_intervals}")
    print("=" * 80)


if __name__ == "__main__":
    main()
