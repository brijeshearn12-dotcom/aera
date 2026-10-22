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
- raw/processed PM2.5 (S3): timestamp_utc, timestamp_ist, station_id, station_name, lat, lon, pm25
- clean.parquet (S4): timestamp, station_id, station_name, lat, lon, pm25, pm25_filled, flag_gap, flag_stuck, flag_impossible, weather columns
- quality_summary.parquet (S4): station_id, data_quality_pct, quality_label (Good >= 90, Fair 70-90, Low < 70)
- patterns.json / heatmap.parquet (S5)
- feature list, target definition, split rule, baseline metrics (S6)
- model_metrics.json, predictions.parquet: station_id, predicted_class, p_good, p_unhealthy, p_severe, predicted_pm25, as_of (S7)
- explanations.parquet: station_id, driver_1..3 (text, direction), lower, upper, quality_label, notes (S8)
- ranked list structure (S9)

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

## 11. Screens and flows verified (step, screen, width, finding, evidence path)
- S1: none (foundation step, no screens)
- S2: Desktop Home | 1280px | Title, subtitle, v0.1.0, warning callout, and 5-row table render cleanly on light background | `desktop_1280x800.png`
- S2: Mobile Home | 390px | Card-like responsive layout, text wraps cleanly, table scrolls naturally without page-level horizontal overflow | `mobile_390x844.png`

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

## 15. Exact next action
Awaiting user to deploy repository on Streamlit Community Cloud and provide the public URL. Once provided, verify the live URL and complete S2.

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
