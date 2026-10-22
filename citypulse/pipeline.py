"""End-to-end data processing, feature engineering, and model training pipeline.

Coordinates the CityPulse execution:
1. Ingestion / Caching: OpenAQ S3 and Open-Meteo weather (or offline cached datasets).
2. QA/QC Cleaning: Outlier flagging, stuck sensor detection, and regular timeline reindexing.
3. Pattern Discovery: Evening peak, calm wind stagnation, and persistent hot spot detection.
4. Feature Engineering: Lags, rolling aggregates, meteorological encodings, and forecast stand-ins.
5. Modeling & Baselines: Persistence, 24h moving average, LightGBM Regressor and Classifier training.
6. Honest Evaluation: Saves metrics, models, and predictions for production use.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import (
    MODELS_DIR,
    OUTPUTS_DIR,
    PROCESSED_DATA_DIR,
    SAMPLE_DATA_DIR,
)
from citypulse.brief import capture_brief_screenshot, generate_brief
from citypulse.clean import clean, compute_quality_summary, generate_clean_comparison_chart
from citypulse.explain import (
    create_driver_chart,
    create_interval_chart,
    explain_predictions,
    train_quantile_regressors,
)
from citypulse.fetch_data import VERIFIED_MUMBAI_STATIONS, fetch_pm25, fetch_weather
from citypulse.features import compute_features, filter_modeling_dataset
from citypulse.patterns import (
    build_station_hour_heatmap,
    calm_wind_episodes,
    evening_peak,
    persistent_worst_stations,
    render_heatmap_chart,
)
from citypulse.recommend import rank_stations
from citypulse.train import (
    SPLIT_TEST_START,
    create_evaluation_chart,
    evaluate_baselines,
    generate_latest_predictions,
    split_time,
    train_models,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(cached: bool = True) -> int:
    """Run the complete CityPulse pipeline end-to-end.

    Parameters
    ----------
    cached : bool
        If True, read committed/cached Parquet datasets offline without external network calls.
        If False, fetch fresh observations from OpenAQ S3 and Open-Meteo APIs.
    """
    t0 = time.time()
    print("=" * 80)
    print(f"CityPulse End-to-End Pipeline [Mode: {'CACHED (Offline)' if cached else 'LIVE (Network)'}]")
    print("=" * 80)

    pm25_raw_path = PROCESSED_DATA_DIR / "pm25_observed.parquet"
    weather_raw_path = PROCESSED_DATA_DIR / "weather_observed.parquet"

    # Step 1: Ingestion / Data Loading
    print("\n[Step 1/5] Ingestion & Raw Observation Verification...")
    if not cached or not pm25_raw_path.exists() or not weather_raw_path.exists():
        if cached:
            # Fallback to sample data if processed is not yet generated
            sample_pm25 = SAMPLE_DATA_DIR / "pm25_sample.parquet"
            sample_weather = SAMPLE_DATA_DIR / "weather_sample.parquet"
            if sample_pm25.exists() and sample_weather.exists():
                print("Using committed offline sample dataset from data/sample/")
                df_pm25 = pd.read_parquet(sample_pm25)
                df_weather = pd.read_parquet(sample_weather)
            else:
                print("Offline datasets not found; triggering network fetch...")
                df_pm25 = fetch_pm25(VERIFIED_MUMBAI_STATIONS, "2025-11-01", "2026-02-28")
                df_weather = fetch_weather(19.0760, 72.8777, "2025-11-01", "2026-02-28")
        else:
            df_pm25 = fetch_pm25(VERIFIED_MUMBAI_STATIONS, "2025-11-01", "2026-02-28")
            df_weather = fetch_weather(19.0760, 72.8777, "2025-11-01", "2026-02-28")
    else:
        print(f"Loading cached observations from {PROCESSED_DATA_DIR}...")
        df_pm25 = pd.read_parquet(pm25_raw_path)
        df_weather = pd.read_parquet(weather_raw_path)

    print(f"Loaded {len(df_pm25)} PM2.5 records across {df_pm25['station_id'].nunique()} stations.")
    print(f"Loaded {len(df_weather)} matching weather records.")

    # Step 2: Cleaning & QA/QC Flagging
    print("\n[Step 2/5] Cleaning, Regularizing Timeline & Quality Flagging...")
    df_clean = clean(df_pm25, df_weather)
    clean_path = PROCESSED_DATA_DIR / "clean.parquet"
    df_clean.to_parquet(clean_path, index=False)

    summary_df = compute_quality_summary(df_clean, days=30)
    summary_path = OUTPUTS_DIR / "quality_summary.parquet"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_parquet(summary_path, index=False)

    # Comparison chart
    chart_clean_path = OUTPUTS_DIR / "s4_clean_comparison.html"
    first_st_id = int(df_clean["station_id"].iloc[0])
    generate_clean_comparison_chart(df_pm25, df_clean, station_id=first_st_id, output_path=chart_clean_path)
    print(f"Cleaned dataset saved: {clean_path} ({len(df_clean)} rows)")
    print(f"Quality summary saved: {summary_path}")

    # Step 3: Pattern Discovery & Heatmap
    print("\n[Step 3/5] Discovering Recurring Operational Patterns...")
    # 90-day window
    window_days = 90
    max_ts = df_clean["timestamp"].max()
    window_start = max_ts - pd.Timedelta(days=window_days)
    df_window = df_clean[df_clean["timestamp"] >= window_start].copy()

    p1 = evening_peak(df_window)
    p2 = calm_wind_episodes(df_window)
    p3 = persistent_worst_stations(df_window)

    patterns_output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
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
    patterns_json_path = OUTPUTS_DIR / "patterns.json"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    patterns_json_path.write_text(json.dumps(patterns_output, indent=2), encoding="utf-8")

    heatmap_df = build_station_hour_heatmap(df_window)
    heatmap_parquet_path = OUTPUTS_DIR / "heatmap.parquet"
    heatmap_df.to_parquet(heatmap_parquet_path, index=False)

    heatmap_html_path = OUTPUTS_DIR / "heatmap.html"
    render_heatmap_chart(heatmap_df, heatmap_html_path)
    print(f"Patterns exported: {patterns_json_path}")
    print(f"Heatmap exported: {heatmap_parquet_path} and {heatmap_html_path}")

    # Step 4: Feature Engineering
    print("\n[Step 4/5] Engineering Temporal & Meteorological Features...")
    feat_df = compute_features(df_clean)
    feat_path = PROCESSED_DATA_DIR / "features.parquet"
    feat_df.to_parquet(feat_path, index=False)
    print(f"Features dataset saved: {feat_path} ({len(feat_df)} rows, {len(feat_df.columns)} cols)")

    # Step 5: Chronological Split, Baselines & Modeling
    print("\n[Step 5/5] Training Models, Evaluating Baselines & Generating Predictions...")
    modeling_df = filter_modeling_dataset(feat_df)
    train_df, test_df = split_time(modeling_df, test_start=SPLIT_TEST_START)

    # Baselines
    baseline_path = OUTPUTS_DIR / "baseline_metrics.json"
    evaluate_baselines(test_df, save_path=baseline_path)

    # Train LightGBM
    reg, clf, full_metrics = train_models(train_df, test_df, save_models=True)

    # Latest predictions
    pred_path = OUTPUTS_DIR / "predictions.parquet"
    preds_df = generate_latest_predictions(reg, clf, feat_df, output_path=pred_path)

    # Evaluation chart
    eval_chart_path = OUTPUTS_DIR / "s7_eval_comparison.html"
    create_evaluation_chart(test_df, reg, output_path=eval_chart_path, station_id=first_st_id)

    # Step 6: Model Explanations & Conformal Prediction Intervals (S8)
    print("\n[Step 6/7] Explaining Risk Drivers & Calibrating Prediction Intervals...")
    q_low, q_high, delta, coverage_info = train_quantile_regressors(train_df, test_df)
    expl_df = explain_predictions(
        clf=clf,
        feat_df=feat_df,
        preds_df=preds_df,
        quality_df=summary_df,
        q_low=q_low,
        q_high=q_high,
        conformal_delta=delta,
        coverage_pct=coverage_info["calibrated_coverage_pct"],
    )
    expl_path = OUTPUTS_DIR / "explanations.parquet"
    expl_df.to_parquet(expl_path, index=False)
    create_driver_chart(expl_df, OUTPUTS_DIR / "s8_shap_drivers.html")
    create_interval_chart(expl_df, OUTPUTS_DIR / "s8_prediction_intervals.html")
    print(f"Explanations saved: {expl_path} ({coverage_info['calibrated_coverage_pct']}% test coverage)")

    # Step 7: Municipal Recommendation Prioritization & Briefing (S9)
    print("\n[Step 7/7] Generating Ranked Interventions & Decision Brief...")
    ranked_df = rank_stations(preds_df, expl_df, top_n=5)
    ranked_path = OUTPUTS_DIR / "ranked_stations.parquet"
    ranked_df.to_parquet(ranked_path, index=False)

    brief_html = OUTPUTS_DIR / "brief.html"
    generate_brief(ranked_df=ranked_df, patterns_data=patterns_output, metrics_data=full_metrics, output_path=brief_html)
    capture_brief_screenshot(brief_html, OUTPUTS_DIR / "brief.png")
    print(f"Ranked actions saved: {ranked_path}")
    print(f"Decision brief saved: {brief_html}")

    elapsed = time.time() - t0
    print("\n" + "=" * 80)
    print(f"PIPELINE COMPLETE in {elapsed:.1f}s")
    print("=" * 80)
    print(f"- Regressor MAE: {full_metrics['lightgbm_regressor']['mae']} ug/m3")
    print(f"- Classifier F1:  {full_metrics['lightgbm_classifier']['f1_unhealthy_or_worse']}")
    print(f"- Persistence MAE: {full_metrics['baselines']['persistence']['mae']} ug/m3")
    print(f"- Persistence F1:  {full_metrics['baselines']['persistence']['f1_unhealthy_or_worse']}")
    print(f"- Production Decision: {full_metrics['comparison_summary']['production_decision']}")
    print(f"- Predictions saved: {pred_path} ({len(preds_df)} stations)")
    print(f"- Briefing generated: {brief_html}")
    print("=" * 80)

    return 0


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="CityPulse End-to-End Pipeline")
    parser.add_argument(
        "--cached",
        action="store_true",
        default=True,
        help="Use committed/cached offline data without network requests (default: True).",
    )
    parser.add_argument(
        "--live",
        dest="cached",
        action="store_false",
        help="Perform live network downloads from OpenAQ S3 and Open-Meteo APIs.",
    )
    args = parser.parse_args()

    exit_code = run_pipeline(cached=args.cached)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
