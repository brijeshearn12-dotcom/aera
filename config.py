"""Configuration constants and path definitions for AERA."""

from pathlib import Path

CITY = "Mumbai"

GOOD_MAX = 60
UNHEALTHY_MAX = 250

FORECAST_HORIZON_HOURS = 24
GAP_FILL_LIMIT_HOURS = 3
STUCK_VALUE_RUN_LENGTH = 6

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
SAMPLE_DATA_DIR = PROJECT_ROOT / "data" / "sample"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
MODELS_DIR = PROJECT_ROOT / "models"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
