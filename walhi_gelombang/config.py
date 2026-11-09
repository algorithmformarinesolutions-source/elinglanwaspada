"""Konfigurasi proyek estimasi gelombang SMB/CERC untuk EWS WALHI.

Rahasia API dibaca dari file .env / environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    # ThingSpeak
    thingspeak_base_url: str = os.environ.get("THINGSPEAK_BASE_URL", "https://api.thingspeak.com")
    channel_id: int = int(os.environ.get("THINGSPEAK_CHANNEL_ID", "3433995"))
    read_api_key: str = os.environ.get("THINGSPEAK_READ_API_KEY", "")
    write_api_key: str = os.environ.get("THINGSPEAK_WRITE_API_KEY", "")  # disimpan, tidak dipakai untuk read
    wind_speed_field: str = os.environ.get("WIND_SPEED_FIELD", "field1")
    wind_dir_field: str = os.environ.get("WIND_DIR_FIELD", "field2")
    max_results_per_request: int = int(os.environ.get("THINGSPEAK_MAX_RESULTS", "8000"))
    request_timeout_seconds: int = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))

    # Station
    station_latitude: float = float(os.environ.get("STATION_LATITUDE", "-6.905105"))
    station_longitude: float = float(os.environ.get("STATION_LONGITUDE", "110.498692"))
    local_timezone: str = os.environ.get("LOCAL_TIMEZONE", "Asia/Jakarta")

    # Processing
    resample_frequency: str = os.environ.get("RESAMPLE_FREQUENCY", "1h")
    max_interpolation_gap: int = int(os.environ.get("MAX_INTERPOLATION_GAP", "3"))

    # SMB/CERC parameters (dipertahankan dari notebook, dapat diubah lewat .env)
    fetch_meter: float = float(os.environ.get("FETCH_METER", "150000"))
    duration_hours: float = float(os.environ.get("DURATION_HOURS", "3"))

    # Output
    output_dir: Path = Path(os.environ.get("OUTPUT_DIR", str(BASE_DIR / "outputs")))
    auto_open_plots: bool = os.environ.get("AUTO_OPEN_PLOTS", "true").strip().lower() in {
        "1", "true", "yes", "y", "on"
    }


SETTINGS = Settings()
