"""Perhitungan estimasi gelombang lokal dengan metode SMB/CERC (SPM 1984)."""
from __future__ import annotations

import numpy as np
import pandas as pd

G = 9.81


def wind_stress_factor(wind_speed_ms):
    """Konversi kecepatan angin U (m/s) menjadi wind-stress factor U_A."""
    u = np.asarray(wind_speed_ms, dtype=float)
    return 0.71 * np.power(u, 1.23)


def _valid_positive(u):
    arr = np.asarray(u, dtype=float)
    return np.isfinite(arr) & (arr > 0)


def fetch_limited(wind_speed_ms, fetch_meter: float):
    """Hs dan Ts untuk kondisi fetch-limited."""
    u = np.asarray(wind_speed_ms, dtype=float)
    hs = np.full_like(u, np.nan, dtype=float)
    ts = np.full_like(u, np.nan, dtype=float)

    valid = _valid_positive(u)
    if np.any(valid):
        ua = wind_stress_factor(u[valid])
        gf_ua2 = G * fetch_meter / np.square(ua)
        ghs_ua2 = 0.283 * np.tanh(0.0125 * np.power(gf_ua2, 0.42))
        gts_ua = 7.54 * np.tanh(0.077 * np.power(gf_ua2, 0.25))
        hs[valid] = ghs_ua2 * np.square(ua) / G
        ts[valid] = gts_ua * ua / G

    calm = np.isfinite(u) & (u <= 0)
    hs[calm] = 0.0
    ts[calm] = 0.0
    return hs, ts


def duration_limited(wind_speed_ms, duration_hours: float):
    """Hs dan Ts untuk kondisi duration-limited."""
    u = np.asarray(wind_speed_ms, dtype=float)
    hs = np.full_like(u, np.nan, dtype=float)
    ts = np.full_like(u, np.nan, dtype=float)

    valid = _valid_positive(u)
    if np.any(valid):
        ua = wind_stress_factor(u[valid])
        duration_seconds = duration_hours * 3600.0
        gt_ua = G * duration_seconds / ua
        gfeff_ua2 = np.power(gt_ua / 68.8, 1.0 / 0.75)
        hs[valid] = 0.283 * np.tanh(0.0125 * np.power(gfeff_ua2, 0.42)) * np.square(ua) / G
        ts[valid] = 7.54 * np.tanh(0.077 * np.power(gfeff_ua2, 0.25)) * ua / G

    calm = np.isfinite(u) & (u <= 0)
    hs[calm] = 0.0
    ts[calm] = 0.0
    return hs, ts


def estimate_wave(wind_speed_ms, fetch_meter: float, duration_hours: float):
    """Estimasi governing SMB, bukan forecast waktu ke depan.

    Kondisi governing dipilih dari Hs yang lebih kecil antara fetch-limited dan
    duration-limited. Data NaN tetap NaN. Angin <= 0 dianggap calm.
    """
    u = np.asarray(wind_speed_ms, dtype=float)
    hs_f, ts_f = fetch_limited(u, fetch_meter)
    hs_d, ts_d = duration_limited(u, duration_hours)

    choose_fetch = hs_f <= hs_d
    hs = np.where(choose_fetch, hs_f, hs_d)
    ts = np.where(choose_fetch, ts_f, ts_d)
    condition = np.where(choose_fetch, "fetch-limited", "duration-limited").astype(object)

    calm = np.isfinite(u) & (u <= 0)
    condition[calm] = "calm"
    condition[~np.isfinite(u)] = None
    return hs, ts, condition


def add_wave_estimates(df: pd.DataFrame, fetch_meter: float, duration_hours: float) -> pd.DataFrame:
    """Tambahkan Hs, Ts, kondisi governing, dan arah gelombang ke DataFrame."""
    result = df.copy()
    hs, ts, condition = estimate_wave(result["wind_speed"].to_numpy(), fetch_meter, duration_hours)
    result["Hs_m"] = hs
    result["Ts_s"] = ts
    result["kondisi"] = condition
    result["arah_gel"] = result["wind_dir"]  # asumsi SMB lokal: arah gelombang mengikuti arah datang angin
    return result
