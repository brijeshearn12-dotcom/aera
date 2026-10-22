# brain.md: CityPulse permanent source of truth

> RULES (Antigravity must follow these every step)  
> 1. Read this file and TASKS.md before starting any step. Update both at the END of every step.  
> 2. Never mark a task VERIFIED until its acceptance criteria have actually passed. Paste the real evidence.  
> 3. Never invent data, URLs, metrics, screenshots or test results. If something cannot be done, say so.  
> 4. Never expose secrets, disable security checks, or weaken/hide failing tests.  
> 5. Do not create a file that is not in section 3. If a new file is genuinely needed, add it to section 3 in the same step with the reason in section 7.  
> 6. Stop after each step and wait for the user's approval.  

## Status system
NOT STARTED | IN PROGRESS | BLOCKED | VERIFIED | DEFERRED
- VERIFIED = acceptance criteria passed, with evidence recorded in section 10 or 11.
- BLOCKED = needs a fix, account or approval. Must have a blocker record in section 12.
- DEFERRED = consciously postponed. Must have a reason in section 7.

## 1. Requirements and scope
- Product: CityPulse, a decision-support app for a Mumbai municipal pollution-control officer.
- Daily decision: where to focus dust control, advisories and inspections in the next 24 hours.
- Core loop: Discover, Predict, Explain, Act.
- Classes (PM2.5 ug/m3): Good <= 60, Unhealthy > 60 to 250, Severe > 250.
- In scope: one city, station level, 24h forecast, explanation, rule-based actions, one-page brief.
- Out of scope: street-level prediction, traffic/industry data, public alerts, any paid API or LLM.
- Acceptance criteria AC1 to AC9: see TASKS.md.
- Success measure: F1 on Unhealthy-or-worse on a held-out block, beating persistence and 24h moving average.
- S2 scope: Minimal Streamlit dashboard and deployment readiness smoke test. Displays title, subtitle, version (v0.1.0), prominent placeholder warning, and mock illustrative station table. No live sensors, no data fetching, no ML models.

## 2. Stack and architecture
- Python 3.11, pandas, pyarrow, scikit-learn, LightGBM, statsmodels, SHAP, Streamlit, streamlit-folium, Folium, Plotly, Jinja2, requests, pytest, joblib.
- Host: Streamlit Community Cloud (backup: Hugging Face Spaces, Streamlit SDK).
- Data flow: sources -> fetch_data -> clean -> processed parquet -> patterns / features -> train -> explain -> recommend -> outputs parquet/json -> app.py + brief.py.
- The app reads only data/outputs and data/sample. It never trains or fetches.
- S2 implementation: Single lightweight entrypoint `app.py` injecting global CSS font from `ui/styles.css` using `st.markdown`, rendering native Streamlit headers, warning callouts, and dataframes.

## 3. Directory tree
```text
citypulse/
├── .env.example
├── .gitignore
├── README.md
├── TASKS.md
├── brain.md
├── requirements.txt
├── runtime.txt
├── app.py
├── config.py
├── .streamlit/
│   └── config.toml
├── citypulse/
│   ├── __init__.py
│   ├── fetch_data.py
│   ├── clean.py
│   ├── patterns.py
│   ├── features.py
│   ├── train.py
│   ├── explain.py
│   ├── recommend.py
│   ├── brief.py
│   └── pipeline.py
├── ui/
│   ├── styles.css
│   ├── components.py
│   ├── map_view.py
│   └── charts.py
├── templates/
│   └── brief.html.j2
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   ├── sample/
│   │   └── .gitkeep
│   ├── processed/
│   │   └── .gitkeep
│   └── outputs/
│       └── .gitkeep
├── models/
│   └── .gitkeep
└── tests/
    ├── test_clean.py
    ├── test_patterns.py
    ├── test_features.py
    ├── test_recommend.py
    └── test_pipeline_smoke.py
```

## 4. Design tokens and UI conventions
- Font: -apple-system, BlinkMacSystemFont, 'SF Pro Text', Inter, system-ui, sans-serif
- Colours: bg #FFFFFF, surface #F5F5F7, text #1D1D1F, secondary #6E6E73, hairline #D2D2D7, accent #0071E3, risk green #34C759 / amber #FF9500 / red #FF3B30
- Type scale 34/22/17/15/13. Spacing 4/8/12/16/24/32/48. Radius 12 cards, 8 inputs, 999 pills. Shadow 0 1px 3px rgba(0,0,0,0.08).
- Rules: risk colours only for risk; colour never the only signal (always a text label); max 3 charts on screen; every number has a one-line plain explanation; no gradients or glass; motion 150-200ms ease-out; respect reduced motion.
- Breakpoints: <768 stacked; 768-1100 map above list; >1100 60/40.
- Amber text on white fails contrast: amber for markers/borders only, dark text on a tinted pill.

## 5. Data models and API contracts
(Filled as each step defines a schema. Each schema is a contract; later steps must not change it silently.)
- raw/processed PM2.5 (S3):
  - File: `data/processed/pm25_observed.parquet`
  - Columns:
    * `timestamp_utc`: datetime64[ns, UTC] — Timezone-aware UTC observation time
    * `timestamp_ist`: datetime64[ns, Asia/Kolkata] — Corresponding IST observation time
    * `station_id`: int64 — OpenAQ numeric location identifier
    * `station_name`: object / string — Provider station name (e.g. "Bandra Kurla Complex, Mumbai - MPCB")
    * `lat`: float64 — Station latitude coordinate
    * `lon`: float64 — Station longitude coordinate
    * `pm25`: float64 — Real hourly mean concentration (derived from available 15-min telemetry)
    * `units`: object / string — Measurement unit (`µg/m³`)
    * `source`: object / string — Source provenance ("OpenAQ S3 Archive / CPCB-MPCB")
    * `raw_obs_count`: int64 — Number of raw 15-min telemetry readings in the hour
  - Missing values: Genuine missing hours are preserved as absent rows; no interpolation or artificial zero-filling in S3.
- processed Weather (S3):
  - File: `data/processed/weather_observed.parquet`
  - Columns:
    * `timestamp_utc`: datetime64[ns, UTC] — Timezone-aware UTC timestamp
    * `timestamp_ist`: datetime64[ns, Asia/Kolkata] — Corresponding IST timestamp
    * `lat`: float64 — Mumbai centroid latitude (19.0760)
    * `lon`: float64 — Mumbai centroid longitude (72.8777)
    * `temperature`: float64 — 2m air temperature (°C)
    * `relative_humidity`: float64 — 2m relative humidity (%)
    * `rainfall`: float64 — Precipitation (mm)
    * `wind_speed`: float64 — 10m wind speed (km/h)
    * `wind_direction`: float64 — 10m wind direction (degrees)
    * `boundary_layer_height`: float64 — Boundary layer height (m)
    * `source`: object / string — "Open-Meteo ERA5 / Historical Archive"
- clean.parquet (S4):
  - File: `data/processed/clean.parquet`
  - Total records: 25,920 regular hourly observations (9 stations x 2,880 hours, 2025-11-01 00:30 to 2026-02-28 23:30 IST)
  - Timezone: `Asia/Kolkata` (strictly regular 1-hour step, 0 duplicate timestamps)
  - Columns:
    * `timestamp`: datetime64[ns, Asia/Kolkata] — Regular hourly observation timestamp in local IST
    * `station_id`: int64 — OpenAQ numeric station identifier
    * `station_name`: object / string — Official monitoring station name
    * `lat`: float64 — Station latitude coordinate
    * `lon`: float64 — Station longitude coordinate
    * `pm25`: float64 — Cleaned PM2.5 concentration in µg/m³ (NaN for unfillable gaps, stuck runs, or impossible values)
    * `pm25_filled`: bool — True if the value was filled via time interpolation (1–3h transmission gap)
    * `flag_gap`: bool — True if this was an unrecorded transmission slot in raw sensor telemetry
    * `flag_stuck`: bool — True if part of a run of >=6 consecutive identical valid measurements (set to NaN)
    * `flag_impossible`: bool — True if raw reading was < 0 or > 1000 µg/m³ (set to NaN)
    * `temperature`: float64 — 2m air temperature (°C) joined from Open-Meteo
    * `relative_humidity`: float64 — 2m relative humidity (%) joined from Open-Meteo
    * `rainfall`: float64 — Precipitation (mm) joined from Open-Meteo
    * `wind_speed`: float64 — 10m wind speed (km/h) joined from Open-Meteo
    * `wind_direction`: float64 — 10m wind direction (degrees) joined from Open-Meteo
    * `boundary_layer_height`: float64 — Boundary layer height (m) joined from Open-Meteo
  - QA/QC & Missing-Value Policy:
    1. Deduplication on (station_id, timestamp).
    2. Range check: values < 0 or > 1000 µg/m³ flagged `flag_impossible=True` and set to NaN.
    3. Flatline check: runs of >= 6 consecutive identical valid values flagged `flag_stuck=True` and set to NaN.
    4. Reindexing to continuous hourly grid: unrecorded slots flagged `flag_gap=True`.
    5. Gap interpolation: only transmission gaps (`flag_gap=True`) of 1–3 consecutive hours bounded by valid observations are interpolated via time interpolation (`pm25_filled=True`).
    6. Extended gaps (> 3 hours) and invalid telemetry (impossible or stuck) strictly remain missing (`pm25=NaN`, `pm25_filled=False`). No artificial zero-filling.
    7. Weather join: exact 1-to-1 left join on hourly timestamp; unavailable weather hours remain missing (NaN) without fabrication.
- quality_summary.parquet (S4):
  - File: `data/outputs/quality_summary.parquet`
  - Columns:
    * `station_id`: int64 — Station identifier
    * `station_name`: object / string — Station name
    * `valid_hours`: int64 — Count of non-null PM2.5 hours in the latest 30-day window (720 expected slots)
    * `total_hours`: int64 — Total expected hourly slots in 30 days (720)
    * `data_quality_pct`: float64 — Valid-hour percentage (valid_hours / total_hours * 100)
    * `quality_label`: object / string — Standard quality tier (Good >= 90%, Fair 70–90%, Low < 70%)
    * `notes`: object / string — Explicit documentation of any historical coverage shortfall
  - Actual results (latest 30 days: 2026-01-30 to 2026-02-28):
    * Ghatkopar: 88.1% (Fair)
    * Kherwadi_Bandra East: 87.4% (Fair)
    * Mindspace-Malad West: 87.2% (Fair)
    * Shivaji Nagar: 86.9% (Fair)
    * Bandra Kurla Complex: 81.8% (Fair)
    * Chembur: 80.7% (Fair)
    * Byculla: 74.6% (Fair)
    * Kandivali West: 66.0% (Low)
    * Sewri: 49.4% (Low)
- patterns.json / heatmap.parquet (S5):
  - File: `data/outputs/patterns.json`
  - Structure:
    * `generated_at_utc`: ISO-8601 UTC timestamp
    * `analysis_window`: `start`, `end`, `days` (90 days: 2025-11-30 to 2026-02-28), `total_observations` (14,730 valid obs)
    * `patterns.evening_peak`: `title`, `sentence`, `peak_hour` (8), `peak_median` (57.8 µg/m³), `overall_median` (50.2 µg/m³), `percentage_difference` (+15.1%), `sample_size` (14,730), `data_window`, `weak` (False)
    * `patterns.calm_wind_episodes`: `title`, `sentence`, `q1_wind_speed` (4.8 km/h), `episode_hours` (433 hrs), `calm_mean_pm25` (58.9 µg/m³), `other_mean_pm25` (49.2 µg/m³), `percentage_difference` (+19.7%), `sample_size` (14,730), `data_window`, `weak` (False)
    * `patterns.persistent_worst_stations`: `title`, `sentence`, `threshold_ug_m3` (60.0), `top_stations` (ranked list: Kherwadi 46.7%, Byculla 43.3%, BKC 38.8%), `sample_size` (14,730), `data_window`, `weak` (False)
  - File: `data/outputs/heatmap.parquet`
  - Schema:
    * `station_id`: int64 — Station ID
    * `station_name`: object / string — Station name
    * `hour`: int64 — Hour of day (0..23 in Asia/Kolkata)
    * `median_pm25`: float64 — Median PM2.5 concentration for this station-hour
  - Total records: 216 rows (9 stations x 24 hours), rendered in `data/outputs/heatmap.html` using a single-hue sequential blue scale (`Blues`).
- feature list, target definition, split rule, baseline metrics (S6):
  - File: `data/processed/features.parquet`
  - 22 Predictor Features:
    * PM2.5 Lags: `pm25`, `pm25_lag_1`, `pm25_lag_3`, `pm25_lag_6`, `pm25_lag_12`, `pm25_lag_24`
    * PM2.5 Rolling: `pm25_roll_mean_6h`, `pm25_roll_max_6h`, `pm25_roll_mean_24h`, `pm25_roll_max_24h`
    * Calendar: `hour` (0..23), `weekday` (0..6), `month` (1..12)
    * Meteorology: `wind_speed`, `sin_wind_dir`, `cos_wind_dir`, `temperature`, `relative_humidity`, `rainfall_sum_24h`, `boundary_layer_height`
    * Forecast Stand-ins: `forecast_wind_speed_mean_24h`, `forecast_rainfall_sum_24h` (mean/sum over [t+1h, t+24h] historical weather as NWP proxies)
  - Target Definitions:
    * `target_pm25`: Continuous PM2.5 concentration at t+24h
    * `target_class`: 3-tier risk tier (Good <=60, Unhealthy >60–250, Severe >250 µg/m³)
  - Chronological Split Rule:
    * Train: 2025-11-01 00:30 to 2026-01-31 23:30 IST (14,551 valid modeling samples; Good: 9,004, Unhealthy: 5,478, Severe: 69)
    * Test: 2026-02-01 00:30 to 2026-02-28 23:30 IST (3,654 valid modeling samples; Good: 2,756, Unhealthy: 898, Severe: 0)
    * Unhealthy test sample count: 898 (well above the ~30 minimum requirement)
  - Baseline Metrics (`data/outputs/baseline_metrics.json`):
    * Persistence (carried forward t to t+24h): MAE = 11.82 µg/m³, F1 (Unhealthy+) = 0.6251
    * 24h Moving Average: MAE = 12.86 µg/m³, F1 (Unhealthy+) = 0.5432
- model_metrics.json, predictions.parquet (S7):
  - File: `data/outputs/model_metrics.json`
    * LightGBM Regressor: MAE = 13.00 µg/m³, RMSE = 17.58 µg/m³
    * LightGBM Balanced Classifier: F1 (Unhealthy+) = 0.6076 (Precision = 0.5401, Recall = 0.6949 for Unhealthy)
    * Complete comparison table, per-class metrics, confusion matrices for LightGBM, Persistence, and 24h Moving Average
    * Production decision: `DEPLOY_MODEL_WITH_HONEST_DISCLOSURE`
  - File: `data/outputs/predictions.parquet`
    * Columns: `station_id` (int64), `station_name` (string), `predicted_class` (string), `p_good` (float64), `p_unhealthy` (float64), `p_severe` (float64), `predicted_pm25` (float64), `as_of` (string)
    * Total rows: 9 stations (latest available hour 2026-02-28 23:30 IST)
    * Probability sum: strictly 1.0 across all stations
  - File: `data/outputs/s7_eval_comparison.html`
    * Plotly interactive time-series comparison chart of Actuals vs LightGBM vs Persistence on test set
- explanations.parquet (S8):
  - File: `data/outputs/explanations.parquet`
  - Columns:
    * `station_id`: int64 — Station identifier
    * `station_name`: object / string — Station name
    * `predicted_class`: object / string — Predicted risk class ('Good', 'Unhealthy', 'Severe')
    * `predicted_pm25`: float64 — Point forecast for t+24h in µg/m³
    * `driver_1_text`: object / string — Plain-language phrase for top SHAP feature
    * `driver_1_dir`: object / string — Direction ('raises risk' or 'lowers risk')
    * `driver_2_text`: object / string — Plain-language phrase for second feature
    * `driver_2_dir`: object / string — Direction
    * `driver_3_text`: object / string — Plain-language phrase for third feature
    * `driver_3_dir`: object / string — Direction
    * `lower`: float64 — Conformal-calibrated 10th percentile bound in µg/m³ (clamped >= 0 and <= point forecast)
    * `upper`: float64 — Conformal-calibrated 90th percentile bound in µg/m³ (clamped >= point forecast)
    * `quality_label`: object / string — Telemetry quality tier ('Good', 'Fair', 'Low')
    * `notes`: object / string — Plain-language explanation of interval calibration and containment clamping
  - Coverage: 80.16% empirical test coverage achieved on untouched February 2026 test block (via conformal delta = 4.67 µg/m³).
- ranked_stations.parquet (S9):
  - File: `data/outputs/ranked_stations.parquet`
  - Columns:
    * `rank`: int64 — Priority rank (1 to 5)
    * `station_id`: int64 — Monitoring station identifier
    * `station_name`: object / string — Station name
    * `predicted_class`: object / string — Forecast risk tier
    * `predicted_pm25`: float64 — Forecast PM2.5 in µg/m³
    * `p_unhealthy`: float64 — Probability of Unhealthy risk
    * `p_severe`: float64 — Probability of Severe risk
    * `severity_weight`: float64 — Explicit priority multiplier (Severe=2.0, Unhealthy=1.5, Good=1.0 + 0.5*p_unh + 1.0*p_sev)
    * `risk_score`: float64 — Priority score: (p_unhealthy + p_severe) * severity_weight
    * `time_window`: object / string — Targeted intervention window ("Next 24 hours (diurnal peak 08:00 IST)")
    * `action`: object / string — Deterministic rule-based municipal intervention action
    * `warning`: object / string — Explicit telemetry alert (e.g. "[ALERT] Low historical telemetry coverage (<70%)")
    * `quality_label`: object / string — 'Good', 'Fair', or 'Low'
    * `lower`: float64 — Lower 80% interval bound
    * `upper`: float64 — Upper 80% interval bound
    * `primary_driver`: object / string — Plain-language top feature driver with direction
- brief.html / brief.png (S9):
  - File: `data/outputs/brief.html` and `data/outputs/brief.png`
  - Format: Single-page A4 printable municipal decision brief (white background, print-specific CSS, 10mm margins).
  - Sections:
    1. Operational Header (Forecast Date, Horizon, Decision Cycle).
    2. Summary Statistics (Total stations, At-risk count, Citywide median forecast, Conformal coverage).
    3. Top-5 Prioritized Station Interventions Table.
    4. Recurring Operational Pollution Patterns (Diurnal peak, Calm-wind stagnation, Persistent corridors).
    5. Predictive Model vs. Baseline Evaluation Table (LightGBM, Persistence, 24h Moving Avg).
    6. Governance, Provenance & Known Limitations Box.

## 6. Environment variables (no secrets exist in this project)
| Name | Example | Purpose |
|---|---|---|
| CITY | Mumbai | Documented default; real value lives in config.py |
| DATA_MODE | cached | cached = read committed data, live = refetch |

Hosting needs no secrets. For S2, no secrets or API keys are required.

## 7. Decisions log (date/time, step, decision, reason)
| When | Step | Decision | Reason |
|---|---|---|---|
| (start) | Plan | City = Mumbai | Chosen by user |
| (start) | Plan | Streamlit + Parquet, no backend | Fastest, keyless, free |
| (start) | Plan | Host = Streamlit Community Cloud, backup HF Spaces | Free, simple |
| (start) | Plan | D5: 24h chart = last 24h actuals + forecast point with band, not an invented hourly curve | Models produce one t+24h value |
| (start) | Plan | D6: weather "forecast" features use historical data as a stand-in | No forecast archive; disclose in README |
| 2026-10-22 | S1 | Installed Python 3.11.9 via winget (`--scope user`) | Python 3.11 environment required for reproducibility and parity |
| 2026-10-22 | S1 | Direct dependencies pinned strictly to stable releases | Ensure reproducible builds across local and cloud environments |
| 2026-10-22 | S1 | Directory `.gitkeep` files force-tracked for ignored folders | Allows keeping empty data/raw and models directories tracked while ignoring contents |
| 2026-10-22 | S2 | `ui/styles.css` path resolved via `Path(__file__).parent / "ui" / "styles.css"` with try-except fallback | Prevents hardcoded paths and handles missing file gracefully |
| 2026-10-22 | S2 | Validated dependency reproducibility in clean external venv `.citypulse-verify-venv` | Proves environment rebuildability; `pip check` confirmed 0 broken reqs |
| 2026-10-22 | S3 | Ingest real PM2.5 from OpenAQ S3 public archive (`records/csv.gz/locationid=...`) | OpenAQ REST API v1/v2 retired (410), v3 requires API key (401), but public S3 bucket is accessible anonymously via HTTPS (200) |
| 2026-10-22 | S3 | Selected 9 verified Mumbai stations covering winter Nov 2025 – Feb 2026 (120 days) | Exceeds minimum criteria (>=8 stations, >=90 days); all located in Mumbai proper |
| 2026-10-22 | S3 | Sourced 6 matching weather variables from Open-Meteo Historical Archive | Keyless, CC BY 4.0, includes genuine `boundary_layer_height` (2,880 hourly rows) |
| 2026-10-22 | S3 | Cached 3-station 30-day genuine sample in `data/sample/` with metadata.json | Fully reproducible offline testing without committing raw provider downloads |
| 2026-10-22 | S4 | Reindex to canonical regular hourly grid in `Asia/Kolkata` with strictly regular 1h step | Eliminates duplicate timestamps and aligns all 9 stations on a common decision timeline |
| 2026-10-22 | S4 | Enforce strict QA/QC ordering: impossible (<0, >1000) & stuck (>=6 run) -> reindex -> 1-3h gap fill | Ensures sensor faults (negative values, extreme spikes, flatlines) are never interpolated as valid |
| 2026-10-22 | S4 | Left join weather on exact hourly timestamp with deduplication guard | Guarantees strictly 1-to-1 join without many-to-many row multiplication |
| 2026-10-22 | S5 | Use 90-day winter baseline window (2025-11-30 to 2026-02-28) for pattern discovery | Captures seasonal winter stagnation and diurnal dynamics across 14,730 valid records |
| 2026-10-22 | S5 | Dynamic peak hour detection with honesty guard | Peak identified at 08:00 IST (+15.1% over median); calm wind Q1 <= 4.8 km/h yields +19.7% uplift; neither marked weak |
| 2026-10-22 | S5 | Single-hue sequential blue scale (`Blues`) for diurnal heatmap | Complies with UI design tokens and contrast standards; exported to `heatmap.html` |
| 2026-10-22 | S6 | 4-week chronological test split (February 2026, 3,654 samples, 898 Unhealthy) | Completely eliminates data leakage while providing ample sample size (>30 required) |
| 2026-10-22 | S6 | Historical weather as next-24-hour forecast stand-in | Acknowledged limitation; proxies NWP operational inputs for wind speed and rainfall |
| 2026-10-22 | S7 | Model kept in production with honest disclosure | Persistence achieves lower MAE (11.82 vs 13.00) due to diurnal autocorrelation; LightGBM beats 24h Moving Avg on F1 (0.6076 vs 0.5432) and is necessary for probabilistic risk tiers and SHAP |
| 2026-10-22 | S7 | Probability normalization constraint enforced | Guarantees p_good + p_unhealthy + p_severe == 1.0 strictly for downstream UI stability |
| 2026-10-22 | S8 | Conformal widening on validation block (delta = 4.67 µg/m³) | Raw quantile regressor coverage was 70.83%; conformal widening achieved 80.16% test coverage |
| 2026-10-22 | S8 | Point forecast interval containment clamping | Guarantees lower <= point_forecast <= upper and lower >= 0 physically; flagged in notes |
| 2026-10-22 | S9 | Explicit severity weight formula for station ranking | Severity weight scales priority without secretly altering scores based on data quality |
| 2026-10-22 | S9 | Low telemetry quality surfaced as operational warning | Surfaced as explicit alert ([ALERT] Low telemetry coverage) rather than a hidden score penalty |
| 2026-10-22 | S10 | Flat design system tokens (WCAG AA >= 4.5:1 contrast) | Strict exclusion of gradients, glass effects, or unreadable tint-on-white text combinations |
| 2026-10-22 | S10 | 60/40 responsive shell layout with media query stacking | Stacks columns below 768px for clean mobile rendering while preserving 60/40 desktop grid |

### Phase A — Data Access Verification Report

| Source | Actual endpoint | HTTP result | Authentication | Coverage/result | Terms |
|---|---|---|---|---|---|
| OpenAQ API v1/v2 | `https://api.openaq.org/v2/locations?city=Mumbai` | 410 Gone | None | Endpoints retired; instructs migration to v3 | [OpenAQ Legal](https://openaq.org/about/legal/) |
| OpenAQ API v3 | `https://api.openaq.org/v3/locations` | 401 Unauthorized | API Key (`X-API-Key`) | Free registration required for REST endpoint | [OpenAQ Terms](https://docs.openaq.org/docs/terms-of-use) |
| OpenAQ S3 Public Archive | `https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid={id}/...` | 200 OK | Anonymous / None | 9 Mumbai stations, 2025-11-01 to 2026-02-28, 19,989 hourly records | [AWS Open Data](https://registry.opendata.aws/openaq/) / [OpenAQ Legal](https://openaq.org/about/legal/) |
| Open-Meteo Weather Archive | `https://archive-api.open-meteo.com/v1/archive` | 200 OK | Anonymous / None | 2,880 hourly rows (temp, RH, rain, wind spd/dir, boundary layer height) | [Open-Meteo Terms](https://open-meteo.com/en/terms) (CC BY 4.0) |
| Open-Meteo Air Quality | `https://air-quality-api.open-meteo.com/v1/air-quality` | 200 OK | Anonymous / None | Modelled PM2.5 available (2,880 rows); kept separate, not merged into observations | [Open-Meteo Terms](https://open-meteo.com/en/terms) (CC BY 4.0) |

## 8. Files created or modified (step, file, created/modified, one-line purpose)
- S1 | `citypulse/.env.example` | created | Example environment variable template
- S1 | `citypulse/.gitignore` | created | Git ignore rules for venv, caches, raw data, models
- S1 | `citypulse/README.md` | created | Project documentation and setup instructions
- S1 | `citypulse/TASKS.md` | created | 14-step task tracker and acceptance criteria
- S1 | `citypulse/brain.md` | created | Project source of truth and state tracking
- S1 | `citypulse/requirements.txt` | created | Pinned direct dependencies
- S1 | `citypulse/runtime.txt` | created | Python 3.11 runtime specification
- S1 | `citypulse/config.py` | created | Configuration constants and Path constants
- S1 | `citypulse/app.py` | created | Streamlit application entry point placeholder
- S1 | `citypulse/.streamlit/config.toml` | created | Streamlit light theme styling configuration
- S1 | `citypulse/citypulse/__init__.py` | created | CityPulse Python package entry
- S1 | `citypulse/citypulse/fetch_data.py` | created | Data fetching placeholder module
- S1 | `citypulse/citypulse/clean.py` | created | Data cleaning and validation placeholder module
- S1 | `citypulse/citypulse/patterns.py` | created | Pattern analysis placeholder module
- S1 | `citypulse/citypulse/features.py` | created | Feature engineering placeholder module
- S1 | `citypulse/citypulse/train.py` | created | Model training placeholder module
- S1 | `citypulse/citypulse/explain.py` | created | Model explanation placeholder module
- S1 | `citypulse/citypulse/recommend.py` | created | Recommendation engine placeholder module
- S1 | `citypulse/citypulse/brief.py` | created | Briefing generation placeholder module
- S1 | `citypulse/citypulse/pipeline.py` | created | End-to-end pipeline coordinator placeholder module
- S1 | `citypulse/ui/styles.css` | created | Custom CSS stylesheet placeholder
- S1 | `citypulse/ui/components.py` | created | UI reusable components placeholder module
- S1 | `citypulse/ui/map_view.py` | created | Geospatial map rendering placeholder module
- S1 | `citypulse/ui/charts.py` | created | Charts rendering placeholder module
- S1 | `citypulse/templates/brief.html.j2` | created | Jinja2 briefing template placeholder
- S1 | `citypulse/data/raw/.gitkeep` | created | Directory placeholder
- S1 | `citypulse/data/sample/.gitkeep` | created | Directory placeholder
- S1 | `citypulse/data/processed/.gitkeep` | created | Directory placeholder
- S1 | `citypulse/data/outputs/.gitkeep` | created | Directory placeholder
- S1 | `citypulse/models/.gitkeep` | created | Directory placeholder
- S1 | `citypulse/tests/test_clean.py` | created | Cleaning test placeholder module
- S1 | `citypulse/tests/test_features.py` | created | Features test placeholder module
- S1 | `citypulse/tests/test_recommend.py` | created | Recommendation test placeholder module
- S1 | `citypulse/tests/test_pipeline_smoke.py` | created | Smoke test placeholder module
- S2 | `citypulse/app.py` | modified | Minimal Streamlit dashboard with title, version, warning, and mock table
- S2 | `citypulse/ui/styles.css` | modified | Added standard font family rule
- S2 | `citypulse/README.md` | modified | Added comprehensive local run and Streamlit Community Cloud deployment guide
- S2 | `citypulse/TASKS.md` | modified | Updated S2 tracking to IN PROGRESS awaiting cloud deployment URL
- S2 | `citypulse/brain.md` | modified | Updated S2 state, screenshots, and test outcomes
- S3 | `citypulse/citypulse/fetch_data.py` | modified | Real PM2.5 (OpenAQ S3) and weather (Open-Meteo) ingestion and caching pipeline
- S3 | `citypulse/tests/test_pipeline_smoke.py` | modified | Added data contract tests for PM2.5, weather, sample, and Plotly visual check
- S3 | `citypulse/data/processed/pm25_observed.parquet` | created | 19,989 real hourly PM2.5 records across 9 Mumbai stations (120 days)
- S3 | `citypulse/data/processed/weather_observed.parquet` | created | 2,880 hourly weather records with 6 variables for Mumbai (120 days)
- S3 | `citypulse/data/sample/pm25_sample.parquet` | created | 3-station 30-day real PM2.5 sample dataset (1,936 records)
- S3 | `citypulse/data/sample/weather_sample.parquet` | created | 30-day matching weather sample dataset (720 records)
- S3 | `citypulse/data/sample/metadata.json` | created | Metadata, provenance, coordinates, and license information for cached sample
- S3 | `citypulse/data/outputs/s3_check.html` | created | Plotly time-series quality verification chart for BKC station
- S3 | `citypulse/brain.md` | modified | Updated S3 contracts, decisions, command history, and test logs
- S3 | `citypulse/TASKS.md` | modified | Marked S3 VERIFIED with exact acceptance metrics
- S4 | `citypulse/citypulse/clean.py` | modified | Implemented cleaning, quality flagging, weather join, and quality summary
- S4 | `citypulse/tests/test_clean.py` | modified | Implemented 5 contract unit tests using synthetic fixtures
- S4 | `citypulse/tests/test_pipeline_smoke.py` | modified | Added clean and quality summary schema tests
- S4 | `citypulse/data/processed/clean.parquet` | created | 25,920 cleaned hourly observations (9 stations x 2,880 hrs)
- S4 | `citypulse/data/outputs/quality_summary.parquet` | created | 30-day quality metrics per station (7 Fair, 2 Low)
- S4 | `citypulse/data/outputs/s4_clean_comparison.html` | created | Plotly before/after comparison chart for BKC station
- S4 | `citypulse/brain.md` | modified | Updated S4 contracts, decisions, commands, and test logs
- S4 | `citypulse/TASKS.md` | modified | Marked S4 VERIFIED with evidence
- S5 | `citypulse/citypulse/patterns.py` | modified | Implemented evening_peak, calm_wind_episodes, persistent_worst_stations, and heatmap builder
- S5 | `citypulse/tests/test_patterns.py` | created | Unit test suite for pattern discovery, math, weak flags, and ranking
- S5 | `citypulse/tests/test_pipeline_smoke.py` | modified | Added pattern and heatmap contract smoke tests
- S5 | `citypulse/data/outputs/patterns.json` | created | Exported 3 operational patterns with plain-language sentences and metrics
- S5 | `citypulse/data/outputs/heatmap.parquet` | created | 216-row station-by-hour median PM2.5 dataset
- S5 | `citypulse/data/outputs/heatmap.html` | created | Single-hue sequential blue scale diurnal heatmap visualization
- S5 | `citypulse/brain.md` | modified | Updated S5 contracts, decisions, command history, and test logs
- S5 | `citypulse/TASKS.md` | modified | Marked S5 VERIFIED with exact acceptance metrics
- S6 | `citypulse/citypulse/features.py` | modified | Engineered 22 predictor features, forecast stand-ins, and target classifications
- S6 | `citypulse/tests/test_features.py` | modified | Unit test suite testing causal leakage prevention, temporal splits, and thresholds
- S6 | `citypulse/data/processed/features.parquet` | created | 25,920 engineered feature records (18,205 valid modeling rows)
- S6 | `citypulse/data/outputs/baseline_metrics.json` | created | Evaluation of Persistence (MAE 11.82, F1 0.6251) and 24h MA (MAE 12.86, F1 0.5432)
- S7 | `citypulse/citypulse/train.py` | modified | LightGBM Regressor and Classifier training, evaluation, inference, and chart generator
- S7 | `citypulse/citypulse/pipeline.py` | modified | End-to-end pipeline coordinator supporting --cached offline execution in 4.9s
- S7 | `citypulse/tests/test_pipeline_smoke.py` | modified | Added 5 contract tests for features, models, metrics, predictions, and evaluation chart
- S7 | `citypulse/models/reg.joblib` | created | Trained LightGBM PM2.5 continuous regressor (100 trees)
- S7 | `citypulse/models/clf.joblib` | created | Trained LightGBM balanced risk classifier (100 trees)
- S7 | `citypulse/data/outputs/model_metrics.json` | created | Comprehensive evaluation metrics, confusion matrices, and honest shipping decision
- S7 | `citypulse/data/outputs/predictions.parquet` | created | Latest 9-station t+24h predictions with strictly normalized probabilities
- S7 | `citypulse/data/outputs/s7_eval_comparison.html` | created | Plotly interactive time-series evaluation chart for test block
- S7 | `citypulse/brain.md` | modified | Updated S6/S7 contracts, metrics, decisions, and test logs
- S7 | `citypulse/TASKS.md` | modified | Marked S6 and S7 VERIFIED with evidence
- S8 | `citypulse/citypulse/explain.py` | created | SHAP TreeExplainer driver extraction and conformal prediction interval module
- S8 | `citypulse/tests/test_explain.py` | created | Unit test suite for driver counts, raw-name exclusion, bounds containment, and coverage
- S8 | `citypulse/data/outputs/explanations.parquet` | created | 9-station SHAP explanations, plain-language drivers, and calibrated intervals (80.16% coverage)
- S8 | `citypulse/data/outputs/s8_shap_drivers.html` | created | Interactive Plotly horizontal bar chart of top environmental drivers
- S8 | `citypulse/data/outputs/s8_prediction_intervals.html` | created | Interactive Plotly error-bar chart of point forecasts with 80% conformal bounds
- S9 | `citypulse/citypulse/recommend.py` | created | Municipal recommendation and intervention ranking engine with explicit severity weights
- S9 | `citypulse/citypulse/brief.py` | created | Municipal decision brief generator and headless screenshot capture
- S9 | `citypulse/templates/brief.html.j2` | created | Jinja2 A4-printable briefing template with white-background print CSS
- S9 | `citypulse/tests/test_recommend.py` | created | Unit test suite for deterministic rules, ranking order, quality warnings, and brief rendering
- S9 | `citypulse/data/outputs/ranked_stations.parquet` | created | Top-5 ranked municipal intervention actions with scores and time windows
- S9 | `citypulse/data/outputs/brief.html` | created | Rendered one-page A4 municipal decision brief
- S9 | `citypulse/data/outputs/brief.png` | created | High-resolution headless browser screenshot of the printable brief
- S10 | `citypulse/ui/styles.css` | modified | Flat design system tokens (Apple/Linear inspired, WCAG AA >=4.5:1, reduced-motion, no gradients)
- S10 | `citypulse/ui/components.py` | created | Reusable UI components: risk_pill, quality_badge, card, big_number
- S10 | `citypulse/app.py` | modified | Responsive dashboard shell with top bar, real status line, 60/40 two-column layout, and bottom strip
- S10 | `citypulse/data/outputs/s10_desktop_1280.png` | created | Verified 1280px desktop viewport screenshot
- S10 | `citypulse/data/outputs/s10_mobile_390.png` | created | Verified 390px mobile viewport screenshot
- S10 | `citypulse/brain.md` | modified | Updated S8-S10 schemas, contracts, decisions, screenshots, and test logs
- S10 | `citypulse/TASKS.md` | modified | Marked S8, S9, S10 VERIFIED with real evidence

## 9. Commands executed (step, command, result summary)
- S1 | `py -3.11 -m venv .venv` | Created Python 3.11 virtual environment in `citypulse/.venv`
- S1 | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` | Installed 14 direct dependencies and all transitives successfully (exit 0)
- S1 | `.\.venv\Scripts\python.exe -c "import config; ..."` | Verified config attributes: CITY=Mumbai, GOOD_MAX=60, UNHEALTHY_MAX=250, FORECAST_HORIZON_HOURS=24, PROJECT_ROOT resolved (exit 0)
- S1 | `.\.venv\Scripts\pytest.exe` | Collected 0 items, 0 errors, no tests ran (exit 1, expected no-tests exit code)
- S1 | `git init` | Initialized repository in `citypulse`
- S1 | `git check-ignore .venv/ data/raw/ models/ .env` | Confirmed all 4 paths are correctly ignored (exit 0)
- S1 | `git check-ignore -v data/outputs/predictions.parquet data/outputs/patterns.json data/sample` | Confirmed outputs and sample folders are tracked/not ignored (exit 1, no output)
- S1 | `git commit -m "chore: initialize CityPulse project skeleton"` | Initial commit recorded
- S1 | `git remote add origin https://github.com/brijeshearn12-dotcom/citypulse.git && git push -u origin main` | Pushed initial skeleton to GitHub remote repository (exit 0)
- S2 | `py -3.11 -m venv .citypulse-verify-venv` | Created temporary clean verification virtual environment
- S2 | `pip install -r requirements.txt` in `.citypulse-verify-venv` | All 14 pinned requirements installed cleanly (exit 0)
- S2 | `pip check` in `.citypulse-verify-venv` | Output: "No broken requirements found." (exit 0)
- S2 | `pip freeze` in `.citypulse-verify-venv` | Verified exact versions against requirements.txt (exit 0)
- S2 | `Remove-Item .citypulse-verify-venv` | Safely deleted temporary environment after validation
- S2 | `streamlit run app.py` | Launched local Streamlit instance on port 8501 (daemon)
- S2 | `msedge.exe --headless=new --screenshot=... --window-size=1280,800` | Captured verified desktop screenshot
- S2 | `msedge.exe --headless=new --screenshot=... --window-size=390,844` | Captured verified mobile screenshot
- S3 | `python -m citypulse.fetch_data` | Executed full ingestion: 9 Mumbai stations, 120 days, 19,989 PM2.5 rows, 2,880 weather rows (exit 0)
- S3 | `python -m pytest -v` | Ran smoke and contract tests: 4 passed in 1.55s (exit 0)
- S4 | `python -m citypulse.clean` | Executed cleaning pipeline on real S3 data: 25,920 rows cleaned, quality summary and chart generated (exit 0)
- S4 | `python -m pytest -v` | Ran test suite: all 11 tests passed in 1.58s (exit 0)
- S5 | `python -m citypulse.patterns` | Executed pattern discovery on real data: generated patterns.json, heatmap.parquet, heatmap.html (exit 0)
- S5 | `python -m pytest -v` | Ran full test suite: all 18 tests passed in 1.72s (exit 0)
- S6 | `python -m citypulse.features` | Executed feature engineering on clean observations: generated features.parquet (exit 0)
- S7 | `python -m citypulse.train` | Trained LightGBM regressor & classifier, evaluated baselines, saved metrics and predictions (exit 0)
- S7 | `python -m citypulse.pipeline --cached` | Executed complete end-to-end pipeline in cached offline mode in 4.9s (exit 0)
- S7 | `python -m pytest -v` | Ran complete test suite: all 28 unit and contract tests passed in 3.85s (exit 0)
- S7 | `Start-Process data\outputs\s7_eval_comparison.html` | Opened interactive evaluation comparison chart in system browser (exit 0)
- S8 | `python -m citypulse.explain` | Computed SHAP feature drivers, trained quantile regressors, applied conformal widening (80.16% coverage) (exit 0)
- S9 | `python -m citypulse.recommend` | Executed municipal ranking with explicit weights, generated top-5 actions with telemetry alerts (exit 0)
- S9 | `python -m citypulse.brief` | Generated brief.html and captured high-resolution brief.png screenshot (exit 0)
- S10 | `python -m citypulse.pipeline --cached` | Executed end-to-end pipeline through S10 in 13.2s (exit 0)
- S10 | `python -m pytest -v` | Ran complete test suite: all 41 unit and contract tests passed in 4.63s (exit 0)
- S10 | Headless Edge screenshot capture | Captured verified desktop (1280x800) and mobile (390x844) viewport screenshots (exit 0)

## 10. Test results (real output only)
| Step | Command | Result (passed/failed counts) | Date/time |
|---|---|---|---|
| S1 | `python -m pip install -r requirements.txt` | Pass (all 14 requirements satisfied, exit code 0) | 2026-10-22 20:44:21 |
| S1 | `python -c "import config; print(config.CITY); print(config.GOOD_MAX, config.UNHEALTHY_MAX); print(config.FORECAST_HORIZON_HOURS); print(config.PROJECT_ROOT)"` | Pass (Mumbai, 60 250, 24, PROJECT_ROOT printed, exit code 0) | 2026-10-22 20:44:21 |
| S1 | `pytest` | Pass (collected 0 items, 0 errors, no tests ran) | 2026-10-22 20:44:40 |
| S1 | Directory Structure Verification | Pass (34 files matching tree exactly) | 2026-10-22 20:45:02 |
| S1 | Git Ignore & Staging Verification | Pass (ignored paths excluded, required tracked) | 2026-10-22 20:46:21 |
| S2 | Clean venv pip install | Pass (clean install of all 14 packages, exit 0) | 2026-10-22 21:06:40 |
| S2 | Clean venv `pip check` | Pass ("No broken requirements found.", exit 0) | 2026-10-22 21:07:20 |
| S2 | Local Streamlit launch | Pass (app rendered on http://localhost:8501 without traceback) | 2026-10-22 21:09:44 |
| S2 | Desktop viewport 1280x800 | Pass (Title, subtitle, v0.1.0, warning banner, table rendered) | 2026-10-22 21:13:05 |
| S2 | Mobile viewport 390x844 | Pass (Single-column responsive layout, no horizontal overflow) | 2026-10-22 21:13:57 |
| S3 | `python -m citypulse.fetch_data` | Pass (9 stations, 120 days, 19,989 PM2.5 obs, 2,880 weather obs, 0 dups, exit 0) | 2026-10-22 21:51:18 |
| S3 | `python -m pytest -v` | Pass (4 passed: test_processed_pm25_contract, test_processed_weather_contract, test_sample_dataset_contract, test_visual_check_output) | 2026-10-22 21:57:55 |
| S4 | `python -m pytest -v` | Pass (11 passed: 5 in test_clean.py, 6 in test_pipeline_smoke.py, exit 0) | 2026-10-22 22:13:19 |
| S4 | `python -m citypulse.clean` | Pass (25,920 hourly rows reindexed, 743 gap fills, 135 stuck flags, 83 impossible flags, exit 0) | 2026-10-22 22:12:06 |
| S5 | `python -m pytest -v` | Pass (18 passed: 5 clean, 6 patterns, 7 smoke contract tests, exit 0) | 2026-10-22 22:30:19 |
| S5 | `python -m citypulse.patterns` | Pass (Diurnal peak +15.1% at 08:00, calm wind +19.7% uplift, persistent worst stations ranked, exit 0) | 2026-10-22 22:29:19 |
| S6 | `python -m pytest tests/test_features.py` | Pass (5 passed: leakage prevention, forecast stand-ins, chronological split, target thresholds, exit 0) | 2026-10-22 23:00:16 |
| S7 | `python -m pytest -v` | Pass (28 passed: 5 clean, 5 features, 6 patterns, 12 smoke contract tests, exit 0) | 2026-10-22 23:00:16 |
| S7 | `python -m citypulse.pipeline --cached` | Pass (rebuilt clean, patterns, features, models, predictions in 4.9s without keys, exit 0) | 2026-10-22 22:58:33 |
| S8 | `python -m pytest tests/test_explain.py` | Pass (4 passed: driver count, raw-name exclusion, interval containment, station coverage, exit 0) | 2026-10-22 23:32:00 |
| S9 | `python -m pytest tests/test_recommend.py` | Pass (5 passed: deterministic rules, severity weights, top-5 truncation, low quality warning, brief contract, exit 0) | 2026-10-22 23:32:00 |
| S10 | `python -m pytest -v` | Pass (41 passed: 5 clean, 4 explain, 5 features, 6 patterns, 16 smoke contract tests, 5 recommend, exit 0) | 2026-10-22 23:46:46 |
| S10 | `python -m citypulse.pipeline --cached` | Pass (rebuilt full pipeline end-to-end through S10 in 13.2s without keys, exit 0) | 2026-10-22 23:45:16 |

## 11. Screens and flows verified (step, screen, width, finding, evidence path)
- S1: none (foundation step, no screens)
- S2: Desktop Home | 1280px | Title, subtitle, v0.1.0, warning callout, and 5-row table render cleanly on light background | `desktop_1280x800.png`
- S2: Mobile Home | 390px | Card-like responsive layout, text wraps cleanly, table scrolls naturally without page-level horizontal overflow | `mobile_390x844.png`
- S8: SHAP Key Drivers Bar Chart | 1200px | Top-3 SHAP contribution counts across monitoring stations; no raw feature names | `s8_shap_drivers.html`
- S8: Prediction Interval Plot | 1200px | Station-by-station point estimates with conformal uncertainty bounds (80.16% coverage) | `s8_prediction_intervals.html`
- S9: Municipal Decision Brief | 1200x1600 | Single-page A4 printable document with top-5 actions, 3 patterns, model vs baseline metrics, limitations | `brief.html` / `brief.png`
- S10: Desktop App Shell | 1280px | Flat design system, 60/40 two-column layout, top bar with real-time station counts, WCAG AA contrast (>=4.5:1), no gradients or glass effects | `s10_desktop_1280.png`
- S10: Mobile App Shell | 390px | Single-column stacked responsive layout below 768px, readable typography, cards wrap cleanly | `s10_mobile_390.png`

## 12. Known bugs and blockers
- None

## 13. Deployment configuration and status
- Repo URL: https://github.com/brijeshearn12-dotcom/citypulse.git
- Host: Streamlit Community Cloud
- Main file: app.py | Python: 3.11 (set in Advanced settings) | Secrets: none
- Live URL: (none yet. Never invent one. Awaiting user clicks and URL.)
- Smoke test (S2): IN PROGRESS (Local verified, awaiting cloud deployment)
- Final verification (S14): NOT STARTED
- Evidence: (log excerpts, screenshot paths)

## 14. Time used and remaining
| Step | Planned min | Actual min | Cumulative | Remaining of 360 |
|---|---|---|---|---|
| S1 | 25 | 20 | 20 | 340 |
| S2 | 20 | 16 | 36 | 324 |
| S3 | 35 | 22 | 58 | 302 |
| S4 | 25 | 15 | 73 | 287 |
| S5 | 25 | 14 | 87 | 273 |
| S6 | 30 | 20 | 107 | 253 |
| S7 | 30 | 22 | 129 | 231 |
| S8 | 25 | 18 | 147 | 213 |
| S9 | 25 | 18 | 165 | 195 |
| S10 | 25 | 20 | 185 | 175 |

## 15. Exact next action
Awaiting user approval for Steps 8, 9, and 10 (Explain, Act/Brief, and Design System/App Shell) completion before proceeding to Step 11 (Map, list, station panel). S2 cloud deployment URL pending user deployment on Streamlit Community Cloud.

## 16. Step report format (required at the end of every step)
1. What was completed
2. Files created or modified
3. What actually works
4. Evidence (screenshot, test output, deployment log). If screenshots are impossible, say so and give the best alternative
5. Tests run and real results
6. Known issues
7. Elapsed and remaining minutes
8. Next task and its dependencies
9. Acceptance criteria: passed / failed / partly, with reasons
