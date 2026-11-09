"""Central configuration for the tidal pipeline.

Direct-run design
-----------------
- ``PERIOD_DATE_START`` is resolved automatically to the local date/time
  (to the second) when ``run_pipeline.py`` starts.
- ``PERIOD_DATE_END`` is exactly one calendar month after that start time.
- Because ThingSpeak cannot provide observations from the future, the
  historical analysis window is separated from the operational/forecast
  window. By default, one calendar month of observations immediately before
  ``PERIOD_DATE_START`` is requested for preprocessing and harmonic fitting.
- External HOBO validation is an optional sidecar. It never changes the
  tidal analysis, forecast, threshold, calendar, or visualization.
"""
from __future__ import annotations

import os

import pandas as pd

# ============================================================
# THINGSPEAK / STATION
# ============================================================
THINGSPEAK_CHANNEL_ID = int(os.environ.get("THINGSPEAK_CHANNEL_ID", "3433993"))
THINGSPEAK_READ_API_KEY = os.environ.get("THINGSPEAK_READ_API_KEY", "38FITZRV5JCZN75R")
THINGSPEAK_WRITE_API_KEY = os.environ.get("THINGSPEAK_WRITE_API_KEY", "57GQO1KIZZNQ4CBR")
THINGSPEAK_BASE_URL = "https://api.thingspeak.com"

FIELD_MAP = {1: "tide_swl"}

STATION_LATITUDE = float(os.environ.get("STATION_LATITUDE", "-6.905105"))
STATION_LONGITUDE = float(os.environ.get("STATION_LONGITUDE", "110.498692"))
LOCAL_TIMEZONE = "Asia/Jakarta"

# ============================================================
# COLUMN NAMES / UNIT
# ============================================================
COL_TIME = "time"
COL_WL = "water_level"
COL_WL_PREDICTED = "water_level_predicted"
COL_DATA_SOURCE = "data_source"
WATER_LEVEL_UNIT = "cm"

# ============================================================
# DYNAMIC OPERATIONAL PERIOD
# ============================================================
# Evaluated once when config.py is imported by run_pipeline.py.
# floor("s") ensures the start follows the actual second at run time.
_PIPELINE_RUN_LOCAL = pd.Timestamp.now(tz=LOCAL_TIMEZONE).floor("s")
PIPELINE_RUN_AT = _PIPELINE_RUN_LOCAL

# User-requested period: NOW -> +1 calendar month.
PERIOD_DATE_START_TS = _PIPELINE_RUN_LOCAL.tz_localize(None)
PERIOD_DATE_END_TS = PERIOD_DATE_START_TS + pd.DateOffset(months=1)
PERIOD_DATE_START = PERIOD_DATE_START_TS.strftime("%Y-%m-%d %H:%M:%S")
PERIOD_DATE_END = PERIOD_DATE_END_TS.strftime("%Y-%m-%d %H:%M:%S")

# ============================================================
# HISTORICAL DATA WINDOW FOR THINGSPEAK
# ============================================================
# Future observations do not exist yet. Harmonic analysis therefore uses a
# historical lookback ending at PERIOD_DATE_START. The default is one calendar
# month, which can be changed without changing the operational forecast period.
DEFAULT_DATA_MODE = os.environ.get("TIDE_DATA_MODE", "period").lower()
DEFAULT_HISTORY_MONTHS = int(os.environ.get("TIDE_HISTORY_MONTHS", "1"))

_DEFAULT_HISTORY_END_TS = PERIOD_DATE_START_TS
_DEFAULT_HISTORY_START_TS = _DEFAULT_HISTORY_END_TS - pd.DateOffset(months=DEFAULT_HISTORY_MONTHS)
DEFAULT_START = os.environ.get(
    "TIDE_START",
    _DEFAULT_HISTORY_START_TS.strftime("%Y-%m-%d %H:%M:%S"),
)
DEFAULT_END = os.environ.get(
    "TIDE_END",
    _DEFAULT_HISTORY_END_TS.strftime("%Y-%m-%d %H:%M:%S"),
)
DEFAULT_LATEST_RESULTS = int(os.environ.get("TIDE_LATEST_RESULTS", "8000"))

# ============================================================
# PREPROCESSING / ANALYSIS
# ============================================================
DEFAULT_SAMPLE_FREQ = os.environ.get("TIDE_SAMPLE_FREQ", "15min")
DEFAULT_INTERPOLATION_METHOD = os.environ.get("TIDE_INTERPOLATION_METHOD", "auto")
DEFAULT_VALID_MIN = None
DEFAULT_VALID_MAX = None

# ============================================================
# EXTERNAL HOBO VALIDATION (SIDECAR / INDEPENDENT)
# ============================================================
# Validation compares HOBO against the processed sensor series
# (raw observations + interpolation), NOT against UTide reconstruction.
ENABLE_HOBO_VALIDATION = os.environ.get("HOBO_VALIDATION_ENABLED", "1").strip().lower() not in {
    "0", "false", "no", "off"
}

DEFAULT_VALIDATION_CSV = os.environ.get(
    "HOBO_VALIDATION_CSV",
    "data pasut hobo 25-27 juli 2026.csv",
)
DEFAULT_VALIDATION_DATE_COL = "Date"
DEFAULT_VALIDATION_CLOCK_COL = "Time"
DEFAULT_VALIDATION_VALUE_COL = "Water Level"
DEFAULT_VALIDATION_SEP = ";"
DEFAULT_VALIDATION_TIME_MODE = "12h_no_ampm"
DEFAULT_VALIDATION_START_DATETIME = os.environ.get(
    "HOBO_START_DATETIME",
    "2026-07-25 13:29:00",
)
DEFAULT_VALIDATION_DATE_FORMAT = "%m/%d/%y"
DEFAULT_VALIDATION_EXPECTED_INTERVAL = "1min"

# Unit harmonization and mounting-height correction.
# The current HOBO export stores water level in metres, while the main sensor
# pipeline uses centimetres. Values are converted before statistics are made.
DEFAULT_VALIDATION_INPUT_UNIT = os.environ.get("HOBO_INPUT_UNIT", "m").lower()
DEFAULT_VALIDATION_TARGET_UNIT = WATER_LEVEL_UNIT

# Distance between the installed HOBO sensor and bottom/reference point.
# Current project value: 20 cm. Change this in config.py if field metadata changes.
DEFAULT_VALIDATION_BOTTOM_OFFSET = float(os.environ.get("HOBO_BOTTOM_OFFSET", "20"))
DEFAULT_VALIDATION_BOTTOM_OFFSET_UNIT = os.environ.get("HOBO_BOTTOM_OFFSET_UNIT", "cm").lower()
# "subtract": corrected = converted_value - offset
# "add":      corrected = converted_value + offset
# "none":     only unit conversion, no vertical correction
DEFAULT_VALIDATION_CORRECTION = os.environ.get("HOBO_CORRECTION", "subtract").lower()

# Validation alignment. HOBO is reduced to the same grid as the processed
# sensor (e.g. 15 min) before calculating RMSE/MAE/bias/etc.
DEFAULT_VALIDATION_ALIGN_FREQ = DEFAULT_SAMPLE_FREQ

# ============================================================
# FORECAST / THRESHOLD / OUTPUT
# ============================================================
# Direct-run forecast uses the dynamic operational period exactly:
# PERIOD_DATE_START -> PERIOD_DATE_END. DEFAULT_FORECAST_DAYS remains available
# only as a CLI/backward-compatible fallback.
DEFAULT_FORECAST_DAYS = int(os.environ.get("TIDE_FORECAST_DAYS", "30"))
DEFAULT_FORECAST_INTERVAL = os.environ.get("TIDE_FORECAST_INTERVAL", "1h")
DEFAULT_THRESHOLD = int(os.environ.get("TIDE_THRESHOLD", "125"))
OUTPUT_FOLDER = os.environ.get("TIDE_OUTPUT_FOLDER", "output")
SHOW_PLOT = os.environ.get("TIDE_SHOW_PLOT", "1").strip().lower() not in {
    "0", "false", "no", "off"
}
