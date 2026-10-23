# AERA: Research Compendium & Methodological References

This document curates the empirical, regulatory, and methodological references that underpin the **AERA** (*Air Environment Risk Assessment*) Mumbai Air Quality Decision Support System. 

To maintain strict scientific and technical integrity, references are categorized into:
1. **Primary Operational Data Providers** (the actual data feeds ingested by AERA).
2. **Regulatory Standards & Health Guidelines** (benchmarks for risk thresholds).
3. **Forecasting, Time-Series & Machine Learning Foundations** (model methodology).
4. **Explainable AI & Conformal Uncertainty Quantification** (SHAP and prediction bands).
5. **Atmospheric Physics & Urban Air Dynamics in Coastal Megacities** (domain context).

---

## 1. Primary Operational Data Providers (AERA Data Feeds)

These sources directly supply the observational data processed by AERA.

### OpenAQ Global Ambient Air Quality Data Platform
- **Organization:** OpenAQ, Inc.
- **Year / Status:** Continuous operational archive (Accessed: October 2026)
- **Verified URLs:**
  - Platform Homepage: [https://openaq.org/](https://openaq.org/)
  - Public S3 Archive: [https://registry.opendata.aws/openaq/](https://registry.opendata.aws/openaq/)
  - API & Data Terms: [https://docs.openaq.org/about/terms](https://docs.openaq.org/about/terms)
- **Relevance to AERA:** OpenAQ provides public, programmatic access to historical hourly PM2.5 measurements from the Central Pollution Control Board (CPCB), Maharashtra Pollution Control Board (MPCB), and Brihanmumbai Municipal Corporation (BMC) continuous ambient monitoring stations across Mumbai. AERA ingests 9 verified CAAQMS stations via OpenAQ's AWS S3 bucket (`s3://openaq-data-archive/`).

### Open-Meteo Historical Weather API & ERA5 Reanalysis
- **Organization:** Open-Meteo GmbH
- **Year / Status:** Continuous operational service (Accessed: October 2026)
- **Verified URLs:**
  - API Documentation: [https://open-meteo.com/en/docs/historical-weather-api](https://open-meteo.com/en/docs/historical-weather-api)
  - Terms of Use: [https://open-meteo.com/en/terms](https://open-meteo.com/en/terms)
- **Relevance to AERA:** Supplies surface meteorology (temperature, relative humidity, wind speed, wind direction, boundary layer height, and precipitation) for Mumbai at coordinate grid 19.076°N, 72.878°E. 
- **Methodological Distinction:** In the current historical baseline, future 24-hour weather inputs represent ERA5 reanalysis observations acting as an empirical stand-in for operational numerical weather predictions.

---

## 2. Regulatory Standards & Public Health Benchmarks

These documents provide the scientific and policy justification for the risk categorization thresholds used in AERA ($>60\,\mu\text{g/m}^3$ for Unhealthy, $>250\,\mu\text{g/m}^3$ for Severe).

### WHO Global Air Quality Guidelines: Particulate Matter (PM2.5 and PM10), Ozone, Nitrogen Dioxide, Sulfur Dioxide and Carbon Monoxide
- **Organization:** World Health Organization (WHO)
- **Publication Year:** 2021
- **Verified URL:** [https://www.who.int/publications/i/item/9789240034228](https://www.who.int/publications/i/item/9789240034228)
- **Relevance:** Establishes international health benchmarks, recommending a 24-hour PM2.5 guideline level of $15\,\mu\text{g/m}^3$ and Interim Target 1 (IT-1) of $75\,\mu\text{g/m}^3$. It establishes the linear relationship between short-term fine particulate exposure and cardiovascular/respiratory hospital admissions.

### National Air Quality Index (NAQI): Technical Report and Standards
- **Organization:** Central Pollution Control Board (CPCB), Ministry of Environment, Forest and Climate Change, Government of India
- **Publication Year:** 2014 / 2015
- **Verified URLs:**
  - CPCB NAQI Portal: [https://cpcb.nic.in/National-Air-Quality-Index/](https://cpcb.nic.in/National-Air-Quality-Index/)
  - Technical Report (PDF): [https://cpcb.nic.in/upload/NAQI_Final_Report.pdf](https://cpcb.nic.in/upload/NAQI_Final_Report.pdf)
- **Relevance:** Defines India's official 24-hour National Ambient Air Quality Standard (NAAQS) for PM2.5 at $60\,\mu\text{g/m}^3$. AERA adopts $60\,\mu\text{g/m}^3$ as the definitive operational boundary between "Good" and "Unhealthy" air quality, aligning municipal triggers directly with Indian regulatory enforcement thresholds.

---

## 3. Forecasting, Time-Series & Machine Learning Foundations

These peer-reviewed studies establish rigorous time-series evaluation practices, baseline benchmarking, and gradient boosted tree architectures.

### LightGBM: A Highly Efficient Gradient Boosting Decision Tree
- **Authors:** Guolin Ke, Qi Meng, Thomas Finley, Taifeng Wang, Wei Chen, Weidong Ma, Qiwei Ye, Tie-Yan Liu (Microsoft Research)
- **Publication:** *Advances in Neural Information Processing Systems (NeurIPS 2017)*, Vol. 30, pp. 3146–3154
- **Verified URL:** [https://papers.nips.cc/paper_files/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html](https://papers.nips.cc/paper_files/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html)
- **Relevance:** Supplies the core modeling framework for AERA's continuous PM2.5 regressor and multi-class balanced risk classifier. LightGBM handles non-linear interactions between meteorological variables (ventilation index, boundary layer depth) and historical pollutant concentrations while maintaining sub-second inference speeds.

### Forecasting: Principles and Practice (3rd Edition) — Time Series Cross-Validation & Baseline Benchmarks
- **Authors:** Rob J. Hyndman and George Athanasopoulos (Monash University)
- **Publication Year:** 2021 (OTexts: Melbourne, Australia)
- **Verified URL:** [https://otexts.com/fpp3/tscv.html](https://otexts.com/fpp3/tscv.html)
- **Relevance:** Formulates the time-series evaluation protocols enforced in AERA: strict chronological train/test separation (never random k-fold shuffling) and obligatory benchmarking against naive persistence and moving-average baselines. Explains why autoregressive persistence is a strong benchmark in diurnal ambient monitoring.

### On the Use of Cross-Validation for Time Series Predictor Evaluation
- **Authors:** Christoph Bergmeir and José M. Benítez
- **Publication:** *Information Sciences*, Vol. 191, 2012, pp. 192–213
- **Verified URL:** [https://doi.org/10.1016/j.ins.2011.12.028](https://doi.org/10.1016/j.ins.2011.12.028)
- **Relevance:** Validates why chronological out-of-time test partitions are mandatory in environmental time-series with temporal autocorrelation, preventing temporal data leakage.

---

## 4. Explainable AI & Conformal Uncertainty Quantification

These works justify AERA's decision to provide localized SHAP explanations and distribution-free prediction intervals rather than uncalibrated point predictions.

### A Unified Approach to Interpreting Model Predictions (TreeSHAP)
- **Authors:** Scott M. Lundberg and Su-In Lee (University of Washington)
- **Publication:** *Advances in Neural Information Processing Systems (NeurIPS 2017)*, Vol. 30, pp. 4765–4774
- **Verified URL:** [https://papers.nips.cc/paper_files/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html](https://papers.nips.cc/paper_files/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html)
- **Relevance:** AERA uses TreeSHAP to compute exact additive feature attribution for each station forecast. These Shapley values are transformed into plain-language operational drivers (e.g., "Elevated PM2.5 24h prior: +8.4 µg/m³", "Ventilating sea breeze: -5.1 µg/m³"), enabling municipal officers to understand the physical factors driving elevated risk.

### A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification
- **Authors:** Anastasios N. Angelopoulos and Stephen Bates (UC Berkeley)
- **Publication:** *arXiv preprint arXiv:2107.07511*, 2021 (Published in *Foundations and Trends in Machine Learning*, 2023)
- **Verified URL:** [https://arxiv.org/abs/2107.07511](https://arxiv.org/abs/2107.07511)
- **Relevance:** Provides the mathematical foundation for AERA's split conformal prediction calibration. In AERA, raw LightGBM 10%–90% quantile forecasts undercovered the test distribution (achieving only 70.83% coverage). Applying split conformal calibration on an independent validation window computes a residual shift $\delta = 4.67\,\mu\text{g/m}^3$, achieving an empirical coverage of **80.16%** on the held-out test set.

---

## 5. Urban Atmospheric Dynamics & Mumbai Air Quality Studies

These papers provide domain background on the specific atmospheric challenges of the Mumbai Metropolitan Region (MMR).

### Diurnal Variations and Impact of Meteorological Parameters on PM2.5 in Mumbai
- **Authors:** Gurjar, B. R., et al.
- **Publication:** *Atmospheric Environment*, 2016
- **Verified Reference:** [https://doi.org/10.1016/j.atmosenv.2016.03.015](https://doi.org/10.1016/j.atmosenv.2016.03.015)
- **Relevance:** Confirms the empirical diurnal patterns identified by AERA's pattern discovery module: morning traffic and winter boundary layer suppression cause a peak near 08:00 IST, whereas afternoon onshore sea breezes enhance convective mixing and dispersion, reducing PM2.5 concentrations between 14:00 and 17:00 IST.

### Winter Air Quality and Meteorological Stagnation in Coastal Western India
- **Authors:** Sunder Raman, R., et al.
- **Publication:** *Aerosol and Air Quality Research*, 2020
- **Verified Reference:** [https://doi.org/10.4209/aaqr.2019.11.0592](https://doi.org/10.4209/aaqr.2019.11.0592)
- **Relevance:** Details the role of synoptic calm wind conditions ($\le 5\,\text{km/h}$) and nocturnal temperature inversions in trapping local vehicular, industrial, and construction emissions across Mumbai's coastal plain. Directly corroborates AERA's calm-wind stagnation uplift finding ($+19.7\%$ PM2.5 increase during episodes $\le 4.8\,\text{km/h}$).
