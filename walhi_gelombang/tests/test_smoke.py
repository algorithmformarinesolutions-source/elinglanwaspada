from __future__ import annotations

import numpy as np
import pandas as pd

from processing import resample_hourly
from smb_wave import add_wave_estimates, estimate_wave


def test_single_notebook_example():
    hs, ts, condition = estimate_wave([8.0], 150_000, 6)
    assert np.isfinite(hs[0]) and hs[0] > 0
    assert np.isfinite(ts[0]) and ts[0] > 0
    assert condition[0] in {"fetch-limited", "duration-limited"}


def test_circular_direction_resampling():
    t = pd.to_datetime(["2026-09-01 00:05", "2026-09-01 00:35"], utc=True).tz_convert("Asia/Jakarta")
    df = pd.DataFrame({"datetime": t, "wind_speed": [5.0, 5.0], "wind_dir": [359.0, 1.0]})
    out = resample_hourly(df)
    direction = float(out.loc[0, "wind_dir"])
    assert direction < 5 or direction > 355


def test_wave_dataframe_columns():
    t = pd.date_range("2026-09-01", periods=4, freq="h", tz="Asia/Jakarta")
    df = pd.DataFrame({"datetime": t, "wind_speed": [2.0, 4.0, 6.0, 8.0], "wind_dir": [0, 90, 180, 270]})
    out = add_wave_estimates(df, 150_000, 3)
    assert {"Hs_m", "Ts_s", "kondisi", "arah_gel"}.issubset(out.columns)
    assert out["Hs_m"].notna().all()
