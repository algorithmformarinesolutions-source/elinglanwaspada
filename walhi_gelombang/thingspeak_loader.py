"""Pengambilan data observasi angin dari ThingSpeak."""
from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd
import requests

from config import Settings

LOGGER = logging.getLogger(__name__)


def get_run_window(local_timezone: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Rentang data = tepat satu bulan kalender sebelum saat script dijalankan sampai saat itu."""
    date_end = pd.Timestamp.now(tz=local_timezone)
    date_start = date_end - pd.DateOffset(months=1)
    return date_start, date_end


def _format_thingspeak_time(ts: pd.Timestamp) -> str:
    """ThingSpeak feed timestamps diperlakukan dalam UTC."""
    return ts.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S")


def _request_interval(
    session: requests.Session,
    settings: Settings,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
) -> list[dict]:
    """Ambil satu interval. Jika menyentuh batas 8000 baris, interval dibelah otomatis."""
    url = f"{settings.thingspeak_base_url.rstrip('/')}/channels/{settings.channel_id}/feeds.json"
    params = {
        "start": _format_thingspeak_time(start_utc),
        "end": _format_thingspeak_time(end_utc),
        "results": settings.max_results_per_request,
    }
    if settings.read_api_key:
        params["api_key"] = settings.read_api_key

    try:
        response = session.get(url, params=params, timeout=settings.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        # Jangan teruskan repr exception karena URL request dapat memuat private API key.
        raise RuntimeError(
            f"Gagal terhubung ke ThingSpeak channel {settings.channel_id}. "
            "Periksa koneksi internet, Channel ID, dan Read API Key."
        ) from None
    except ValueError:
        raise RuntimeError("Respons ThingSpeak bukan JSON yang valid.") from None
    feeds = payload.get("feeds", [])

    # Jika tepat/lebih dari limit, ada risiko data terpotong. Belah interval secara rekursif.
    if len(feeds) >= settings.max_results_per_request:
        span = end_utc - start_utc
        if span <= timedelta(minutes=1):
            raise RuntimeError(
                "ThingSpeak mengembalikan jumlah data sebesar batas maksimum bahkan pada interval <= 1 menit. "
                "Naikkan strategi pengambilan/cek frekuensi sensor."
            )
        midpoint = start_utc + span / 2
        LOGGER.info("Interval padat (%s baris); membelah request menjadi dua.", len(feeds))
        left = _request_interval(session, settings, start_utc, midpoint)
        right = _request_interval(session, settings, midpoint, end_utc)
        return left + right

    return feeds


def fetch_thingspeak_range(
    settings: Settings,
    date_start: pd.Timestamp,
    date_end: pd.Timestamp,
) -> pd.DataFrame:
    """Ambil seluruh feed dalam rentang waktu, lalu normalisasi menjadi observasi angin.

    Output timezone-aware pada kolom ``datetime`` dengan timezone lokal.
    Tidak ada fallback data sintetis: kegagalan API akan diteruskan sebagai error.
    """
    if date_start.tzinfo is None or date_end.tzinfo is None:
        raise ValueError("date_start dan date_end harus timezone-aware.")
    if date_start >= date_end:
        raise ValueError("date_start harus lebih awal daripada date_end.")
    if not settings.read_api_key:
        LOGGER.warning("THINGSPEAK_READ_API_KEY kosong; channel private kemungkinan menolak request.")

    start_utc = date_start.tz_convert("UTC")
    end_utc = date_end.tz_convert("UTC")

    # Request awal dibagi per hari agar aman terhadap limit 8000 entri per request.
    feeds: list[dict] = []
    with requests.Session() as session:
        cursor = start_utc
        while cursor < end_utc:
            chunk_end = min(cursor + pd.Timedelta(days=1), end_utc)
            feeds.extend(_request_interval(session, settings, cursor, chunk_end))
            cursor = chunk_end

    if not feeds:
        return pd.DataFrame(columns=["entry_id", "datetime", "wind_speed", "wind_dir"])

    df = pd.json_normalize(feeds)
    required = {"created_at", settings.wind_speed_field, settings.wind_dir_field}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(
            f"Field ThingSpeak yang dibutuhkan tidak ditemukan: {sorted(missing)}. "
            f"Periksa WIND_SPEED_FIELD/WIND_DIR_FIELD di .env. Kolom tersedia: {list(df.columns)}"
        )

    df["wind_speed"] = pd.to_numeric(df[settings.wind_speed_field], errors="coerce")
    df["wind_dir"] = pd.to_numeric(df[settings.wind_dir_field], errors="coerce") % 360.0
    df["datetime"] = pd.to_datetime(df["created_at"], utc=True).dt.tz_convert(settings.local_timezone)

    if "entry_id" not in df.columns:
        df["entry_id"] = pd.NA

    df = df[["entry_id", "datetime", "wind_speed", "wind_dir"]]
    df = df.drop_duplicates(subset=["entry_id", "datetime"], keep="last")
    df = df.sort_values("datetime")

    # Pastikan request boundary tidak menyisakan nilai di luar rentang persis.
    df = df[(df["datetime"] >= date_start) & (df["datetime"] <= date_end)]
    df = df.dropna(subset=["wind_speed", "wind_dir"]).reset_index(drop=True)
    return df
