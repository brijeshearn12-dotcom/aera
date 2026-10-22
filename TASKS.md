# TASKS.md: CityPulse

Status: NOT STARTED | IN PROGRESS | BLOCKED | VERIFIED | DEFERRED  
Priority: P0 = mandatory MVP, P1 = important, P2 = optional  
Update at the end of every step. VERIFIED only with evidence.

## Steps
| ID | Task | Pri | Min | Depends on | Status | Acceptance (short) | Evidence |
|---|---|---|---|---|---|---|---|
| S1 | Repo, structure, brain.md, TASKS.md | P0 | 25 | none | VERIFIED | Tree matches plan; pip install ok; config imports | All 34 planned files verified; pip install exit code 0; config imports verified; pytest 0 items collected with 0 errors; git initial commit verified |
| S2 | Early deployment smoke test | P0 | 20 | S1 | NOT STARTED | Public URL loads placeholder | |
| S3 | Verify sources, fetch, cache | P0 | 35 | S1 | NOT STARTED | Parquet with >= 8 stations, >= 90 days (or approved fallback) | |
| S4 | Cleaning and quality flags | P0 | 25 | S3 | NOT STARTED | Tests pass; hourly index per station | |
| S5 | Discover: 3 patterns | P0 | 25 | S4 | NOT STARTED | 3 patterns from real data, honest wording | |
| S6 | Features, label, baselines | P0 | 30 | S4 | NOT STARTED | Leakage test passes; split documented; baselines saved | |
| S7 | Models and evaluation | P0 | 30 | S6 | NOT STARTED | Models saved; honest metrics; pipeline runs | |
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

## Acceptance criteria
| ID | Criterion | Status | Evidence |
|---|---|---|---|
| AC1 | `python -m citypulse.pipeline` rebuilds data and model, no keys | NOT STARTED | |
| AC2 | App loads from cache offline, under 5 s | NOT STARTED | |
| AC3 | Map shows all stations, risk colour plus text label | NOT STARTED | |
| AC4 | At least 3 patterns auto-detected and shown | NOT STARTED | |
| AC5 | Per station: class, probabilities, band, top 3 drivers, quality badge | NOT STARTED | |
| AC6 | Needs-attention top 5 with risk, window, action | NOT STARTED | |
| AC7 | Download brief produces a one-page brief | NOT STARTED | |
| AC8 | Model vs both baselines on F1 and MAE, reported honestly | NOT STARTED | |
| AC9 | Live on free host; core journey verified on real URL | NOT STARTED | |

## Deferred (optional) items
| Item | Status | Reason |
|---|---|---|
| Modelled air-quality benchmark feature | DEFERRED | Optional |
| OpenStreetMap context | DEFERRED | Optional |
| GitHub Actions daily refresh | DEFERRED | Optional |
| PM10 and NO2 features | DEFERRED | Optional |
