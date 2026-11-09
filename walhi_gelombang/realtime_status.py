"""Cek satu kali status dari entri ThingSpeak paling baru, tanpa polling/blocking loop."""
from __future__ import annotations

import logging

import pandas as pd
import requests

from alerts import classify_realtime
from config import SETTINGS
from smb_wave import estimate_wave


def fetch_latest():
    s = SETTINGS
    url = f"{s.thingspeak_base_url.rstrip('/')}/channels/{s.channel_id}/feeds.json"
    params = {"results": 1}
    if s.read_api_key:
        params["api_key"] = s.read_api_key
    try:
        response = requests.get(url, params=params, timeout=s.request_timeout_seconds)
        response.raise_for_status()
        feeds = response.json().get("feeds", [])
    except requests.RequestException:
        # Hindari mencetak URL lengkap yang dapat memuat private API key.
        raise RuntimeError(
            f"Gagal terhubung ke ThingSpeak channel {s.channel_id}. "
            "Periksa koneksi internet, Channel ID, dan Read API Key."
        ) from None
    except ValueError:
        raise RuntimeError("Respons ThingSpeak bukan JSON yang valid.") from None
    if not feeds:
        raise RuntimeError("Tidak ada feed terbaru dari ThingSpeak.")

    feed = feeds[-1]
    when = pd.to_datetime(feed["created_at"], utc=True).tz_convert(s.local_timezone)
    u = float(feed[s.wind_speed_field])
    direction = float(feed[s.wind_dir_field]) % 360.0
    hs, ts, cond = estimate_wave([u], s.fetch_meter, s.duration_hours)
    status, detail = classify_realtime(float(hs[0]), u)
    return when, u, direction, float(hs[0]), float(ts[0]), str(cond[0]), status, detail


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    when, u, direction, hs, ts, condition, status, detail = fetch_latest()
    print("=" * 60)
    print(f"WAKTU DATA   : {when}")
    print(f"Kec. angin   : {u:.2f} m/s ({u * 1.94384:.1f} knot), arah {direction:.1f}°")
    print(f"Hs / Ts      : {hs:.2f} m / {ts:.2f} s ({condition})")
    print(f"Status Hs    : {detail['Hs_m']['status']}")
    print(f"Status angin : {detail['wind_knot']['status']}")
    print(f"STATUS AKHIR : {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
