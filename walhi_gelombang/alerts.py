"""Klasifikasi status peringatan dari Hs dan kecepatan angin."""
from __future__ import annotations

# Dipertahankan dari notebook sumber dan dibuat terpusat agar mudah direvisi.
THRESHOLDS = {
    "Hs_m": {"AMAN": 1.25, "WASPADA": 2.5},
    "wind_knot": {"AMAN": 15.0, "WASPADA": 25.0},
}

LEVEL_ORDER = {"AMAN": 0, "WASPADA": 1, "BAHAYA": 2}


def classify_parameter(value: float, thresholds: dict[str, float]) -> str:
    if value < thresholds["AMAN"]:
        return "AMAN"
    if value < thresholds["WASPADA"]:
        return "WASPADA"
    return "BAHAYA"


def precautionary_max(*statuses: str) -> str:
    return max(statuses, key=lambda s: LEVEL_ORDER[s])


def classify_realtime(hs_m: float, wind_speed_ms: float) -> tuple[str, dict]:
    wind_knot = wind_speed_ms * 1.94384
    hs_status = classify_parameter(hs_m, THRESHOLDS["Hs_m"])
    wind_status = classify_parameter(wind_knot, THRESHOLDS["wind_knot"])
    overall = precautionary_max(hs_status, wind_status)
    details = {
        "Hs_m": {"value": round(float(hs_m), 2), "status": hs_status},
        "wind_knot": {"value": round(float(wind_knot), 1), "status": wind_status},
    }
    return overall, details
