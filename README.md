# CityPulse: Mumbai Air Quality Decision Support System

Next-24-hour PM2.5 pollution risk forecasting, causal pattern discovery, and operational decision support for municipal pollution-control officers in Mumbai, Maharashtra.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3119/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.39-FF4B4B.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/pytest-43%20passed-brightgreen.svg)](tests/)

---

## 1. Project Purpose & System Overview

**CityPulse** is an operational decision-support tool engineered specifically for municipal environmental engineers and pollution-control officers across the Brihanmumbai Municipal Corporation (BMC) jurisdiction. 

Rather than presenting raw, uncalibrated sensor graphs or inventing fine-grained hourly forecasts that exceed meteorological predictability, CityPulse delivers:
- **Decision D5 Forecasts**: A transparent time-series view linking the past 24 hours of verified ground observations directly to a single $t+24\text{h}$ ahead categorical risk forecast and continuous PM2.5 prediction interval.
- **Conformal Uncertainty Bands**: Asymmetric 80% prediction intervals calibrated via split conformal inference on holdout observations (achieving 80.16% empirical coverage).
- **Interpretable SHAP Attribution**: Plain-language feature drivers explaining *why* a station's risk is elevated (without raw feature jargon or false causal claims).
- **Rule-Based Prioritized Interventions**: Deterministic municipal action directives (e.g., anti-smog gun deployment, mist cannon sweeps, construction halts) ranked by probability of severe contamination.
- **One-Page A4 Printable Municipal Brief**: Downloadable HTML brief designed for executive morning briefings.

---

## 2. Core Features & Capabilities

| Capability | Module | Description |
|---|---|---|
| **Discover** | `citypulse/patterns.py` | Detects recurring operational patterns (08:00 diurnal peak $+15.1\%$, calm wind $\le 4.8\,\text{km/h}$ stagnation $+19.7\%$ PM2.5 uplift, persistent worst-corridor rankings) over 90-day baselines. |
| **Predict** | `citypulse/train.py` | LightGBM Regressor and balanced multi-class Classifier predicting next-24h PM2.5 and 3-tier risk tiers (Good $\le 60$, Unhealthy $>60\text{–}250$, Severe $>250\,\mu\text{g/m}^3$). |
| **Explain** | `citypulse/explain.py` | Tree SHAP feature attribution mapping top 3 positive and negative contributors into human-readable phrases; 80% conformal prediction intervals. |
| **Act** | `citypulse/recommend.py` | Ranks stations via explicit severity formula $(p_{\text{unhealthy}} + p_{\text{severe}}) \times \text{weight}$ and assigns deterministic rule-based interventions. |
| **Brief** | `citypulse/brief.py` | Formats a single-page A4 executive municipal brief with print CSS and headless screenshot rendering. |
| **Visualize** | `app.py`, `ui/` | Responsive 60/40 dashboard with Folium map, Plotly charts ($\le 3$ simultaneously), WCAG AA ($\ge 4.5:1$) contrast, and full telemetry status. |

---

## 3. Architecture & Data Flow

```text
[OpenAQ S3 Archive]      [Open-Meteo Weather API]
        │                           │
        └─────────────┬─────────────┘
                      ▼
            citypulse/fetch_data.py
                      │
                      ▼
            citypulse/clean.py (QA/QC: 1-3h gap fill, stuck & impossible flags)
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
citypulse/patterns.py    citypulse/features.py (22 causal features + 2 stand-ins)
         │                         │
         │                         ▼
         │               citypulse/train.py (LightGBM regressor & classifier)
         │                         │
         │                         ▼
         │               citypulse/explain.py (SHAP drivers & 80% conformal intervals)
         │                         │
         └────────────┬────────────┘
                      ▼
            citypulse/recommend.py (Severity ranking & deterministic actions)
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
  citypulse/brief.py             app.py (Streamlit UI + Folium Map)
(A4 Printable Brief)      (Interactive Decision Dashboard)
```

---

## 4. One-Command Local Setup

### Prerequisites
- Python 3.11.x (tested on 3.11.9)
- Git

### Quickstart
```bash
# 1. Clone repository
git clone https://github.com/brijeshearn12-dotcom/citypulse.git
cd citypulse

# 2. Set up virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 3. Install pinned dependencies
python -m pip install -r requirements.txt

# 4. Rebuild full pipeline from committed offline cache (Zero API keys required)
python -m citypulse.pipeline --cached

# 5. Run test suite
python -m pytest

# 6. Launch dashboard
streamlit run app.py
```
Access the dashboard locally at `http://localhost:8501`.

---

## 5. Verified Data Sources & Provenance

CityPulse operates strictly on real, verified historical datasets:

1. **OpenAQ Public S3 Archive**:
   - Bucket: `s3://openaq-data-archive/` (Anonymous public access, no AWS credentials required).
   - Terms & Documentation: [OpenAQ Data Terms](https://openaq.org/) & [OpenAQ AWS S3 Documentation](https://registry.opendata.aws/openaq/).
   - Stations: 9 official CPCB/MPCB continuous ambient monitoring stations across Mumbai (Bandra Kurla Complex, Kherwadi, Shivaji Nagar, Byculla, Chembur, Ghatkopar, Mindspace-Malad West, Borivali East, Sewri).
   - Temporal Coverage: November 1, 2025 to February 28, 2026 (120 days, 25,920 regular hourly observation slots).

2. **Open-Meteo Historical Weather Archive & Air Quality**:
   - Base URLs: `https://archive-api.open-meteo.com/v1/archive` and `https://air-quality-api.open-meteo.com/v1/air-quality`
   - Terms & Documentation: [Open-Meteo Terms of Use](https://open-meteo.com/en/terms) (Open-source, non-commercial CC-BY 4.0).
   - Parameters: Temperature, relative humidity, precipitation, 10m wind speed, 10m wind direction, boundary layer height.

---

## 6. Model Performance & Baseline Comparison

All models were evaluated on a strictly held-out chronological test block. Time-series data is **never randomly shuffled**.

### Chronological Evaluation Split
- **Training Period**: November 1, 2025 00:00 to January 31, 2026 23:59 IST (14,551 valid training examples; 9,004 Good, 5,478 Unhealthy, 69 Severe).
- **Test Period**: February 1, 2026 00:00 to February 28, 2026 23:59 IST (3,654 test examples; 2,756 Good, 898 Unhealthy).

### Out-of-Time Metric Results

| Model / Benchmark | MAE ($\mu\text{g/m}^3$) | RMSE ($\mu\text{g/m}^3$) | F1 (Unhealthy+Severe) | Multi-Class Macro F1 |
|---|---|---|---|---|
| **Persistence Baseline** | **11.82** | 18.06 | **0.6251** | 0.7719 |
| **24-Hour Moving Average Baseline** | 12.86 | 17.51 | 0.5432 | 0.7303 |
| **LightGBM Regressor + Balanced Classifier** | 13.00 | **17.20** | 0.6076 | **0.7813** |

### Honest Technical Evaluation & Deployment Decision
In seasonal time-series air quality prediction with strong autocorrelation, the simple 24-hour persistence baseline is a formidable benchmark. While LightGBM achieved a marginally lower RMSE (17.20 vs. 18.06) and higher multi-class macro F1 (0.7813 vs. 0.7719), its continuous MAE is 13.00 compared to 11.82 for persistence. 

**Production Decision:** `DEPLOY_MODEL_WITH_HONEST_DISCLOSURE`. The LightGBM system is deployed alongside the Persistence baseline because it provides feature attributions (SHAP drivers) and adapts to changing meteorological ventilation that persistence cannot anticipate. All evaluation trade-offs are disclosed transparently on the dashboard and executive brief.

---

## 7. Prediction Intervals & Conformal Calibration

To protect municipal officers from overconfident point forecasts:
- Raw LightGBM quantile regressors ($\alpha=0.1, 0.9$) yielded 70.83% empirical coverage on untouched test observations.
- Split conformal calibration on an independent validation window computed a non-conformity adjustment $\delta = 4.67\,\mu\text{g/m}^3$.
- Calibrated prediction bands $[y_{\text{pred}} - \delta, y_{\text{pred}} + \delta]$ achieved **80.16% empirical coverage** across the 3,654 test hours.

---

## 8. Honest Operational Limitations

1. **Small Sensor Network**: Mumbai's continuous monitoring network is sparse (9 verified stations in this dataset). Spatial interpolation between stations must be interpreted cautiously.
2. **Monsoon Skew**: In tropical coastal India, monsoon months (June–September) exhibit near-zero particulate contamination due to heavy wet deposition, skewing raw annual class balances toward "Good". The evaluation block focuses on high-risk winter inversion months.
3. **Held-Out Winter Period**: Evaluated over February 2026 winter conditions; performance during transitional pre-monsoon summer dust events may differ.
4. **Historical Weather Stand-Ins**: In this historical analysis version, next-24-hour weather features represent historical reanalysis observations acting as proxies for actual 24-hour meteorological forecasts.
5. **Advisory Scope**: **⚠️ Decision support, not an official alert.** CityPulse recommendations provide operational prioritization for municipal teams, not statutory regulatory declarations.

---

## 9. Production Deployment

### Streamlit Community Cloud (Recommended)
1. Fork or push this repository to GitHub.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app** and select:
   - **Repository:** `brijeshearn12-dotcom/citypulse`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. In **Advanced settings**, set Python to `3.11`. No environment secrets or API keys are required.
5. Click **Deploy!**

### Fallback Host: Hugging Face Spaces
If Streamlit Community Cloud experiences platform downtime:
1. Create a new Space on [Hugging Face](https://huggingface.co/spaces) with SDK: `Streamlit`.
2. Connect your GitHub repository.
3. Set the application entry file to `app.py`.

---

## 10. Verification, Tests & Security

- **Pytest Suite**: Run `python -m pytest -v` (43 passed tests covering cleaning, leak prevention, feature contracts, pattern statistics, conformal intervals, recommendation rules, UI components, and end-to-end smoke tests).
- **Security Audit**: Zero credentials, tokens, or live API keys committed. Retains `.env.example` with harmless default placeholders (`CITY=Mumbai`).
