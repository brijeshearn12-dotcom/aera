# CityPulse

Next-24-hour PM2.5 pollution risk forecasting and decision support for municipal pollution-control officers in Mumbai.

## Overview

**CityPulse** is a decision-support application built for municipal pollution-control officers in Mumbai. It provides station-level 24-hour risk forecasting for particulate matter ($PM_{2.5}$), identifies primary environmental drivers, and generates prioritized, evidence-based mitigation recommendations (such as anti-smog gun deployments, mechanical sweeping, and localized construction halts).

## Current Implementation Status

> ⚠️ **Status: Step 2 of 14 (Minimal Dashboard & Deployment Readiness)**  
> **Explicit Notice:** The current dashboard displays hard-coded illustrative placeholder figures strictly to verify interface rendering and cloud deployment readiness.  
> **No live air quality sensors, data pipelines, or forecasting models are connected in this step.**

## Planned Capabilities

- **Discover**: Automated pattern detection identifying diurnal peaks, weekday vs. weekend variances, and seasonal trends across Mumbai monitoring stations.
- **Predict**: Next-24-hour $PM_{2.5}$ categorical risk forecasts (Good $\le 60\,\mu\text{g/m}^3$, Unhealthy $> 60 \text{ to } 250\,\mu\text{g/m}^3$, Severe $> 250\,\mu\text{g/m}^3$) with probabilistic confidence bands.
- **Explain**: Interpretable model drivers powered by SHAP and feature attribution to justify operational alerts.
- **Act**: Rule-based prioritized municipal interventions and downloadable one-page operational briefings.

## Prerequisites

- **Python**: Python 3.11 (tested on 3.11.9)
- **Git**: Installed and configured
- **GitHub Account**: Required for publishing and deploying to Streamlit Community Cloud

## Local Setup & Execution

1. **Clone the repository**:
   ```bash
   git clone https://github.com/brijeshearn12-dotcom/citypulse.git
   cd citypulse
   ```

2. **Create and activate a Python 3.11 virtual environment**:
   ```powershell
   # Windows
   py -3.11 -m venv .venv
   .\.venv\Scripts\activate
   ```
   ```bash
   # macOS / Linux
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install pinned dependencies**:
   ```bash
   python -m pip install -r requirements.txt
   ```

4. **Verify configuration**:
   ```bash
   python -c "import config; print(config.CITY)"
   ```

5. **Run the local Streamlit dashboard**:
   ```bash
   streamlit run app.py
   ```
   Access the dashboard locally at `http://localhost:8501`.

## Publishing to GitHub

If working from a local branch, push changes to the GitHub repository:

```bash
git push origin main
```

Repository: `https://github.com/brijeshearn12-dotcom/citypulse.git`

## Streamlit Community Cloud Deployment

To deploy the application live:

1. Navigate to [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with your GitHub account.
2. Click **Create app** (or **Deploy an app**).
3. Choose **Deploy from a GitHub repo**.
4. Configure the deployment settings:
   - **Repository:** `brijeshearn12-dotcom/citypulse`
   - **Branch:** `main`
   - **Main file path:** `app.py`
5. Open **Advanced settings**:
   - **Python version:** `3.11`
   - **Secrets:** None required for S2 (leave empty)
6. Click **Deploy!**
7. Once the build completes, copy the public URL provided by Streamlit Community Cloud to access the live dashboard.
