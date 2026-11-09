"""External HOBO validation for the processed tide-sensor series.

This module is intentionally independent from harmonic reconstruction,
forecasting, threshold classification, and visualization.

Validation target
-----------------
The HOBO series is compared with the *processed sensor series* produced by
``preprocessing.py``: observed/raw sensor bins plus values filled by the
selected interpolation method. UTide reconstruction is NOT used as the
validation target.

HOBO-specific handling
----------------------
1. Reconstruct the July 2026 12-hour clock export using a known first-record
   datetime anchor.
2. Convert HOBO water-level units to the main pipeline unit (cm by default).
3. Apply an explicit vertical mounting/bottom offset when configured.
4. Aggregate HOBO to the same temporal grid as the processed sensor before
   calculating RMSE, MAE, bias, correlation, R², and NSE.

A validation failure should be handled by ``run_pipeline.py`` as a sidecar
warning and must not alter or stop the main tide visualization/forecast flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

COL_TIME = "time"
COL_WL = "water_level"
COL_DATA_SOURCE = "data_source"
COL_HOBO = "hobo_water_level"
COL_SENSOR = "sensor_processed_water_level"
COL_RESIDUAL = "residual"


@dataclass
class ValidationResult:
    metrics: dict
    merged: pd.DataFrame
    timing_diagnostics: Optional[pd.DataFrame] = None


# ---------------------------------------------------------------------------
# Time normalization and HOBO clock reconstruction
# ---------------------------------------------------------------------------

def _strip_timezone(series: pd.Series) -> pd.Series:
    """Keep station-local clock time while removing timezone information."""
    dt = pd.to_datetime(series, errors="coerce")
    try:
        if getattr(dt.dt, "tz", None) is not None:
            dt = dt.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return dt


def _clock12_to_seconds(clock: pd.Series) -> pd.Series:
    """Convert a 12-hour clock without AM/PM to seconds in [0, 43200)."""
    text = clock.astype(str).str.strip()
    parts = text.str.extract(
        r"^(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})$"
    )
    numeric = parts.apply(pd.to_numeric, errors="coerce")
    invalid = (
        numeric.isna().any(axis=1)
        | ~numeric["hour"].between(1, 12)
        | ~numeric["minute"].between(0, 59)
        | ~numeric["second"].between(0, 59)
    )
    if invalid.any():
        sample = text.loc[invalid].head(10).tolist()
        raise ValueError(
            "Format Time HOBO tidak sesuai clock 12-jam HH:MM:SS tanpa AM/PM. "
            f"Contoh nilai bermasalah: {sample}"
        )

    hour12 = numeric["hour"].astype(int) % 12
    return (
        hour12 * 3600
        + numeric["minute"].astype(int) * 60
        + numeric["second"].astype(int)
    ).astype(int)


def reconstruct_hobo_12h_timestamps(
    date_series: pd.Series,
    clock_series: pd.Series,
    start_datetime: str | pd.Timestamp,
    date_format: str = "%m/%d/%y",
    expected_interval: str | None = "1min",
) -> tuple[pd.Series, pd.DataFrame]:
    """Reconstruct chronological timestamps from a 12-hour export without AM/PM."""
    if start_datetime is None:
        raise ValueError(
            "start_datetime wajib untuk time_mode='12h_no_ampm' karena clock "
            "tanpa AM/PM bersifat ambigu."
        )

    anchor = pd.Timestamp(start_datetime)
    if anchor.tzinfo is not None:
        anchor = anchor.tz_localize(None)

    exported_date = pd.to_datetime(
        date_series.astype(str).str.strip(),
        format=date_format,
        errors="coerce",
    )
    if exported_date.isna().any():
        sample = date_series.loc[exported_date.isna()].head(10).tolist()
        raise ValueError(
            f"Sebagian Date HOBO gagal diparse dengan format {date_format!r}: {sample}"
        )

    clock_seconds = _clock12_to_seconds(clock_series).to_numpy(dtype=np.int64)
    if len(clock_seconds) == 0:
        return pd.Series(dtype="datetime64[ns]"), pd.DataFrame()

    anchor_clock_seconds = (
        (anchor.hour % 12) * 3600 + anchor.minute * 60 + anchor.second
    )
    if int(clock_seconds[0]) != int(anchor_clock_seconds):
        raise ValueError(
            "Clock pada start_datetime tidak cocok dengan Time baris pertama HOBO. "
            f"Baris pertama={clock_series.iloc[0]!r}, start_datetime={anchor}."
        )

    first_exported_date = exported_date.iloc[0].normalize()
    if anchor.normalize() != first_exported_date:
        raise ValueError(
            "Tanggal start_datetime tidak cocok dengan Date baris pertama HOBO. "
            f"Date pertama={first_exported_date.date()}, start_datetime={anchor}."
        )

    elapsed = np.zeros(len(clock_seconds), dtype=np.int64)
    interval_seconds = np.full(len(clock_seconds), np.nan, dtype=float)
    for i in range(1, len(clock_seconds)):
        delta = int(clock_seconds[i] - clock_seconds[i - 1])
        if delta < 0:
            delta += 12 * 3600
        elapsed[i] = elapsed[i - 1] + delta
        interval_seconds[i] = float(delta)

    reconstructed = pd.Series(
        anchor + pd.to_timedelta(elapsed, unit="s"),
        index=date_series.index,
        name=COL_TIME,
    )

    date_match = (
        reconstructed.dt.normalize().to_numpy()
        == exported_date.dt.normalize().to_numpy()
    )

    diagnostics = pd.DataFrame({
        "raw_row": np.arange(len(date_series), dtype=int),
        "raw_date": date_series.astype(str).str.strip().to_numpy(),
        "raw_time": clock_series.astype(str).str.strip().to_numpy(),
        "reconstructed_time": reconstructed.to_numpy(),
        "interval_seconds": interval_seconds,
        "date_matches_export": date_match,
    })

    if expected_interval is not None:
        expected_seconds = pd.Timedelta(expected_interval).total_seconds()
        diagnostics["interval_matches_expected"] = (
            diagnostics["interval_seconds"].isna()
            | np.isclose(diagnostics["interval_seconds"], expected_seconds)
        )
    else:
        diagnostics["interval_matches_expected"] = True

    diagnostics["issue"] = ""
    diagnostics.loc[~diagnostics["date_matches_export"], "issue"] = "date_mismatch"
    irregular = ~diagnostics["interval_matches_expected"]
    diagnostics.loc[
        irregular & (diagnostics["issue"] == ""), "issue"
    ] = "irregular_interval"
    both = irregular & (diagnostics["issue"] != "") & (
        diagnostics["issue"] != "irregular_interval"
    )
    diagnostics.loc[both, "issue"] += ";irregular_interval"

    date_mismatch_count = int((~diagnostics["date_matches_export"]).sum())
    if date_mismatch_count:
        sample = diagnostics.loc[~diagnostics["date_matches_export"]].head(10)
        raise ValueError(
            f"Hasil rekonstruksi waktu tidak cocok dengan Date HOBO pada "
            f"{date_mismatch_count} baris. Periksa start_datetime dan urutan data.\n"
            f"Contoh:\n{sample.to_string(index=False)}"
        )

    diagnostics.attrs.update({
        "time_mode": "12h_no_ampm",
        "start_datetime": str(anchor),
        "end_datetime": str(reconstructed.iloc[-1]),
        "n_rows": int(len(reconstructed)),
        "n_unique_timestamps": int(reconstructed.nunique()),
        "n_duplicate_timestamps": int(reconstructed.duplicated().sum()),
        "n_date_mismatches": date_mismatch_count,
        "n_irregular_intervals": int(irregular.iloc[1:].sum()),
        "expected_interval": expected_interval,
        "duration": str(reconstructed.iloc[-1] - reconstructed.iloc[0]),
    })
    return reconstructed, diagnostics


# ---------------------------------------------------------------------------
# HOBO value conversion/correction
# ---------------------------------------------------------------------------

def convert_water_level_unit(
    values: pd.Series,
    from_unit: str,
    to_unit: str,
) -> pd.Series:
    """Convert water-level values between mm, cm, and m."""
    from_unit = str(from_unit).strip().lower()
    to_unit = str(to_unit).strip().lower()
    scale_to_m = {"m": 1.0, "cm": 0.01, "mm": 0.001}
    if from_unit not in scale_to_m or to_unit not in scale_to_m:
        raise ValueError("Unit harus salah satu dari: 'm', 'cm', atau 'mm'.")

    numeric = pd.to_numeric(values, errors="coerce")
    metres = numeric * scale_to_m[from_unit]
    return metres / scale_to_m[to_unit]


def apply_vertical_correction(
    values: pd.Series,
    offset: float = 0.0,
    correction: str = "none",
) -> pd.Series:
    """Apply an offset already expressed in the target water-level unit."""
    correction = str(correction).strip().lower()
    if correction == "subtract":
        return values - float(offset)
    if correction == "add":
        return values + float(offset)
    if correction == "none":
        return values.copy()
    raise ValueError("correction harus 'subtract', 'add', atau 'none'.")


def load_hobo_csv(
    path: str | Path,
    date_col: str = "Date",
    clock_col: str = "Time",
    value_col: str = "Water Level",
    sep: str = ";",
    time_mode: str = "12h_no_ampm",
    start_datetime: str | pd.Timestamp | None = None,
    date_format: str = "%m/%d/%y",
    expected_interval: str | None = "1min",
    input_unit: str = "m",
    target_unit: str = "cm",
    bottom_offset: float = 0.0,
    bottom_offset_unit: str = "cm",
    correction: str = "none",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load HOBO data, repair time, harmonize units, and apply vertical offset."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File HOBO tidak ditemukan: {path}")

    raw = pd.read_csv(path, sep=sep)
    required = [date_col, clock_col, value_col]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(
            f"Kolom HOBO tidak ditemukan: {missing}. Kolom tersedia: {list(raw.columns)}"
        )

    data = raw[[date_col, clock_col, value_col]].copy()
    raw_numeric = pd.to_numeric(data[value_col], errors="coerce")

    if time_mode == "12h_no_ampm":
        reconstructed, diagnostics = reconstruct_hobo_12h_timestamps(
            data[date_col],
            data[clock_col],
            start_datetime=start_datetime,
            date_format=date_format,
            expected_interval=expected_interval,
        )
        data[COL_TIME] = reconstructed
    elif time_mode == "24h":
        data[COL_TIME] = pd.to_datetime(
            data[date_col].astype(str).str.strip()
            + " "
            + data[clock_col].astype(str).str.strip(),
            format=f"{date_format} %H:%M:%S",
            errors="coerce",
        )
        diagnostics = pd.DataFrame({
            "raw_row": np.arange(len(data), dtype=int),
            "raw_date": data[date_col].astype(str).str.strip(),
            "raw_time": data[clock_col].astype(str).str.strip(),
            "reconstructed_time": data[COL_TIME],
        })
        diagnostics.attrs["time_mode"] = "24h"
    else:
        raise ValueError("time_mode harus '12h_no_ampm' atau '24h'.")

    converted = convert_water_level_unit(raw_numeric, input_unit, target_unit)
    offset_target = float(
        convert_water_level_unit(
            pd.Series([bottom_offset]), bottom_offset_unit, target_unit
        ).iloc[0]
    )
    corrected = apply_vertical_correction(converted, offset_target, correction)

    data["hobo_raw_value"] = raw_numeric
    data["hobo_converted_value"] = converted
    data[COL_HOBO] = corrected

    diagnostics["hobo_raw_value"] = raw_numeric.to_numpy()
    diagnostics["hobo_converted_value"] = converted.to_numpy()
    diagnostics["hobo_corrected_value"] = corrected.to_numpy()

    bad_time = int(data[COL_TIME].isna().sum())
    bad_value = int(data[COL_HOBO].isna().sum())
    if bad_time:
        raise ValueError(f"Ada {bad_time} baris HOBO dengan waktu yang gagal diparse.")

    observations = (
        data[[COL_TIME, COL_HOBO, "hobo_raw_value", "hobo_converted_value"]]
        .dropna(subset=[COL_TIME, COL_HOBO])
        .reset_index(drop=True)
    )

    duplicate_count = int(observations[COL_TIME].duplicated().sum())
    if duplicate_count:
        dup = observations.loc[
            observations.duplicated(COL_TIME, keep=False)
        ].head(10)
        raise ValueError(
            f"Masih terdapat {duplicate_count} timestamp aktual duplikat setelah "
            f"rekonstruksi waktu. Contoh:\n{dup.to_string(index=False)}"
        )
    if not observations[COL_TIME].is_monotonic_increasing:
        raise ValueError("Timestamp HOBO hasil rekonstruksi tidak monoton meningkat.")

    diagnostics.attrs.update({
        "bad_time_rows": bad_time,
        "bad_value_rows": bad_value,
        "n_input_rows": int(len(raw)),
        "n_output_rows": int(len(observations)),
        "input_unit": input_unit,
        "target_unit": target_unit,
        "bottom_offset": float(bottom_offset),
        "bottom_offset_unit": bottom_offset_unit,
        "bottom_offset_in_target_unit": offset_target,
        "correction": correction,
    })
    return observations, diagnostics


# ---------------------------------------------------------------------------
# Validation against processed raw+interpolated sensor series
# ---------------------------------------------------------------------------

def _prepare_processed_sensor(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("processed_df harus berupa pandas DataFrame.")
    data = df.copy()
    if "datetime" in data.columns and COL_TIME not in data.columns:
        data = data.rename(columns={"datetime": COL_TIME})
    if "tide_swl" in data.columns and COL_WL not in data.columns:
        data = data.rename(columns={"tide_swl": COL_WL})

    missing = [c for c in (COL_TIME, COL_WL) if c not in data.columns]
    if missing:
        raise ValueError(f"Kolom processed sensor tidak ditemukan: {missing}")

    data[COL_TIME] = _strip_timezone(data[COL_TIME])
    data[COL_WL] = pd.to_numeric(data[COL_WL], errors="coerce")
    keep = [COL_TIME, COL_WL]
    if COL_DATA_SOURCE in data.columns:
        keep.append(COL_DATA_SOURCE)
    data = (
        data[keep]
        .dropna(subset=[COL_TIME, COL_WL])
        .sort_values(COL_TIME)
        .drop_duplicates(COL_TIME, keep="last")
        .reset_index(drop=True)
    )
    return data


def _resample_source_label(values: pd.Series) -> str:
    labels = [str(v) for v in values.dropna().unique()]
    if not labels:
        return "unknown"
    if all(v == "observed" for v in labels):
        return "observed"
    interpolated = [v for v in labels if v.startswith("interpolated")]
    if interpolated:
        return interpolated[0] if len(set(interpolated)) == 1 else "interpolated_mixed"
    return labels[0]


def align_processed_sensor_with_hobo(
    processed_df: pd.DataFrame,
    hobo_df: pd.DataFrame,
    freq: str = "15min",
) -> pd.DataFrame:
    """Aggregate both series to the same grid and return exact matched bins."""
    sensor = _prepare_processed_sensor(processed_df)

    hobo = hobo_df.copy()
    if COL_TIME not in hobo.columns or COL_HOBO not in hobo.columns:
        raise ValueError(
            f"HOBO harus memiliki kolom {COL_TIME!r} dan {COL_HOBO!r}."
        )
    hobo[COL_TIME] = _strip_timezone(hobo[COL_TIME])
    hobo[COL_HOBO] = pd.to_numeric(hobo[COL_HOBO], errors="coerce")
    hobo = hobo.dropna(subset=[COL_TIME, COL_HOBO]).sort_values(COL_TIME)

    sensor = sensor.set_index(COL_TIME)
    sensor_value = sensor[COL_WL].resample(freq).mean().rename(COL_SENSOR)
    if COL_DATA_SOURCE in sensor.columns:
        source = sensor[COL_DATA_SOURCE].resample(freq).apply(_resample_source_label)
        sensor_grid = pd.concat([sensor_value, source.rename(COL_DATA_SOURCE)], axis=1)
    else:
        sensor_grid = sensor_value.to_frame()

    hobo_grid = (
        hobo.set_index(COL_TIME)[COL_HOBO]
        .resample(freq)
        .mean()
        .rename(COL_HOBO)
        .to_frame()
    )

    merged = (
        sensor_grid.join(hobo_grid, how="inner")
        .dropna(subset=[COL_SENSOR, COL_HOBO])
        .reset_index()
    )
    return merged


def compute_residual(merged_df: pd.DataFrame) -> pd.DataFrame:
    out = merged_df.copy()
    # Reference/observed = HOBO; estimate being evaluated = processed sensor.
    out[COL_RESIDUAL] = out[COL_HOBO] - out[COL_SENSOR]
    return out


def compute_rmse(residual: pd.Series) -> float:
    return float(np.sqrt(np.mean(np.square(residual))))


def compute_mae(residual: pd.Series) -> float:
    return float(np.mean(np.abs(residual)))


def compute_bias(residual: pd.Series) -> float:
    return float(np.mean(residual))


def compute_correlation(merged_df: pd.DataFrame) -> float:
    if len(merged_df) < 2:
        return float("nan")
    return float(merged_df[COL_HOBO].corr(merged_df[COL_SENSOR]))


def compute_r_squared(merged_df: pd.DataFrame) -> float:
    obs = merged_df[COL_HOBO].to_numpy(dtype=float)
    pred = merged_df[COL_SENSOR].to_numpy(dtype=float)
    ss_res = np.sum(np.square(obs - pred))
    ss_tot = np.sum(np.square(obs - obs.mean()))
    if ss_tot == 0:
        return float("nan")
    return float(1.0 - ss_res / ss_tot)


def compute_nse(merged_df: pd.DataFrame) -> float:
    obs = merged_df[COL_HOBO].to_numpy(dtype=float)
    pred = merged_df[COL_SENSOR].to_numpy(dtype=float)
    denominator = np.sum(np.square(obs - obs.mean()))
    if denominator == 0:
        return float("nan")
    return float(1.0 - np.sum(np.square(obs - pred)) / denominator)


def run_external_hobo_validation(
    processed_df: pd.DataFrame,
    hobo_df: pd.DataFrame,
    freq: str = "15min",
    unit: str = "cm",
    metadata: Optional[dict] = None,
) -> ValidationResult:
    """Validate processed raw+interpolated sensor data against external HOBO."""
    merged = align_processed_sensor_with_hobo(processed_df, hobo_df, freq=freq)
    merged = compute_residual(merged)
    if merged.empty:
        raise ValueError(
            "Tidak ada timestamp overlap antara data sensor terproses dan HOBO. "
            "Validasi dilewati."
        )

    residual = merged[COL_RESIDUAL]
    metrics = {
        "validation_type": "external_hobo_vs_raw_interpolated",
        "comparison_grid": freq,
        "unit": unit,
        "n_matched": int(len(merged)),
        "start": merged[COL_TIME].min(),
        "end": merged[COL_TIME].max(),
        "rmse": compute_rmse(residual),
        "mae": compute_mae(residual),
        "bias": compute_bias(residual),
        "correlation": compute_correlation(merged),
        "r_squared": compute_r_squared(merged),
        "nse": compute_nse(merged),
        "residual_max": float(residual.max()),
        "residual_min": float(residual.min()),
        "residual_std": float(residual.std()),
        "hobo_mean": float(merged[COL_HOBO].mean()),
        "sensor_processed_mean": float(merged[COL_SENSOR].mean()),
    }
    if COL_DATA_SOURCE in merged.columns:
        metrics["n_sensor_observed"] = int((merged[COL_DATA_SOURCE] == "observed").sum())
        metrics["n_sensor_interpolated"] = int(
            merged[COL_DATA_SOURCE].astype(str).str.startswith("interpolated").sum()
        )
    if metadata:
        for key, value in metadata.items():
            metrics.setdefault(key, value)

    return ValidationResult(metrics=metrics, merged=merged)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_validation_report(result: ValidationResult) -> None:
    print("\n=== EXTERNAL HOBO VALIDATION REPORT ===")
    print("Target: processed sensor (raw observation + interpolation), not UTide reconstruction")
    for key, value in result.metrics.items():
        if isinstance(value, (float, np.floating)):
            print(f"{key:>26}: {value:.6f}")
        elif isinstance(value, pd.Timestamp):
            print(f"{key:>26}: {value}")
        else:
            print(f"{key:>26}: {value}")


def save_validation_report(
    result: ValidationResult,
    output_dir: str = "output/validation_hobo",
    prefix: str = "external_hobo_validation",
    timing_diagnostics: Optional[pd.DataFrame] = None,
) -> tuple[str, str, Optional[str]]:
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    metrics = result.metrics.copy()
    for key, value in list(metrics.items()):
        if isinstance(value, pd.Timestamp):
            metrics[key] = value.isoformat()

    metrics_path = outdir / f"{prefix}_metrics.csv"
    detail_path = outdir / f"{prefix}_detail.csv"
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)
    result.merged.to_csv(detail_path, index=False)

    diagnostics_path = None
    if timing_diagnostics is not None and not timing_diagnostics.empty:
        diagnostics_path_obj = outdir / f"{prefix}_time_diagnostics.csv"
        timing_diagnostics.to_csv(diagnostics_path_obj, index=False)
        diagnostics_path = str(diagnostics_path_obj)

    return str(metrics_path), str(detail_path), diagnostics_path


def get_hobo_timing_summary(diagnostics: pd.DataFrame) -> dict:
    attrs = dict(getattr(diagnostics, "attrs", {}))
    if diagnostics is None or diagnostics.empty:
        return attrs

    reconstructed = pd.to_datetime(diagnostics["reconstructed_time"], errors="coerce")
    attrs.setdefault("n_rows", int(len(diagnostics)))
    attrs.setdefault("n_unique_timestamps", int(reconstructed.nunique()))
    attrs.setdefault("n_duplicate_timestamps", int(reconstructed.duplicated().sum()))
    attrs.setdefault("start_datetime", str(reconstructed.min()))
    attrs.setdefault("end_datetime", str(reconstructed.max()))
    if "date_matches_export" in diagnostics:
        attrs.setdefault(
            "n_date_mismatches",
            int((~diagnostics["date_matches_export"]).sum()),
        )
    if "interval_matches_expected" in diagnostics:
        attrs.setdefault(
            "n_irregular_intervals",
            int((~diagnostics["interval_matches_expected"]).iloc[1:].sum()),
        )
    return attrs


if __name__ == "__main__":
    print("ini_validasi.py adalah modul sidecar; jalankan melalui run_pipeline.py.")
