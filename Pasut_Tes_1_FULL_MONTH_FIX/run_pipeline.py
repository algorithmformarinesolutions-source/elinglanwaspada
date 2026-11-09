"""Master script for the tidal pipeline.

Core operational pipeline
-------------------------
1. Historical ThingSpeak acquisition
2. QC + regularization + interpolation
3. UTide harmonic analysis + Formzahl
4. Forecast for the dynamic operational period
5. Threshold classification
6. Visualization (combined observed + interpolated series + forecast + threshold)
7. Forecast calendar

External HOBO validation is a SIDE-CAR process. It independently loads the
ThingSpeak data that overlaps the HOBO deployment, preprocesses that data, and
compares HOBO with the processed raw+interpolated sensor series. Validation
never feeds values back into the operational graph, harmonic coefficients,
forecast, threshold, or calendar. Validation failure therefore does not stop
the core pipeline.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

import apiloader
import calender
import cobatidal_analysis
import config
import fforecast
import ggrafik
import ini_validasi
import preprocessing
import testthreshold

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse optional CLI overrides; direct VS Code Run needs no arguments."""
    p = argparse.ArgumentParser(
        description="Pipeline pasut. Tanpa argumen, semua default berasal dari config.py."
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--latest", type=int, default=None, metavar="N")
    mode.add_argument("--start", type=str, default=None)
    p.add_argument("--end", type=str, default=None)

    p.add_argument("--freq", default=config.DEFAULT_SAMPLE_FREQ)
    p.add_argument(
        "--method",
        choices=["auto", "harmonic", "linear"],
        default=config.DEFAULT_INTERPOLATION_METHOD,
    )
    p.add_argument("--valid-min", type=float, default=config.DEFAULT_VALID_MIN)
    p.add_argument("--valid-max", type=float, default=config.DEFAULT_VALID_MAX)

    # If omitted, direct-run uses config.PERIOD_DATE_START -> PERIOD_DATE_END.
    p.add_argument(
        "--forecast-days",
        type=int,
        default=None,
        help="Override operational period with N days after the last observation.",
    )
    p.add_argument("--forecast-interval", default=config.DEFAULT_FORECAST_INTERVAL)
    p.add_argument("--forecast-start", default=None)
    p.add_argument("--forecast-end", default=None)

    p.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    p.add_argument("--outdir", default=config.OUTPUT_FOLDER)

    # External validation sidecar.
    p.add_argument("--no-validation", action="store_true", default=not config.ENABLE_HOBO_VALIDATION)
    p.add_argument("--validation-csv", default=config.DEFAULT_VALIDATION_CSV)
    p.add_argument("--validation-date-col", default=config.DEFAULT_VALIDATION_DATE_COL)
    p.add_argument("--validation-clock-col", default=config.DEFAULT_VALIDATION_CLOCK_COL)
    p.add_argument("--validation-value-col", default=config.DEFAULT_VALIDATION_VALUE_COL)
    p.add_argument("--validation-sep", default=config.DEFAULT_VALIDATION_SEP)
    p.add_argument(
        "--validation-time-mode",
        choices=["12h_no_ampm", "24h"],
        default=config.DEFAULT_VALIDATION_TIME_MODE,
    )
    p.add_argument(
        "--validation-start-datetime",
        default=config.DEFAULT_VALIDATION_START_DATETIME,
    )
    p.add_argument("--validation-date-format", default=config.DEFAULT_VALIDATION_DATE_FORMAT)
    p.add_argument(
        "--validation-expected-interval",
        default=config.DEFAULT_VALIDATION_EXPECTED_INTERVAL,
    )
    p.add_argument("--validation-input-unit", default=config.DEFAULT_VALIDATION_INPUT_UNIT)
    p.add_argument("--validation-target-unit", default=config.DEFAULT_VALIDATION_TARGET_UNIT)
    p.add_argument(
        "--validation-bottom-offset",
        type=float,
        default=config.DEFAULT_VALIDATION_BOTTOM_OFFSET,
    )
    p.add_argument(
        "--validation-bottom-offset-unit",
        default=config.DEFAULT_VALIDATION_BOTTOM_OFFSET_UNIT,
    )
    p.add_argument(
        "--validation-correction",
        choices=["subtract", "add", "none"],
        default=config.DEFAULT_VALIDATION_CORRECTION,
    )
    p.add_argument(
        "--validation-align-freq",
        default=config.DEFAULT_VALIDATION_ALIGN_FREQ,
    )

    p.add_argument(
        "--no-plot",
        action="store_true",
        default=not config.SHOW_PLOT,
    )
    return p.parse_args(argv)


def _project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent / path


def _resolve_data_window(args: argparse.Namespace) -> tuple[str | None, str | None, int | None]:
    """Resolve the HISTORICAL observation window used for fitting."""
    if args.latest is not None:
        if args.latest <= 0:
            raise SystemExit("--latest harus > 0.")
        return None, None, args.latest

    if args.start is not None or args.end is not None:
        if not args.start or not args.end:
            raise SystemExit("--start dan --end harus diberikan bersama.")
        return args.start, args.end, None

    mode = str(config.DEFAULT_DATA_MODE).strip().lower()
    if mode == "period":
        return config.DEFAULT_START, config.DEFAULT_END, None
    if mode == "latest":
        if config.DEFAULT_LATEST_RESULTS <= 0:
            raise SystemExit("DEFAULT_LATEST_RESULTS harus > 0.")
        return None, None, config.DEFAULT_LATEST_RESULTS
    raise SystemExit("DEFAULT_DATA_MODE harus 'period' atau 'latest'.")


def _resolve_forecast_window(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Return explicit forecast period, or (None, None) for legacy N-day mode."""
    if args.forecast_days is not None:
        if args.forecast_days <= 0:
            raise SystemExit("--forecast-days harus > 0.")
        if args.forecast_start or args.forecast_end:
            raise SystemExit(
                "Pilih salah satu: --forecast-days ATAU --forecast-start/--forecast-end."
            )
        return None, None

    if args.forecast_start is not None or args.forecast_end is not None:
        if not args.forecast_start or not args.forecast_end:
            raise SystemExit("--forecast-start dan --forecast-end harus diberikan bersama.")
        return args.forecast_start, args.forecast_end

    return config.PERIOD_DATE_START, config.PERIOD_DATE_END


def _prepare_clean_for_tidal_analysis(clean: pd.DataFrame) -> pd.DataFrame:
    if clean.empty:
        raise ValueError("Hasil preprocessing kosong.")
    data = clean.reset_index().copy()
    if "datetime" not in data.columns:
        raise ValueError("Index preprocessing harus bernama 'datetime'.")
    data = data.rename(columns={"datetime": config.COL_TIME, "tide_swl": config.COL_WL})
    required = [config.COL_TIME, config.COL_WL]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Kolom hasil preprocessing tidak lengkap: {missing}")
    keep = required + ([config.COL_DATA_SOURCE] if config.COL_DATA_SOURCE in data.columns else [])
    return data[keep]


def _save_basic_stats(stats: dict, path: Path) -> None:
    out = stats.copy()
    for key, value in out.items():
        if isinstance(value, pd.Timestamp):
            out[key] = value.isoformat()
    pd.DataFrame([out]).to_csv(path, index=False)


def _log_effective_configuration(
    args: argparse.Namespace,
    data_start: str | None,
    data_end: str | None,
    latest: int | None,
    forecast_start: str | None,
    forecast_end: str | None,
    validation_csv: Path | None,
    outdir: Path,
) -> None:
    logger.info("=" * 76)
    logger.info("KONFIGURASI RUN AKTIF")
    logger.info("Run local       : %s", config.PIPELINE_RUN_AT)
    logger.info(
        "Periode operasi : %s s.d. %s (1 bulan kalender)",
        config.PERIOD_DATE_START,
        config.PERIOD_DATE_END,
    )
    if data_start and data_end:
        logger.info("Data historis   : %s s.d. %s", data_start, data_end)
    else:
        logger.info("Data historis   : latest %s data", latest)
    logger.info("Preprocessing   : freq=%s | method=%s", args.freq, args.method)
    if forecast_start and forecast_end:
        logger.info("Forecast        : %s s.d. %s | interval=%s", forecast_start, forecast_end, args.forecast_interval)
    else:
        logger.info("Forecast        : %s hari | interval=%s", args.forecast_days, args.forecast_interval)
    logger.info("Threshold       : %.3f %s", args.threshold, config.WATER_LEVEL_UNIT)
    logger.info("HOBO validation : %s", "OFF" if args.no_validation else validation_csv)
    if not args.no_validation:
        logger.info(
            "HOBO values     : %s -> %s | correction=%s %.3f %s",
            args.validation_input_unit,
            args.validation_target_unit,
            args.validation_correction,
            args.validation_bottom_offset,
            args.validation_bottom_offset_unit,
        )
        logger.info("Validation grid : %s", args.validation_align_freq)
    logger.info("Output          : %s", outdir)
    logger.info("Tampilkan plot  : %s", not args.no_plot)
    logger.info("=" * 76)


def _run_external_validation_sidecar(
    args: argparse.Namespace,
    validation_csv_path: Path,
    outdir: Path,
) -> None:
    """Independent HOBO validation; errors here never modify the core pipeline."""
    logger.info("[SIDE-CAR] Menjalankan validasi eksternal HOBO...")
    validation_dir = outdir / "validation_hobo"
    validation_dir.mkdir(parents=True, exist_ok=True)

    hobo_df, timing_diagnostics = ini_validasi.load_hobo_csv(
        path=validation_csv_path,
        date_col=args.validation_date_col,
        clock_col=args.validation_clock_col,
        value_col=args.validation_value_col,
        sep=args.validation_sep,
        time_mode=args.validation_time_mode,
        start_datetime=args.validation_start_datetime,
        date_format=args.validation_date_format,
        expected_interval=args.validation_expected_interval,
        input_unit=args.validation_input_unit,
        target_unit=args.validation_target_unit,
        bottom_offset=args.validation_bottom_offset,
        bottom_offset_unit=args.validation_bottom_offset_unit,
        correction=args.validation_correction,
    )

    timing_summary = ini_validasi.get_hobo_timing_summary(timing_diagnostics)
    logger.info(
        "HOBO corrected   : %d data | %s s.d. %s",
        len(hobo_df),
        hobo_df[ini_validasi.COL_TIME].min(),
        hobo_df[ini_validasi.COL_TIME].max(),
    )

    # Validation gets its OWN ThingSpeak acquisition window based on HOBO time.
    # This keeps old HOBO deployments usable even when the operational pipeline
    # runs on today's data.
    hobo_start = pd.Timestamp(hobo_df[ini_validasi.COL_TIME].min())
    hobo_end = pd.Timestamp(hobo_df[ini_validasi.COL_TIME].max())
    # Expand to full comparison bins so edge bins are not artificially truncated.
    val_start_ts = hobo_start.floor(args.validation_align_freq)
    val_end_ts = hobo_end.ceil(args.validation_align_freq)
    val_start = val_start_ts.strftime("%Y-%m-%d %H:%M:%S")
    val_end = val_end_ts.strftime("%Y-%m-%d %H:%M:%S")

    validation_raw = apiloader.load_period(start=val_start, end=val_end)
    validation_raw.to_csv(validation_dir / "01_validation_raw_thingspeak.csv", index=False)
    if validation_raw.empty:
        raise ValueError(
            f"ThingSpeak tidak memiliki data pada periode HOBO {val_start} s.d. {val_end}."
        )

    valid_range = None
    if args.valid_min is not None or args.valid_max is not None:
        if args.valid_min is None or args.valid_max is None:
            raise ValueError("valid-min dan valid-max harus berpasangan.")
        valid_range = (args.valid_min, args.valid_max)

    validation_clean = preprocessing.run(
        validation_raw,
        value_col=next(iter(config.FIELD_MAP.values())),
        valid_range=valid_range,
        local_tz=config.LOCAL_TIMEZONE,
        freq=args.freq,
        interpolation_method=args.method,
        latitude=config.STATION_LATITUDE,
    )
    validation_clean.to_csv(validation_dir / "02_validation_processed_sensor.csv")
    validation_processed = _prepare_clean_for_tidal_analysis(validation_clean)

    metadata = {
        "hobo_input_unit": args.validation_input_unit,
        "target_unit": args.validation_target_unit,
        "hobo_bottom_offset": args.validation_bottom_offset,
        "hobo_bottom_offset_unit": args.validation_bottom_offset_unit,
        "hobo_correction": args.validation_correction,
        "hobo_time_mode": timing_summary.get("time_mode", args.validation_time_mode),
    }
    result = ini_validasi.run_external_hobo_validation(
        processed_df=validation_processed,
        hobo_df=hobo_df,
        freq=args.validation_align_freq,
        unit=args.validation_target_unit,
        metadata=metadata,
    )
    ini_validasi.print_validation_report(result)
    metrics_path, detail_path, diagnostic_path = ini_validasi.save_validation_report(
        result,
        output_dir=str(validation_dir),
        prefix="external_hobo_validation",
        timing_diagnostics=timing_diagnostics,
    )
    logger.info("Validation metrics     -> %s", metrics_path)
    logger.info("Validation detail      -> %s", detail_path)
    if diagnostic_path:
        logger.info("HOBO time diagnostics  -> %s", diagnostic_path)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)

    data_start, data_end, latest = _resolve_data_window(args)
    forecast_start, forecast_end = _resolve_forecast_window(args)
    outdir = _project_path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Final visualization no longer uses historical UTide reconstruction.
    # Remove a stale reconstruction CSV from older runs so it cannot be
    # mistaken for a current output.
    stale_reconstruction = outdir / "03_tidal_reconstruction.csv"
    if stale_reconstruction.exists():
        stale_reconstruction.unlink()

    validation_csv_path = _project_path(args.validation_csv) if args.validation_csv else None
    if not args.no_validation and validation_csv_path and not validation_csv_path.exists():
        logger.warning(
            "File HOBO tidak ditemukan (%s). Core pipeline tetap dilanjutkan tanpa validasi.",
            validation_csv_path,
        )
        validation_csv_path = None

    _log_effective_configuration(
        args,
        data_start,
        data_end,
        latest,
        forecast_start,
        forecast_end,
        validation_csv_path,
        outdir,
    )

    # ============================================================
    # 1. HISTORICAL DATA ACQUISITION
    # ============================================================
    logger.info("[1/7] Mengambil data historis dari ThingSpeak...")
    if data_start and data_end:
        raw = apiloader.load_period(start=data_start, end=data_end)
    else:
        raw = apiloader.load_latest(results=latest or config.DEFAULT_LATEST_RESULTS)

    raw_path = outdir / "01_raw_ultrasonic_tide.csv"
    raw.to_csv(raw_path, index=False)
    logger.info("Data mentah: %d baris -> %s", len(raw), raw_path)
    if raw.empty:
        logger.warning("Tidak ada data historis. Core pipeline dihentikan.")
        return

    # ============================================================
    # 2. PREPROCESSING: OBSERVED + INTERPOLATED
    # ============================================================
    logger.info("[2/7] Quality control + grid waktu + interpolasi...")
    valid_range = None
    if args.valid_min is not None or args.valid_max is not None:
        if args.valid_min is None or args.valid_max is None:
            raise SystemExit("--valid-min dan --valid-max harus diberikan bersama.")
        valid_range = (args.valid_min, args.valid_max)

    clean = preprocessing.run(
        raw,
        value_col=next(iter(config.FIELD_MAP.values())),
        valid_range=valid_range,
        local_tz=config.LOCAL_TIMEZONE,
        freq=args.freq,
        interpolation_method=args.method,
        latitude=config.STATION_LATITUDE,
    )
    clean.to_csv(outdir / "02_processed_ultrasonic_tide.csv")
    analysis_df = _prepare_clean_for_tidal_analysis(clean)
    analysis_df.to_csv(outdir / "02_processed_with_source.csv", index=False)

    if config.COL_DATA_SOURCE in analysis_df.columns:
        n_observed = int((analysis_df[config.COL_DATA_SOURCE] == "observed").sum())
        n_interpolated = int(
            analysis_df[config.COL_DATA_SOURCE].astype(str).str.startswith("interpolated").sum()
        )
        logger.info(
            "Processed series: %d total | %d observed | %d interpolated",
            len(analysis_df), n_observed, n_interpolated,
        )

    # ============================================================
    # 3. TIDAL HARMONIC ANALYSIS
    # ============================================================
    logger.info("[3/7] UTide harmonic analysis + Formzahl...")
    stats = cobatidal_analysis.compute_basic_statistics(analysis_df)
    _save_basic_stats(stats, outdir / "03_basic_tidal_statistics.csv")

    tidal_result = cobatidal_analysis.run_full_analysis(
        analysis_df,
        latitude=config.STATION_LATITUDE,
        reconstruct_on="none",
    )
    pd.DataFrame({
        "formzahl": [tidal_result["formzahl"]],
        "classification": [tidal_result["classification"]],
    }).to_csv(outdir / "03_formzahl_classification.csv", index=False)

    logger.info("Formzahl = %s | %s", tidal_result["formzahl"], tidal_result["classification"])

    # ============================================================
    # 4. FORECAST
    # ============================================================
    if forecast_start and forecast_end:
        logger.info(
            "[4/7] Forecast periode operasi %s s.d. %s...",
            forecast_start, forecast_end,
        )
    else:
        logger.info("[4/7] Forecast %d hari...", args.forecast_days)

    forecast_df = fforecast.generate_forecast(
        coef=tidal_result["coef"],
        df=analysis_df,
        forecast_days=(args.forecast_days or config.DEFAULT_FORECAST_DAYS),
        interval=args.forecast_interval,
        forecast_start=forecast_start,
        forecast_end=forecast_end,
    )
    forecast_df.to_csv(outdir / "04_forecast.csv", index=False)

    # ============================================================
    # 5. THRESHOLD
    # ============================================================
    logger.info("[5/7] Threshold %.3f %s...", args.threshold, config.WATER_LEVEL_UNIT)
    threshold_df = testthreshold.apply_threshold(forecast_df, threshold=args.threshold)
    threshold_df.to_csv(outdir / "05_forecast_threshold.csv", index=False)
    pd.DataFrame([testthreshold.get_threshold_summary(threshold_df)]).to_csv(
        outdir / "05_threshold_summary.csv", index=False
    )

    # ============================================================
    # 6. VISUALIZATION -- OBSERVED+INTERPOLATED AND FORECAST
    # ============================================================
    logger.info("[6/7] Visualisasi garis observasi + interpolasi, forecast, dan threshold...")
    if not args.no_plot:
        ggrafik.plot_tide(
            processed_df=analysis_df,
            forecast_df=forecast_df,
            threshold=args.threshold,
            title="Grafik Pasang Surut — Observasi + Interpolasi, Forecast, dan Threshold",
        )

    # ============================================================
    # 7. CALENDAR
    # ============================================================
    logger.info("[7/7] Membuat kalender forecast...")
    calendar_df = calender.generate_hourly_calendar(threshold_df)
    calendar_df.to_csv(outdir / "07_tide_calendar.csv", index=False)
    pd.DataFrame([calender.get_calendar_summary(calendar_df)]).to_csv(
        outdir / "07_calendar_summary.csv", index=False
    )

    logger.info("CORE PIPELINE SELESAI. Output utama: %s", outdir.resolve())

    # ============================================================
    # OPTIONAL SIDE-CAR: EXTERNAL HOBO VALIDATION
    # ============================================================
    if not args.no_validation and validation_csv_path:
        try:
            _run_external_validation_sidecar(args, validation_csv_path, outdir)
        except Exception as exc:
            logger.exception(
                "Validasi HOBO gagal, tetapi core pipeline dan grafik tetap selesai. "
                "Penyebab: %s",
                exc,
            )
    elif args.no_validation:
        logger.info("[SIDE-CAR] Validasi HOBO dinonaktifkan.")
    else:
        logger.info("[SIDE-CAR] Validasi HOBO dilewati karena file tidak tersedia.")


if __name__ == "__main__":
    main()
