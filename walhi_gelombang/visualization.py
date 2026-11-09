"""Pembuatan grafik sebagai file, tanpa plt.show() yang memblokir pipeline."""
from __future__ import annotations

from pathlib import Path

import matplotlib

# Backend non-interaktif: plotting selalu bisa selesai walau dijalankan dari terminal/headless.
matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["figure.figsize"] = (11, 4)
plt.rcParams["font.size"] = 10


def save_monthly_timeseries(df: pd.DataFrame, output_path: Path) -> Path:
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)

    axes[0].plot(df["datetime"], df["wind_speed"], lw=1)
    axes[0].set_ylabel("Kec. Angin (m/s)")
    axes[0].set_title("Estimasi Gelombang 1 Bulan dari Data Angin — Metode SMB/CERC")
    axes[0].grid(alpha=0.3)

    axes[1].plot(df["datetime"], df["Hs_m"], lw=1)
    axes[1].set_ylabel("Hs (m)")
    axes[1].grid(alpha=0.3)

    axes[2].plot(df["datetime"], df["Ts_s"], lw=1)
    axes[2].set_ylabel("Ts (s)")
    axes[2].set_xlabel("Tanggal")
    axes[2].grid(alpha=0.3)
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def save_wave_rose(df: pd.DataFrame, output_path: Path) -> Path:
    valid = df[["arah_gel", "Hs_m"]].dropna()
    arah_rad = np.deg2rad(valid["arah_gel"].to_numpy())

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    scatter = ax.scatter(arah_rad, valid["Hs_m"], c=valid["Hs_m"], cmap="viridis", s=10, alpha=0.6)
    ax.set_title("Distribusi Arah vs Tinggi Gelombang (Hs) — 1 Bulan", pad=20)
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.1)
    colorbar.set_label("Hs (m)")

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path
