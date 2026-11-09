"""Pra-pemrosesan observasi angin."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _circular_direction_from_components(sin_component: pd.Series, cos_component: pd.Series) -> pd.Series:
    angle = np.degrees(np.arctan2(sin_component, cos_component)) % 360.0
    magnitude = np.hypot(sin_component, cos_component)
    return pd.Series(np.where(magnitude > 1e-12, angle, np.nan), index=sin_component.index)


def resample_hourly(
    df: pd.DataFrame,
    frequency: str = "1h",
    interpolation_limit: int = 3,
) -> pd.DataFrame:
    """Samakan resolusi dan isi hanya gap kecil.

    Kecepatan diresample dengan mean aritmetika. Arah diresample menggunakan
    circular mean dan diinterpolasi melalui komponen sin/cos agar wrap 0/360 aman.
    """
    if df.empty:
        return pd.DataFrame(columns=["datetime", "wind_speed", "wind_dir"])

    work = df[["datetime", "wind_speed", "wind_dir"]].copy()
    work = work.sort_values("datetime").set_index("datetime")

    angle_rad = np.deg2rad(work["wind_dir"])
    work["dir_sin"] = np.sin(angle_rad)
    work["dir_cos"] = np.cos(angle_rad)

    hourly = work[["wind_speed", "dir_sin", "dir_cos"]].resample(frequency).mean()

    # Hanya gap pendek yang diisi, sama seperti intent notebook awal.
    hourly["wind_speed"] = hourly["wind_speed"].interpolate(
        method="time", limit=interpolation_limit, limit_area="inside"
    )
    hourly["dir_sin"] = hourly["dir_sin"].interpolate(
        method="time", limit=interpolation_limit, limit_area="inside"
    )
    hourly["dir_cos"] = hourly["dir_cos"].interpolate(
        method="time", limit=interpolation_limit, limit_area="inside"
    )

    hourly["wind_dir"] = _circular_direction_from_components(hourly["dir_sin"], hourly["dir_cos"])
    hourly = hourly.drop(columns=["dir_sin", "dir_cos"]).reset_index()
    return hourly
