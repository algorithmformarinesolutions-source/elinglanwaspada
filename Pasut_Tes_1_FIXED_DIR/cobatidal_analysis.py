"""Tidal harmonic analysis utilities using UTide.

This module contains functions only. It does not install packages, call
ThingSpeak, display notebook output, or execute the analysis at import time.
"""
from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd

try:
    import utide
except ImportError as exc:  # keep import errors informative
    utide = None
    _UTIDE_IMPORT_ERROR = exc
else:
    _UTIDE_IMPORT_ERROR = None

COL_TIME = "time"
COL_WL = "water_level"
COL_PREDICTED = "water_level_predicted"

LATITUDE = -6.905105
LONGITUDE = 110.498692

UTIDE_CONSTIT = ["M2", "S2", "K1", "O1", "N2", "P1", "M4", "MS4"]
UTIDE_METHOD = "robust"
UTIDE_CONF_INT = "linear"
UTIDE_TREND = True
UTIDE_NODAL = True


def _require_utide() -> None:
    if utide is None:
        raise ImportError(
            "UTide belum terpasang. Jalankan di environment Python yang "
            "menjalankan run_pipeline.py: python -m pip install utide"
        ) from _UTIDE_IMPORT_ERROR


def prepare_tidal_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize an input DataFrame to columns ``time`` and ``water_level``."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df harus berupa pandas DataFrame.")
    if df.empty:
        raise ValueError("DataFrame pasut kosong.")

    data = df.copy()
    if "datetime" in data.columns and COL_TIME not in data.columns:
        data = data.rename(columns={"datetime": COL_TIME})
    if "tide_swl" in data.columns and COL_WL not in data.columns:
        data = data.rename(columns={"tide_swl": COL_WL})

    missing = [c for c in (COL_TIME, COL_WL) if c not in data.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing}")

    data[COL_TIME] = pd.to_datetime(data[COL_TIME], errors="coerce")
    data[COL_WL] = pd.to_numeric(data[COL_WL], errors="coerce")
    data = (
        data[[COL_TIME, COL_WL]]
        .dropna()
        .sort_values(COL_TIME)
        .drop_duplicates(subset=COL_TIME, keep="last")
        .reset_index(drop=True)
    )
    if data.empty:
        raise ValueError("Tidak ada pasangan waktu/water_level yang valid.")
    return data


def compute_basic_statistics(df: pd.DataFrame) -> dict:
    data = prepare_tidal_dataframe(df)
    wl = data[COL_WL].astype(float)
    return {
        "n_obs": int(wl.count()),
        "start": data[COL_TIME].min(),
        "end": data[COL_TIME].max(),
        "duration_days": (data[COL_TIME].max() - data[COL_TIME].min()).total_seconds() / 86400.0,
        "mean_sea_level": float(wl.mean()),
        "highest_water_level": float(wl.max()),
        "lowest_water_level": float(wl.min()),
        "std": float(wl.std()),
        "tidal_range": float(wl.max() - wl.min()),
    }


def run_harmonic_analysis(
    df: pd.DataFrame,
    latitude: float = LATITUDE,
    constit: Sequence[str] = UTIDE_CONSTIT,
    method: str = UTIDE_METHOD,
    conf_int: str = UTIDE_CONF_INT,
    trend: bool = UTIDE_TREND,
    nodal: bool = UTIDE_NODAL,
    verbose: bool = False,
):
    _require_utide()
    data = prepare_tidal_dataframe(df)
    coef = utide.solve(
        data[COL_TIME],
        data[COL_WL].to_numpy(),
        lat=latitude,
        constit=list(constit),
        method=method,
        conf_int=conf_int,
        trend=trend,
        nodal=nodal,
        verbose=verbose,
    )
    return coef


def compute_formzahl(coef) -> Optional[float]:
    names = list(coef["name"])
    amps = {name: amp for name, amp in zip(names, coef["A"])}
    required = ["M2", "S2", "K1", "O1"]
    missing = [c for c in required if c not in amps]
    if missing:
        return None
    denominator = amps["M2"] + amps["S2"]
    if denominator == 0:
        return None
    return float((amps["K1"] + amps["O1"]) / denominator)


def classify_tidal_regime(formzahl: Optional[float]) -> str:
    if formzahl is None:
        return "Tidak dapat diklasifikasikan (Formzahl tidak tersedia)"
    if formzahl <= 0.25:
        return "Pasut ganda (semidiurnal)"
    if formzahl <= 1.50:
        return "Pasut campuran condong ke ganda (mixed, mainly semidiurnal)"
    if formzahl <= 3.00:
        return "Pasut campuran condong ke tunggal (mixed, mainly diurnal)"
    return "Pasut tunggal (diurnal)"


def reconstruct_tide(coef, times) -> pd.DataFrame:
    _require_utide()
    times = pd.to_datetime(times)
    tide = utide.reconstruct(times, coef, verbose=False)
    return pd.DataFrame({COL_TIME: times, COL_PREDICTED: tide.h})


def run_full_analysis(
    df: pd.DataFrame,
    latitude: float = LATITUDE,
    reconstruct_on: str = "observed",
) -> dict:
    data = prepare_tidal_dataframe(df)
    coef = run_harmonic_analysis(data, latitude=latitude)
    formzahl = compute_formzahl(coef)
    classification = classify_tidal_regime(formzahl)
    prediction = (
        reconstruct_tide(coef, data[COL_TIME])
        if reconstruct_on == "observed"
        else pd.DataFrame(columns=[COL_TIME, COL_PREDICTED])
    )
    return {
        "coef": coef,
        "formzahl": formzahl,
        "classification": classification,
        "prediction": prediction,
    }
