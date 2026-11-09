"""
preprocessing.py
==================
Stage 2 of the tidal pipeline: turn the raw ThingSpeak feed rows from
apiloader.py into a clean, gap-free, regularly-sampled time series.

Pipeline steps (chained together in `run()`):
    1. load                - parse raw API rows into a typed, sorted frame
    2. quality_control      - drop duplicates/out-of-range values, flag spikes
    3. convert_time         - localize timestamps, snap onto a regular grid
    4. interpolate_missing  - fill the remaining gaps

The interpolation method (`method="harmonic"`) generalizes the approach
from the original exploratory notebook: solve tidal harmonic
constituents with UTide from whatever observed data exists, reconstruct
the pure astronomical tide across the full timeline, and add synthetic
"red" noise scaled to the real observed residual so the filled sections
sit at a realistic variance instead of looking artificially smooth. That
one-off, Colab/FakFak-specific script becomes a reusable function here
that works for any station/date range, with a plain linear-interpolation
fallback for when there isn't enough data to solve for constituents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import utide
    _HAS_UTIDE = True
except ImportError:  # pragma: no cover - exercised only when utide isn't installed
    _HAS_UTIDE = False

# Minimum number of observed points before a harmonic solve is attempted.
# UTide needs enough spread across time to separate tidal constituents;
# below this it's more likely to overfit noise than find real tides.
MIN_HARMONIC_POINTS = 200


@dataclass
class QCResult:
    """Small report of what quality control removed, for logging/audit."""
    n_input: int
    n_duplicates_dropped: int
    n_out_of_range: int
    n_spikes_flagged: int
    n_output: int


@dataclass
class InterpolationReport:
    """Small report of what interpolate_missing did, for logging/audit."""
    method_used: str
    n_observed: int
    n_filled: int
    n_total: int


# ---------------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------------

def load(raw: pd.DataFrame, value_col: str = "tide_swl") -> pd.DataFrame:
    """
    Turn raw ThingSpeak rows (as returned by apiloader) into a typed
    frame with a parsed UTC timestamp column and numeric value column.

    Parameters
    ----------
    raw : pd.DataFrame
        Output of ThingSpeakAPILoader.fetch()/fetch_range() -- expects
        a "created_at" column (ISO-8601 UTC string) and `value_col`.
    value_col : str
        Name of the measurement column to keep (matches config.FIELD_MAP
        values, e.g. "tide_swl").

    Returns
    -------
    pd.DataFrame
        Columns: ["created_at" (tz-aware UTC datetime), value_col (float)].
        Rows with an unparsable timestamp are dropped.
    """
    if raw.empty:
        return pd.DataFrame(columns=["created_at", value_col])

    df = raw[["created_at", value_col]].copy()
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    n_bad_time = int(df["created_at"].isna().sum())
    if n_bad_time:
        logger.warning("Dropping %d row(s) with unparsable timestamps.", n_bad_time)
    df = df.dropna(subset=["created_at"]).sort_values("created_at").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 2. Quality control
# ---------------------------------------------------------------------------

def quality_control(
    df: pd.DataFrame,
    value_col: str = "tide_swl",
    valid_range: Optional[tuple[float, float]] = None,
    spike_window: int = 7,
    spike_threshold: float = 5.0,
) -> tuple[pd.DataFrame, QCResult]:
    """
    Clean a loaded frame: drop duplicate timestamps, drop physically
    impossible readings, and flag (null out) spikes so they get filled
    by interpolation rather than treated as real observations.

    Parameters
    ----------
    df : pd.DataFrame
        Output of `load()`.
    valid_range : (min, max), optional
        Sensor-plausible bounds for `value_col`. Values outside this
        range are dropped outright. Left unset by default since the
        sensor's units/calibration aren't specified here -- pass this
        in once you know the expected range for your deployment.
    spike_window : int
        Window size (in samples) for the rolling median used to detect
        spikes.
    spike_threshold : float
        Number of median-absolute-deviations (MAD) a point must differ
        from its local rolling median to be flagged as a spike.

    Returns
    -------
    (pd.DataFrame, QCResult)
        Cleaned frame (spikes set to NaN, not dropped, so they remain as
        gaps for `interpolate_missing` to fill) and a small report of
        what was removed/flagged.
    """
    n_input = len(df)
    out = df.copy()

    n_dupes = int(out.duplicated(subset="created_at").sum())
    out = out.drop_duplicates(subset="created_at", keep="last")

    n_out_of_range = 0
    if valid_range is not None:
        lo, hi = valid_range
        mask = out[value_col].between(lo, hi) | out[value_col].isna()
        n_out_of_range = int((~mask).sum())
        out = out[mask]

    n_spikes = 0
    if len(out) >= spike_window:
        rolling_median = out[value_col].rolling(spike_window, center=True, min_periods=1).median()
        deviation = (out[value_col] - rolling_median).abs()
        mad = deviation.rolling(spike_window, center=True, min_periods=1).median().replace(0, np.nan)
        robust_z = deviation / (1.4826 * mad)  # 1.4826 makes MAD ~comparable to a std-dev
        spike_mask = (robust_z > spike_threshold).fillna(False)
        n_spikes = int(spike_mask.sum())
        out.loc[spike_mask, value_col] = np.nan

    result = QCResult(
        n_input=n_input,
        n_duplicates_dropped=n_dupes,
        n_out_of_range=n_out_of_range,
        n_spikes_flagged=n_spikes,
        n_output=len(out),
    )
    logger.info(
        "QC: %d in -> %d dupes dropped, %d out-of-range dropped, %d spikes flagged -> %d rows",
        result.n_input, result.n_duplicates_dropped, result.n_out_of_range,
        result.n_spikes_flagged, result.n_output,
    )
    return out.reset_index(drop=True), result


# ---------------------------------------------------------------------------
# 3. Time conversion
# ---------------------------------------------------------------------------

def infer_frequency(df: pd.DataFrame, fallback: str = "15min") -> str:
    """Guess the sensor's logging interval from the most common gap between samples."""
    if len(df) < 3:
        return fallback
    diffs = df["created_at"].diff().dropna()
    if diffs.empty:
        return fallback
    mode = diffs.mode()
    if mode.empty:
        return fallback
    seconds = int(mode.iloc[0].total_seconds())
    return f"{max(seconds, 1)}s"


def convert_time(
    df: pd.DataFrame,
    value_col: str = "tide_swl",
    local_tz: str = "Asia/Jakarta",
    freq: Optional[str] = None,
) -> pd.DataFrame:
    """
    Localize timestamps and snap the series onto a regular time grid.

    Parameters
    ----------
    df : pd.DataFrame
        Output of `quality_control()` -- expects a tz-aware "created_at"
        UTC column.
    local_tz : str
        Target IANA timezone for the output index (station-local time is
        what tidal predictions/website output should be reported in).
    freq : str, optional
        Explicit pandas frequency for the regular grid (e.g. "15min").
        If omitted, it's inferred from the data via `infer_frequency`.

    Returns
    -------
    pd.DataFrame
        Indexed by a regular, timezone-aware DatetimeIndex named
        "datetime" (in `local_tz`), with `value_col` resampled onto it.
        Bins with no reading become NaN gaps -- that's what
        `interpolate_missing` expects.
    """
    if df.empty:
        idx = pd.DatetimeIndex([], name="datetime", tz=local_tz)
        return pd.DataFrame({value_col: []}, index=idx)

    freq = freq or infer_frequency(df)

    local = df.copy()
    local["datetime"] = local["created_at"].dt.tz_convert(local_tz)
    local = local.set_index("datetime")[[value_col]]
    local = local[~local.index.duplicated(keep="last")]

    # Resample onto a uniform grid: a bin with one reading keeps it, a
    # bin with several averages them, a bin with none becomes NaN.
    regular = local.resample(freq).mean()
    regular.index.name = "datetime"
    return regular


# ---------------------------------------------------------------------------
# 4. Interpolation
# ---------------------------------------------------------------------------

def _linear_fill(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Time-weighted linear interpolation; returns (filled series, source labels)."""
    source = pd.Series(
        np.where(series.notna(), "observed", "interpolated_linear"), index=series.index
    )
    filled = series.interpolate(method="time", limit_direction="both")
    return filled, source


def _harmonic_fill(
    series: pd.Series,
    latitude: float,
    add_synthetic_noise: bool = True,
    random_state: Optional[int] = None,
) -> tuple[pd.Series, pd.Series]:
    """
    Reproduce the notebook's approach: solve harmonic constituents from
    observed points, reconstruct the pure astronomical tide across the
    whole index, and (optionally) add synthetic "red" noise matched to
    the real residual variance so filled stretches look like plausible
    ocean data rather than an unnaturally smooth curve.
    """
    if not _HAS_UTIDE:
        raise RuntimeError("utide is not installed; `pip install utide` or use method='linear'.")

    observed = series.dropna()
    epoch = pd.Timestamp("1970-01-01", tz=series.index.tz)
    obs_time_days = (observed.index - epoch).total_seconds() / 86400.0

    coef = utide.solve(obs_time_days.values, observed.values, lat=latitude, verbose=False)

    all_time_days = (series.index - epoch).total_seconds() / 86400.0
    recon = utide.reconstruct(all_time_days.values, coef, verbose=False)
    predicted = pd.Series(recon.h, index=series.index)

    predicted_with_noise = predicted
    if add_synthetic_noise:
        residual = observed - predicted.loc[observed.index]
        noise_std = residual.std()
        if noise_std and not np.isnan(noise_std):
            rng = np.random.default_rng(random_state)
            white_noise = rng.normal(0, noise_std, size=len(series))
            # Smooth white noise into "red" noise: weather-driven surges
            # develop over hours, not instantaneously between samples.
            red_noise = pd.Series(white_noise, index=series.index).rolling(
                window=12, min_periods=1, center=True
            ).mean()
            current_std = red_noise.std()
            if current_std:
                red_noise = red_noise * (noise_std / current_std)
            predicted_with_noise = predicted + red_noise

    source = pd.Series(
        np.where(series.notna(), "observed", "interpolated_harmonic"), index=series.index
    )
    filled = series.fillna(predicted_with_noise)
    return filled, source


def interpolate_missing(
    df: pd.DataFrame,
    value_col: str = "tide_swl",
    method: str = "auto",
    latitude: Optional[float] = None,
    add_synthetic_noise: bool = True,
    min_harmonic_points: int = MIN_HARMONIC_POINTS,
) -> tuple[pd.DataFrame, InterpolationReport]:
    """
    Fill gaps left after `convert_time()`.

    Parameters
    ----------
    method : {"auto", "harmonic", "linear"}
        "harmonic" - UTide constituent solve + reconstruction (+ optional
            synthetic noise), following the original notebook's approach.
            Requires `latitude` and enough observed points.
        "linear"   - plain time-weighted linear interpolation. Always
            available, but flattens long gaps toward a straight line.
        "auto" (default) - use "harmonic" when utide is installed,
            `latitude` is given, and there are at least
            `min_harmonic_points` observed samples; otherwise fall back
            to "linear" (and log why).
    latitude : float, optional
        Station latitude in decimal degrees, required for "harmonic".
    add_synthetic_noise : bool
        For "harmonic" only -- overlay red noise matched to the real
        residual std, so filled sections aren't unnaturally smooth.

    Returns
    -------
    (pd.DataFrame, InterpolationReport)
        Frame with `value_col` gap-filled and a new "data_source" column
        ("observed" / "interpolated_linear" / "interpolated_harmonic"),
        plus a small report of which method ran and how many points
        were filled.
    """
    if df.empty:
        return df.assign(data_source=pd.Series(dtype="object")), InterpolationReport("none", 0, 0, 0)

    series = df[value_col]
    n_observed = int(series.notna().sum())
    n_total = len(series)

    chosen = method
    if method == "auto":
        if _HAS_UTIDE and latitude is not None and n_observed >= min_harmonic_points:
            chosen = "harmonic"
        else:
            chosen = "linear"
            logger.info(
                "Falling back to linear interpolation "
                "(utide_installed=%s, latitude_set=%s, n_observed=%d < min_harmonic_points=%d).",
                _HAS_UTIDE, latitude is not None, n_observed, min_harmonic_points,
            )

    if chosen == "harmonic":
        if latitude is None:
            raise ValueError("method='harmonic' requires a station latitude.")
        filled, source = _harmonic_fill(series, latitude=latitude, add_synthetic_noise=add_synthetic_noise)
    elif chosen == "linear":
        filled, source = _linear_fill(series)
    else:
        raise ValueError(f"Unknown method: {method!r} (expected 'auto', 'harmonic', or 'linear').")

    out = df.copy()
    out[value_col] = filled
    out["data_source"] = source

    n_filled = int((source != "observed").sum())
    report = InterpolationReport(method_used=chosen, n_observed=n_observed, n_filled=n_filled, n_total=n_total)
    logger.info("Interpolation (%s): %d observed, %d filled, %d total.", chosen, n_observed, n_filled, n_total)
    return out, report


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(
    raw: pd.DataFrame,
    value_col: str = "tide_swl",
    valid_range: Optional[tuple[float, float]] = None,
    local_tz: str = "Asia/Jakarta",
    freq: Optional[str] = None,
    interpolation_method: str = "auto",
    latitude: Optional[float] = None,
) -> pd.DataFrame:
    """
    Run the full preprocessing stage: load -> quality_control ->
    convert_time -> interpolate_missing.

    This is the single entry point `run_pipeline.py` (or anything else
    that wants clean data) should call; the individual steps above stay
    available separately for unit testing or reuse in a different order.
    """
    loaded = load(raw, value_col=value_col)
    cleaned, qc_report = quality_control(loaded, value_col=value_col, valid_range=valid_range)
    regular = convert_time(cleaned, value_col=value_col, local_tz=local_tz, freq=freq)
    final, interp_report = interpolate_missing(
        regular, value_col=value_col, method=interpolation_method, latitude=latitude,
    )
    logger.info(
        "Preprocessing complete: %d raw rows -> %d clean rows (%d observed, %d filled via %s).",
        qc_report.n_input, interp_report.n_total, interp_report.n_observed,
        interp_report.n_filled, interp_report.method_used,
    )
    return final


if __name__ == "__main__":
    import apiloader

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raw_df = apiloader.load_latest(results=2000)
    clean_df = run(raw_df)
    print(clean_df.head())
    print(clean_df.tail())
