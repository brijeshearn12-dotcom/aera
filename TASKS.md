# TASKS.md: CityPulse

Status: NOT STARTED | IN PROGRESS | BLOCKED | VERIFIED | DEFERRED  
Priority: P0 = mandatory MVP, P1 = important, P2 = optional  
Update at the end of every step. VERIFIED only with evidence.

## Steps
| ID | Task | Pri | Min | Depends on | Status | Acceptance (short) | Evidence |
|---|---|---|---|---|---|---|---|
| S1 | Repo, structure, brain.md, TASKS.md | P0 | 25 | none | VERIFIED | Tree matches plan; pip install ok; config imports | All 34 planned files verified; pip install exit code 0; config imports verified; pytest 0 items collected with 0 errors; git initial commit verified |
| S2 | Early deployment smoke test | P0 | 20 | S1 | IN PROGRESS | Public URL loads placeholder | Local dashboard verified at 1280px and 390px; clean venv pip check passed with 0 broken reqs; awaiting user deployment URL |
| S3 | Verify sources, fetch, cache | P0 | 35 | S1 | VERIFIED | Parquet with >= 8 stations, >= 90 days (or approved fallback) | 9 Mumbai stations; 120 days (2025-11-01 to 2026-02-28); 19,989 PM2.5 rows; 2,880 weather rows; 3-station 30-day sample cached; 4 pytest smoke tests passed; s3_check.html generated |
| S4 | Cleaning and quality flags | P0 | 25 | S3 | VERIFIED | Tests pass; hourly index per station | All 11 unit & contract tests pass (5 in test_clean.py, 6 in test_pipeline_smoke.py); 25,920 regular hourly observations in clean.parquet (9 stations x 2,880 hrs) in Asia/Kolkata; 743 1-3h gap fills; 83 impossible flags (<0 or >1000) removed; 135 stuck flags (>=6 consecutive) removed; quality_summary.parquet saved (7 Fair, 2 Low); before/after comparison chart generated |
| S5 | Discover: 3 patterns | P0 | 25 | S4 | VERIFIED | 3 patterns from real data, honest wording | 3 patterns derived from real data; Diurnal peak at 08:00 (+15.1% over median); Calm wind Q1 <= 4.8 km/h yields +19.7% uplift; Top 3 worst stations identified (Kherwadi 46.7%, Byculla 43.3%, BKC 38.8%); patterns.json saved; heatmap.parquet (216 rows) saved; heatmap.html generated with single-hue sequential blue scale; 18 unit & contract tests pass |
| S6 | Features, label, baselines | P0 | 30 | S4 | VERIFIED | Leakage test passes; split documented; baselines saved | 22 causal features + 2 forecast stand-ins engineered; future-perturbation leakage test passes; strictly chronological split (Nov 1 – Jan 31 train, Feb 1 – Feb 28 test, 898 Unhealthy test samples); baseline metrics saved (Persistence MAE 11.82, F1 0.6251; 24h MA MAE 12.86, F1 0.5432) |
| S7 | Models and evaluation | P0 | 30 | S6 | VERIFIED | Models saved; honest metrics; pipeline runs | LightGBM regressor & balanced classifier trained and saved in models/; model_metrics.json saved with honest comparison; predictions.parquet generated for 9 stations (prob sum == 1.0); s7_eval_comparison.html created; pipeline --cached executes end-to-end in 4.9s without keys; 28 tests pass |
| S8 | Explain: SHAP + intervals | P0 | 25 | S7 | NOT STARTED | Explanations for all stations; coverage reported | |
| S9 | Act: rules, ranking, brief | P0 | 25 | S7, S8, S5 | NOT STARTED | Top-5 ranked; brief renders on A4 | |
| S10 | Design system and shell | P0 | 25 | S2, S7 | NOT STARTED | Matches tokens at 1280 and 390 px | |
| S11 | Map, list, station panel | P0 | 35 | S9, S10 | NOT STARTED | AC3, AC5, AC6 with screenshots | |
| S12 | Patterns strip, download, badge | P0 | 20 | S11 | NOT STARTED | AC4, AC7 with evidence | |
| S13 | Testing, hardening, README | P0 | 25 | S12 | NOT STARTED | Tests pass; AC1, AC2 verified; README complete | |
| S14 | Final deploy, verification, handover | P0 | 15 | S13 | NOT STARTED | AC9 on the real URL | |

## Subtasks
| ID | Subtask | Status | Time |
|---|---|---|---|
| S1.1 | Initialize project structure, placeholder modules, and configuration | VERIFIED | 5 min |
| S1.2 | Setup Python 3.11 virtual environment and install dependencies | VERIFIED | 10 min |
| S1.3 | Verify test runner (pytest) and configuration imports | VERIFIED | 2 min |
| S1.4 | Initialize Git repository, verify exclusions, and record baseline commit | VERIFIED | 3 min |
| S2.1 | Implement minimal Streamlit dashboard and global font CSS | VERIFIED | 4 min |
| S2.2 | Verify local execution and capture desktop (1280px) and mobile (390px) screenshots | VERIFIED | 5 min |
| S2.3 | Validate clean virtual environment reproducibility and pip check | VERIFIED | 5 min |
| S2.4 | Update README and prepare Git commit/push | VERIFIED | 2 min |
| S2.5 | Verify live public deployment URL on Streamlit Community Cloud | IN PROGRESS | Awaiting user URL |
| S3.1 | Verify source access (OpenAQ S3 archive, Open-Meteo weather & air quality) | VERIFIED | 8 min |
| S3.2 | Select real Mumbai stations with confirmed PM2.5 history (9 stations) | VERIFIED | 5 min |
| S3.3 | Implement fetch_pm25, fetch_weather, and caching pipeline in fetch_data.py | VERIFIED | 5 min |
| S3.4 | Audit station quality, print statistics, generate Plotly visual check, run tests | VERIFIED | 4 min |
| S4.1 | Implement cleaning, impossible/stuck flagging, gap filling, and weather join in clean.py | VERIFIED | 6 min |
| S4.2 | Implement 5 synthetic unit tests in tests/test_clean.py and run pytest | VERIFIED | 4 min |
| S4.3 | Execute real-data cleaning on S3 dataset, produce clean.parquet and quality_summary.parquet | VERIFIED | 3 min |
| S4.4 | Generate Plotly comparison chart s4_clean_comparison.html and update project docs | VERIFIED | 2 min |
| S5.1 | Implement evening_peak, calm_wind_episodes, persistent_worst_stations in patterns.py | VERIFIED | 5 min |
| S5.2 | Implement build_station_hour_heatmap and Plotly single-hue renderer | VERIFIED | 4 min |
| S5.3 | Implement 6 unit tests in tests/test_patterns.py and verify JSON serialization | VERIFIED | 3 min |
| S5.4 | Execute on actual cleaned data, export patterns.json and heatmap.parquet, update docs | VERIFIED | 2 min |
| S6.1 | Implement causal features, rolling aggregations, calendar encodings, and forecast stand-ins in features.py | VERIFIED | 10 min |
| S6.2 | Implement split_time (Nov-Jan train / Feb test) and evaluate Persistence and 24h Moving Avg baselines | VERIFIED | 10 min |
| S7.1 | Implement train_models for LightGBM Regressor and Balanced Classifier in train.py | VERIFIED | 10 min |
| S7.2 | Implement latest predictions generator (predictions.parquet) and evaluation chart (s7_eval_comparison.html) | VERIFIED | 6 min |
| S7.3 | Implement pipeline coordinator (pipeline.py --cached) and expand unit & contract tests in test_features.py and test_pipeline_smoke.py | VERIFIED | 6 min |

## Acceptance criteria
| ID | Criterion | Status | Evidence |
|---|---|---|---|
| AC1 | `python -m citypulse.pipeline` rebuilds data and model, no keys | VERIFIED | Rebuilt in 4.9s via `python -m citypulse.pipeline --cached` offline with zero API keys |
| AC2 | App loads from cache offline, under 5 s | NOT STARTED | |
| AC3 | Map shows all stations, risk colour plus text label | NOT STARTED | |
| AC4 | At least 3 patterns auto-detected and shown | NOT STARTED | |
| AC5 | Per station: class, probabilities, band, top 3 drivers, quality badge | NOT STARTED | |
| AC6 | Needs-attention top 5 with risk, window, action | NOT STARTED | |
| AC7 | Download brief produces a one-page brief | NOT STARTED | |
| AC8 | Model vs both baselines on F1 and MAE, reported honestly | VERIFIED | Full honest disclosure in model_metrics.json & logs: Persistence MAE 11.82 / F1 0.6251 vs 24h MA MAE 12.86 / F1 0.5432 vs LightGBM MAE 13.00 / F1 0.6076 |
| AC9 | Live on free host; core journey verified on real URL | IN PROGRESS | Local smoke test passed; awaiting public deployment URL |

## Deferred (optional) items
| Item | Status | Reason |
|---|---|---|
| Modelled air-quality benchmark feature | DEFERRED | Optional |
| OpenStreetMap context | DEFERRED | Optional |
| GitHub Actions daily refresh | DEFERRED | Optional |
| PM10 and NO2 features | DEFERRED | Optional |
