"""Central configuration for the tidal pipeline."""
from __future__ import annotations
import os

THINGSPEAK_CHANNEL_ID = int(os.environ.get("THINGSPEAK_CHANNEL_ID", "3433993"))
THINGSPEAK_READ_API_KEY = os.environ.get("THINGSPEAK_READ_API_KEY", "38FITZRV5JCZN75R")
THINGSPEAK_WRITE_API_KEY = os.environ.get("THINGSPEAK_WRITE_API_KEY", "57GQO1KIZZNQ4CBR")
THINGSPEAK_BASE_URL = "https://api.thingspeak.com"

FIELD_MAP = {1: "tide_swl"}

STATION_LATITUDE = float(os.environ.get("STATION_LATITUDE", "-6.905105"))
STATION_LONGITUDE = float(os.environ.get("STATION_LONGITUDE", "110.498692"))
LOCAL_TIMEZONE = "Asia/Jakarta"
DEFAULT_SAMPLE_FREQ = "15min"

COL_TIME = "time"
COL_WL = "water_level"
COL_WL_PREDICTED = "water_level_predicted"
DEFAULT_THRESHOLD = float(os.environ.get("TIDE_THRESHOLD", "1.25"))
OUTPUT_FOLDER = "output"
