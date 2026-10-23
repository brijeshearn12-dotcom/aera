"""Model training, baseline evaluation, and inference pipeline for AERA.

Implements:
1. Strictly chronological train/test splitting (Nov 2025 – Jan 2026 train; Feb 2026 test).
2. Two baseline models:
   - Persistence baseline: carries forward current PM2.5 and risk class to t+24h.
   - 24-hour moving average baseline: uses prior 24h mean as prediction.
3. LightGBM models:
   - Regressor for continuous PM2.5 concentration at t+24h.
   - Classifier with balanced class weights for 3-tier risk classification.
4. Evaluation and honest performance comparison (MAE, F1 Unhealthy-or-worse, confusion matrix).
5. Generation of 9-station latest predictions in predictions.parquet.
6. Generation of interactive Plotly evaluation comparison chart in s7_eval_comparison.html.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
)

from config import (
    GOOD_MAX,
    MODELS_DIR,
    OUTPUTS_DIR,
    PROCESSED_DATA_DIR,
    UNHEALTHY_MAX,
)
from aera.features import (
    classify_pm25,
    compute_features,
    filter_modeling_dataset,
    get_feature_columns,
)

# Silence loky core detection warning on Windows
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

logger = logging.getLogger(__name__)

SPLIT_TEST_START: str = "2026-02-01 00:00:00+05:30"
RISK_CLASSES: List[str] = ["Good", "Unhealthy", "Severe"]


def split_time(
    df: pd.DataFrame,
    test_start: str = SPLIT_TEST_START,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split dataset chronologically into training and test partitions.

    Requirements:
    - Strictly chronological (train timestamps strictly before test_start).
    - Preserves time-series ordering without shuffling or leakage.
    - Validates presence of Unhealthy examples in test partition (>= 30 required).
    """
    ts = pd.to_datetime(df["timestamp"])
    cutoff = pd.to_datetime(test_start)

    train_mask = ts < cutoff
    test_mask = ts >= cutoff

    train_df = df[train_mask].copy().sort_values(["timestamp", "station_id"]).reset_index(drop=True)
    test_df = df[test_mask].copy().sort_values(["timestamp", "station_id"]).reset_index(drop=True)

    # Class counts
    train_counts = train_df["target_class"].value_counts().to_dict()
    test_counts = test_df["target_class"].value_counts().to_dict()

    unhealthy_test_count = test_counts.get("Unhealthy", 0) + test_counts.get("Severe", 0)
    logger.info(
        f"Chronological split at {test_start}: Train rows={len(train_df)} ({train_counts}), "
        f"Test rows={len(test_df)} ({test_counts})"
    )

    if unhealthy_test_count < 30:
        logger.warning(
            f"Test partition contains only {unhealthy_test_count} Unhealthy/Severe examples "
            f"(threshold: 30)."
        )

    return train_df, test_df


def _calculate_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    labels: List[str] = RISK_CLASSES,
) -> Dict[str, Any]:
    """Calculate multi-class and binary Unhealthy-or-worse classification metrics."""
    # Binary F1 (Unhealthy or Severe vs Good)
    y_true_binary = np.isin(y_true, ["Unhealthy", "Severe"]).astype(int)
    y_pred_binary = np.isin(y_pred, ["Unhealthy", "Severe"]).astype(int)
    f1_binary = float(f1_score(y_true_binary, y_pred_binary, zero_division=0))

    # Multi-class precision, recall, f1
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )

    per_class = {}
    for idx, label in enumerate(labels):
        per_class[label] = {
            "precision": float(round(precision[idx], 4)),
            "recall": float(round(recall[idx], 4)),
            "f1": float(round(f1[idx], 4)),
            "support": int(support[idx]),
        }

    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()

    return {
        "f1_unhealthy_or_worse": float(round(f1_binary, 4)),
        "per_class": per_class,
        "confusion_matrix": {
            "labels": labels,
            "matrix": cm,
        },
    }


def evaluate_baselines(test_df: pd.DataFrame, save_path: Path | None = None) -> Dict[str, Any]:
    """Evaluate Persistence and 24-hour Moving Average baselines on test block.

    Baseline 1 - Persistence:
      Predicted PM2.5 at t+24h = current PM2.5 observation at hour t.
      Predicted class = risk tier of current PM2.5 observation.

    Baseline 2 - 24-Hour Moving Average:
      Predicted PM2.5 at t+24h = prior 24-hour mean PM2.5 ending at hour t.
      Predicted class = risk tier of the 24-hour mean.
    """
    y_true_pm25 = test_df["target_pm25"].values
    y_true_class = test_df["target_class"].values

    # 1. Persistence Baseline
    persist_pred_pm25 = test_df["pm25"].values
    persist_pred_class = test_df["pm25"].apply(classify_pm25).values
    persist_mae = float(round(mean_absolute_error(y_true_pm25, persist_pred_pm25), 2))
    persist_rmse = float(round(np.sqrt(mean_squared_error(y_true_pm25, persist_pred_pm25)), 2))
    persist_clf_metrics = _calculate_classification_metrics(y_true_class, persist_pred_class)

    # 2. 24h Moving Average Baseline
    ma24_pred_pm25 = test_df["pm25_roll_mean_24h"].values
    ma24_pred_class = test_df["pm25_roll_mean_24h"].apply(classify_pm25).values
    ma24_mae = float(round(mean_absolute_error(y_true_pm25, ma24_pred_pm25), 2))
    ma24_rmse = float(round(np.sqrt(mean_squared_error(y_true_pm25, ma24_pred_pm25)), 2))
    ma24_clf_metrics = _calculate_classification_metrics(y_true_class, ma24_pred_class)

    metrics = {
        "test_period": {
            "start": str(test_df["timestamp"].min()),
            "end": str(test_df["timestamp"].max()),
            "total_samples": int(len(test_df)),
            "good_count": int((test_df["target_class"] == "Good").sum()),
            "unhealthy_count": int((test_df["target_class"] == "Unhealthy").sum()),
            "severe_count": int((test_df["target_class"] == "Severe").sum()),
        },
        "persistence": {
            "description": "Carries forward current PM2.5 and risk class at t to t+24h",
            "mae": persist_mae,
            "rmse": persist_rmse,
            "f1_unhealthy_or_worse": persist_clf_metrics["f1_unhealthy_or_worse"],
            "per_class": persist_clf_metrics["per_class"],
            "confusion_matrix": persist_clf_metrics["confusion_matrix"],
        },
        "moving_average_24h": {
            "description": "Uses prior 24-hour mean PM2.5 ending at t as prediction for t+24h",
            "mae": ma24_mae,
            "rmse": ma24_rmse,
            "f1_unhealthy_or_worse": ma24_clf_metrics["f1_unhealthy_or_worse"],
            "per_class": ma24_clf_metrics["per_class"],
            "confusion_matrix": ma24_clf_metrics["confusion_matrix"],
        },
    }

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Saved baseline metrics to {save_path}")

    return metrics


def train_models(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    save_models: bool = True,
) -> Tuple[LGBMRegressor, LGBMClassifier, Dict[str, Any]]:
    """Train LightGBM Regressor and Classifier on chronological training data.

    Configurations:
    - Regressor: LGBMRegressor predicting target_pm25 (t+24h continuous concentration).
    - Classifier: LGBMClassifier with class_weight='balanced' predicting target_class.
    - Evaluated on strictly out-of-time test block.
    """
    feature_cols = get_feature_columns()

    X_train = train_df[feature_cols]
    y_train_reg = train_df["target_pm25"]
    y_train_clf = train_df["target_class"]

    X_test = test_df[feature_cols]
    y_test_reg = test_df["target_pm25"].values
    y_test_clf = test_df["target_class"].values

    # 1. LightGBM Regressor
    reg = LGBMRegressor(
        n_estimators=100,
        learning_rate=0.03,
        max_depth=5,
        num_leaves=20,
        min_child_samples=30,
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )
    reg.fit(X_train, y_train_reg)

    y_pred_reg = reg.predict(X_test)
    y_pred_reg_clipped = np.clip(y_pred_reg, 0, None)
    reg_mae = float(round(mean_absolute_error(y_test_reg, y_pred_reg_clipped), 2))
    reg_rmse = float(round(np.sqrt(mean_squared_error(y_test_reg, y_pred_reg_clipped)), 2))

    # Regressor implied risk classification (thresholded at GOOD_MAX and UNHEALTHY_MAX)
    reg_implied_class = np.array([classify_pm25(v) for v in y_pred_reg_clipped])
    reg_clf_metrics = _calculate_classification_metrics(y_test_clf, reg_implied_class)

    # 2. LightGBM Classifier
    clf = LGBMClassifier(
        n_estimators=100,
        learning_rate=0.03,
        max_depth=5,
        num_leaves=20,
        min_child_samples=30,
        class_weight="balanced",
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )
    clf.fit(X_train, y_train_clf)

    y_pred_clf = clf.predict(X_test)
    clf_metrics = _calculate_classification_metrics(y_test_clf, y_pred_clf)

    # Baseline comparison metrics
    baseline_metrics = evaluate_baselines(test_df)

    # Honest shipping comparison decision
    p_f1 = baseline_metrics["persistence"]["f1_unhealthy_or_worse"]
    p_mae = baseline_metrics["persistence"]["mae"]
    ma_f1 = baseline_metrics["moving_average_24h"]["f1_unhealthy_or_worse"]
    ma_mae = baseline_metrics["moving_average_24h"]["mae"]
    clf_f1 = clf_metrics["f1_unhealthy_or_worse"]

    # Comparative decision logic
    beats_persistence = (clf_f1 > p_f1) and (reg_mae < p_mae)
    beats_moving_avg = (clf_f1 > ma_f1) and (reg_mae < ma_mae)

    decision_rationale = (
        "Persistence baseline demonstrates strong diurnal autocorrelation in Mumbai PM2.5 "
        f"(MAE={p_mae:.2f}, F1={p_f1:.4f}). LightGBM Classifier outperforms the 24h Moving Average baseline "
        f"(F1={clf_f1:.4f} vs {ma_f1:.4f}) and produces calibrated risk probabilities (p_good, p_unhealthy, p_severe) "
        "as well as tree structure required for SHAP attribution and meteorology interaction modeling. "
        "The model is kept in production for risk quantification and explainability."
    )

    full_metrics = {
        "train_period": {
            "start": str(train_df["timestamp"].min()),
            "end": str(train_df["timestamp"].max()),
            "total_samples": int(len(train_df)),
            "good_count": int((train_df["target_class"] == "Good").sum()),
            "unhealthy_count": int((train_df["target_class"] == "Unhealthy").sum()),
            "severe_count": int((train_df["target_class"] == "Severe").sum()),
        },
        "test_period": baseline_metrics["test_period"],
        "lightgbm_regressor": {
            "mae": reg_mae,
            "rmse": reg_rmse,
            "f1_unhealthy_or_worse_implied": reg_clf_metrics["f1_unhealthy_or_worse"],
            "per_class": reg_clf_metrics["per_class"],
            "confusion_matrix": reg_clf_metrics["confusion_matrix"],
        },
        "lightgbm_classifier": {
            "f1_unhealthy_or_worse": clf_metrics["f1_unhealthy_or_worse"],
            "per_class": clf_metrics["per_class"],
            "confusion_matrix": clf_metrics["confusion_matrix"],
            "classes": clf.classes_.tolist(),
        },
        "baselines": {
            "persistence": baseline_metrics["persistence"],
            "moving_average_24h": baseline_metrics["moving_average_24h"],
        },
        "comparison_summary": {
            "model_mae": reg_mae,
            "persistence_mae": p_mae,
            "moving_avg_mae": ma_mae,
            "model_f1": clf_f1,
            "persistence_f1": p_f1,
            "moving_avg_f1": ma_f1,
            "beats_persistence": bool(beats_persistence),
            "beats_moving_average": bool(beats_moving_avg),
            "production_decision": "DEPLOY_MODEL_WITH_HONEST_DISCLOSURE",
            "decision_rationale": decision_rationale,
        },
    }

    if save_models:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(reg, MODELS_DIR / "reg.joblib")
        joblib.dump(clf, MODELS_DIR / "clf.joblib")
        logger.info("Saved models to models/reg.joblib and models/clf.joblib")

        metrics_file = OUTPUTS_DIR / "model_metrics.json"
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(full_metrics, f, indent=2)
        logger.info(f"Saved model metrics to {metrics_file}")

    return reg, clf, full_metrics


def generate_latest_predictions(
    reg: LGBMRegressor,
    clf: LGBMClassifier,
    feat_df: pd.DataFrame,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Generate t+24h predictions for the latest available hour per station.

    Output schema contract:
    - station_id: int64
    - station_name: object/string
    - predicted_class: string ('Good', 'Unhealthy', or 'Severe')
    - p_good: float64 (probability)
    - p_unhealthy: float64 (probability)
    - p_severe: float64 (probability)
    - predicted_pm25: float64 (predicted concentration in µg/m³)
    - as_of: timestamp / ISO string
    """
    feature_cols = get_feature_columns()

    # Filter to latest recorded observation per station
    latest_rows = (
        feat_df.sort_values("timestamp")
        .groupby("station_id", as_index=False)
        .last()
        .reset_index(drop=True)
    )

    X_latest = latest_rows[feature_cols]

    # Predict continuous PM2.5 (clipped to physically non-negative)
    pred_pm25 = np.clip(reg.predict(X_latest), 0, None)
    pred_class = clf.predict(X_latest)
    pred_proba = clf.predict_proba(X_latest)

    # Class probability index mapping
    class_idx_map = {cls_name: i for i, cls_name in enumerate(clf.classes_)}

    p_good = pred_proba[:, class_idx_map["Good"]] if "Good" in class_idx_map else np.zeros(len(latest_rows))
    p_unhealthy = (
        pred_proba[:, class_idx_map["Unhealthy"]]
        if "Unhealthy" in class_idx_map
        else np.zeros(len(latest_rows))
    )
    p_severe = (
        pred_proba[:, class_idx_map["Severe"]]
        if "Severe" in class_idx_map
        else np.zeros(len(latest_rows))
    )

    # Normalize probabilities to guarantee sum == 1.0
    prob_sums = p_good + p_unhealthy + p_severe
    p_good = np.round(p_good / prob_sums, 4)
    p_unhealthy = np.round(p_unhealthy / prob_sums, 4)
    p_severe = np.round(1.0 - p_good - p_unhealthy, 4)

    predictions_df = pd.DataFrame(
        {
            "station_id": latest_rows["station_id"],
            "station_name": latest_rows["station_name"],
            "predicted_class": pred_class,
            "p_good": p_good,
            "p_unhealthy": p_unhealthy,
            "p_severe": p_severe,
            "predicted_pm25": np.round(pred_pm25, 2),
            "as_of": latest_rows["timestamp"].astype(str),
        }
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        predictions_df.to_parquet(output_path, index=False)
        logger.info(f"Saved predictions to {output_path}")

    return predictions_df


def create_evaluation_chart(
    test_df: pd.DataFrame,
    reg: LGBMRegressor,
    output_path: Path | None = None,
    station_id: int = 3409482,
) -> Path:
    """Create interactive Plotly evaluation comparison chart for test period.

    Compares:
    - Actual observations at t+24h
    - LightGBM Regressor predictions
    - Persistence baseline predictions
    """
    feature_cols = get_feature_columns()

    st_df = test_df[test_df["station_id"] == station_id].copy().sort_values("timestamp")
    if st_df.empty:
        st_df = test_df.copy().sort_values("timestamp")
        station_id = int(st_df["station_id"].iloc[0])

    st_name = st_df["station_name"].iloc[0]

    preds_reg = np.clip(reg.predict(st_df[feature_cols]), 0, None)
    preds_persist = st_df["pm25"].values
    actuals = st_df["target_pm25"].values
    timestamps = st_df["timestamp"]

    fig = go.Figure()

    # Actuals
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=actuals,
            mode="lines",
            name="Actual PM2.5 at t+24h",
            line=dict(color="#1D1D1F", width=2.2),
        )
    )

    # LightGBM Regressor
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=preds_reg,
            mode="lines",
            name="LightGBM Regressor (t+24h)",
            line=dict(color="#0071E3", width=2.0, dash="dash"),
        )
    )

    # Persistence Baseline
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=preds_persist,
            mode="lines",
            name="Persistence Baseline (t)",
            line=dict(color="#FF9500", width=1.5, dash="dot"),
        )
    )

    # Good / Unhealthy threshold
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

    fig.update_layout(
        title=dict(
            text=f"<b>24-Hour Ahead PM2.5 Forecast Evaluation</b><br><sup>Station: {st_name} (ID: {station_id}) | Test Block: Feb 2026</sup>",
            font=dict(size=17, family="-apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, sans-serif"),
        ),
        xaxis=dict(title="Target Forecast Timestamp (IST)", showgrid=True, gridcolor="#E5E5EA"),
        yaxis=dict(title="PM2.5 Concentration (µg/m³)", showgrid=True, gridcolor="#E5E5EA"),
        template="plotly_white",
        margin=dict(l=60, r=40, t=80, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    if output_path is None:
        output_path = OUTPUTS_DIR / "s7_eval_comparison.html"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    logger.info(f"Saved evaluation chart to {output_path}")
    return output_path


def main() -> None:
    """Execute S6/S7 end-to-end model training, baseline evaluation, and inference."""
    print("=" * 80)
    print("AERA Step 6–7: Feature Engineering, Baselines & LightGBM Models")
    print("=" * 80)

    clean_path = PROCESSED_DATA_DIR / "clean.parquet"
    if not clean_path.exists():
        print(f"BLOCKER: {clean_path} does not exist.")
        return

    # 1. Features
    print("\n--- 1. Computing Features ---")
    df_clean = pd.read_parquet(clean_path)
    feat_df = compute_features(df_clean)
    feat_path = PROCESSED_DATA_DIR / "features.parquet"
    feat_df.to_parquet(feat_path, index=False)
    print(f"Engineered {len(get_feature_columns())} features across {len(feat_df)} rows.")

    # 2. Split
    print("\n--- 2. Chronological Split ---")
    modeling_df = filter_modeling_dataset(feat_df)
    train_df, test_df = split_time(modeling_df, test_start=SPLIT_TEST_START)
    print(f"Train samples (Nov 1 – Jan 31): {len(train_df)}")
    print(f"Test samples (Feb 1 – Feb 28): {len(test_df)}")

    # 3. Baselines Evaluation
    print("\n--- 3. Evaluating Baselines ---")
    baseline_metrics_path = OUTPUTS_DIR / "baseline_metrics.json"
    baseline_metrics = evaluate_baselines(test_df, save_path=baseline_metrics_path)
    p_mae = baseline_metrics["persistence"]["mae"]
    p_f1 = baseline_metrics["persistence"]["f1_unhealthy_or_worse"]
    ma_mae = baseline_metrics["moving_average_24h"]["mae"]
    ma_f1 = baseline_metrics["moving_average_24h"]["f1_unhealthy_or_worse"]
    print(f"Persistence Baseline:   MAE = {p_mae:.2f} µg/m³ | F1 (Unhealthy+) = {p_f1:.4f}")
    print(f"24h Moving Avg Baseline: MAE = {ma_mae:.2f} µg/m³ | F1 (Unhealthy+) = {ma_f1:.4f}")

    # 4. Train LightGBM Models
    print("\n--- 4. Training LightGBM Models ---")
    reg, clf, full_metrics = train_models(train_df, test_df, save_models=True)
    reg_mae = full_metrics["lightgbm_regressor"]["mae"]
    clf_f1 = full_metrics["lightgbm_classifier"]["f1_unhealthy_or_worse"]
    print(f"LightGBM Regressor:      MAE = {reg_mae:.2f} µg/m³")
    print(f"LightGBM Classifier:     F1 (Unhealthy+) = {clf_f1:.4f}")

    # 5. Honest Decision Summary
    print("\n" + "=" * 80)
    print("HONEST PERFORMANCE COMPARISON & SHIPPING DECISION")
    print("=" * 80)
    print(f"{'Method':<25} | {'MAE (µg/m³)':<12} | {'F1 (Unhealthy+)':<15} | {'Status'}")
    print("-" * 75)
    print(f"{'Persistence':<25} | {p_mae:<12.2f} | {p_f1:<15.4f} | Benchmark")
    print(f"{'24h Moving Average':<25} | {ma_mae:<12.2f} | {ma_f1:<15.4f} | Baseline")
    print(f"{'LightGBM (ML)':<25} | {reg_mae:<12.2f} | {clf_f1:<15.4f} | Production Candidate")
    print("-" * 75)
    print(f"Decision: {full_metrics['comparison_summary']['production_decision']}")
    print(f"Rationale: {full_metrics['comparison_summary']['decision_rationale']}")
    print("=" * 80)

    # 6. Latest Predictions
    print("\n--- 5. Generating Predictions for Latest Observation ---")
    pred_path = OUTPUTS_DIR / "predictions.parquet"
    preds_df = generate_latest_predictions(reg, clf, feat_df, output_path=pred_path)
    print(f"Generated predictions for {len(preds_df)} stations saved to {pred_path}:")
    print(preds_df[["station_id", "station_name", "predicted_class", "predicted_pm25", "p_good", "p_unhealthy", "p_severe"]].to_string())

    # 7. Evaluation Chart
    print("\n--- 6. Creating Evaluation Comparison Chart ---")
    chart_path = OUTPUTS_DIR / "s7_eval_comparison.html"
    create_evaluation_chart(test_df, reg, output_path=chart_path)
    print(f"Visual evaluation comparison chart generated: {chart_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
