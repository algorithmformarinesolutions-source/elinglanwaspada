"""Visualization utilities for the tidal pipeline.

The operational graph shows three elements:
1. the processed water-level series (direct sensor observations combined with
   preprocessing interpolation),
2. the UTide forecast series, and
3. the high-wave threshold line.

Historical UTide reconstruction is intentionally excluded from the plot.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

import config

COL_TIME = config.COL_TIME
COL_WL = config.COL_WL
COL_DATA_SOURCE = config.COL_DATA_SOURCE


def _prepare_processed_series(df: pd.DataFrame) -> pd.DataFrame:
    """Return a chronological processed observed+interpolated series."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input grafik processed_df harus berupa pandas DataFrame.")
    if df.empty:
        return pd.DataFrame(columns=[COL_TIME, COL_WL, COL_DATA_SOURCE])

    missing = [c for c in (COL_TIME, COL_WL) if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom processed series tidak ditemukan: {missing}")

    data = df.copy()
    data[COL_TIME] = pd.to_datetime(data[COL_TIME], errors="coerce")
    data[COL_WL] = pd.to_numeric(data[COL_WL], errors="coerce")

    keep = [COL_TIME, COL_WL]
    if COL_DATA_SOURCE in data.columns:
        keep.append(COL_DATA_SOURCE)

    return (
        data[keep]
        .dropna(subset=[COL_TIME, COL_WL])
        .sort_values(COL_TIME)
        .drop_duplicates(subset=COL_TIME, keep="last")
        .reset_index(drop=True)
    )


def _prepare_forecast_series(df: pd.DataFrame) -> pd.DataFrame:
    """Return a chronological UTide forecast series ready for plotting."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input grafik forecast_df harus berupa pandas DataFrame.")
    if df.empty:
        return pd.DataFrame(columns=[COL_TIME, COL_WL])

    data = df.copy()
    time_col = COL_TIME if COL_TIME in data.columns else "time"
    wl_col_candidates = [COL_WL, "water_level_predicted", "prediction", "forecast"]
    wl_col = next((c for c in wl_col_candidates if c in data.columns), None)
    if wl_col is None:
        raise ValueError(
            "Kolom forecast water level tidak ditemukan. "
            f"Kolom tersedia: {list(data.columns)}"
        )

    data[time_col] = pd.to_datetime(data[time_col], errors="coerce")
    data[wl_col] = pd.to_numeric(data[wl_col], errors="coerce")

    prepared = (
        data[[time_col, wl_col]]
        .rename(columns={time_col: COL_TIME, wl_col: COL_WL})
        .dropna(subset=[COL_TIME, COL_WL])
        .sort_values(COL_TIME)
        .drop_duplicates(subset=COL_TIME, keep="last")
        .reset_index(drop=True)
    )
    return prepared


def plot_tide(
    processed_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    threshold: float = config.DEFAULT_THRESHOLD,
    title: str = "Grafik Pasang Surut — Observasi + Interpolasi, Forecast, dan Threshold",
):
    """Plot processed series, forecast, and the threshold line.

    Historical UTide reconstruction is deliberately excluded from the graph.
    The chart focuses on:
    - data pasut hasil preprocessing (observasi + interpolasi),
    - garis forecast UTide, and
    - garis threshold gelombang tinggi.
    """
    processed = _prepare_processed_series(processed_df)
    if processed.empty:
        raise ValueError("Tidak ada data observasi/interpolasi untuk divisualisasikan.")

    forecast = _prepare_forecast_series(forecast_df)
    if forecast.empty:
        raise ValueError("Tidak ada data forecast untuk divisualisasikan.")

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(
        processed[COL_TIME],
        processed[COL_WL],
        linestyle="-",
        linewidth=1.6,
        label="Data pasut (observasi + interpolasi)",
    )

    ax.plot(
        forecast[COL_TIME],
        forecast[COL_WL],
        linestyle="-",
        linewidth=1.8,
        label="Forecast pasut",
    )

    ax.axhline(
        y=float(threshold),
        linestyle="--",
        linewidth=1.5,
        label=f"Threshold gelombang tinggi ({float(threshold):.0f} {config.WATER_LEVEL_UNIT})",
    )

    ax.set_xlabel("Waktu")
    ax.set_ylabel(f"Water Level ({config.WATER_LEVEL_UNIT})")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    plt.show()
    return fig, ax
