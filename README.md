# CityPulse

Next-24-hour PM2.5 pollution risk forecasting and decision support for municipal pollution-control officers in Mumbai.

## Overview

**CityPulse** is a decision-support application built for municipal pollution-control officers in Mumbai. It provides station-level 24-hour risk forecasting for particulate matter ($PM_{2.5}$), identifies primary environmental drivers, and generates prioritized, evidence-based mitigation recommendations (such as anti-smog gun deployments, mechanical sweeping, and localized construction halts).

## Intended Audience

Municipal environmental officers, ward commissioners, and air-quality monitoring engineers tasked with operational dust control, public health advisories, and enforcement inspections across Mumbai.

## Planned Capabilities

- **Discover**: Automated pattern detection identifying diurnal peaks, weekday vs. weekend variances, and seasonal trends across Mumbai monitoring stations.
- **Predict**: Next-24-hour $PM_{2.5}$ categorical risk forecasts (Good $\le 60\,\mu\text{g/m}^3$, Unhealthy $> 60 \text{ to } 250\,\mu\text{g/m}^3$, Severe $> 250\,\mu\text{g/m}^3$) with probabilistic confidence bands.
- **Explain**: Interpretable model drivers powered by SHAP and feature attribution to justify operational alerts.
- **Act**: Rule-based prioritized municipal interventions and downloadable one-page operational briefings.

## Setup Status

> **Important Note:** This repository is currently in its initial foundation phase (**Step 1 of 14**).  
> The project structure, environment configuration, and placeholder architecture have been established.  
> **Forecasting models, data ingestion pipelines, and interactive UI features are not yet implemented.**

## Setup Instructions

1. Create and activate a Python 3.11 virtual environment:
   ```bash
   py -3.11 -m venv .venv
   .venv\Scripts\activate   # On Windows
   # source .venv/bin/activate  # On Linux/macOS
   ```
2. Install pinned dependencies:
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
3. Verify configuration:
   ```bash
   python -c "import config; print(config.CITY)"
   ```
4. Run tests:
   ```bash
   pytest
   ```
