"""Master script for the end-to-end tidal data pipeline.

Pipeline order
1. ThingSpeak data acquisition (apiloader)
2. preprocessing / QC / interpolation
3. tidal harmonic analysis + Formzahl (cobatidal_analysis)
4. validation (ini_validasi)
5. forecast (fforecast)
6. threshold classification (testthreshold)
7. visualization (ggrafik)
8. calendar generation (calender)

Run this file, not the individual modules, to execute the complete workflow.
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="End-to-end pipeline data pasang surut ThingSpeak.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--latest", type=int, default=None, metavar="N", help="Ambil N data terbaru. Default: 8000.")
    mode.add_argument("--start", type=str, default=None, help="Awal rentang YYYY-MM-DD HH:MM:SS.")
    p.add_argument("--end", type=str, default=None, help="Akhir rentang; wajib bersama --start.")
    p.add_argument("--freq", default=config.DEFAULT_SAMPLE_FREQ, help="Grid preprocessing, mis. 15min.")
    p.add_argument("--method", choices=["auto", "harmonic", "linear"], default="auto")
    p.add_argument("--valid-min", type=float, default=None)
    p.add_argument("--valid-max", type=float, default=None)
    p.add_argument("--forecast-days", type=int, default=30)
    p.add_argument("--forecast-interval", default="1h")
    p.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD)
    p.add_argument("--outdir", default=config.OUTPUT_FOLDER)
    p.add_argument(
        "--validation-csv",
        default=None,
        help="CSV observasi eksternal (mis. HOBO). Jika tidak diberikan, validation memakai data observasi pipeline; sifatnya in-sample.",
    )
    p.add_argument("--validation-time-col", default="time")
    p.add_argument("--validation-value-col", default="water_level")
    p.add_argument("--validation-tolerance", default="1min")
    p.add_argument("--no-plot", action="store_true", help="Jangan tampilkan grafik interaktif.")
    return p.parse_args()


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
    return data[required + (["data_source"] if "data_source" in data.columns else [])]


def _load_external_validation_csv(path: str, time_col: str, value_col: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    if time_col not in raw.columns or value_col not in raw.columns:
        raise ValueError(
            f"CSV validasi harus memiliki kolom '{time_col}' dan '{value_col}'. "
            f"Kolom tersedia: {list(raw.columns)}"
        )
    return raw[[time_col, value_col]].rename(columns={time_col: config.COL_TIME, value_col: config.COL_WL})


def _save_basic_stats(stats: dict, path: Path) -> None:
    out = stats.copy()
    for key, value in out.items():
        if isinstance(value, pd.Timestamp):
            out[key] = value.isoformat()
    pd.DataFrame([out]).to_csv(path, index=False)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = parse_args()

    if args.end and not args.start:
        raise SystemExit("--end hanya boleh digunakan bersama --start.")
    if args.start and not args.end:
        raise SystemExit("--start wajib disertai --end.")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 1. DATA ACQUISITION
    # ============================================================
    logger.info("[1/8] Mengambil data dari ThingSpeak...")
    if args.start and args.end:
        raw = apiloader.load_period(start=args.start, end=args.end)
    else:
        raw = apiloader.load_latest(results=args.latest or 8000)

    raw_path = outdir / "01_raw_ultrasonic_tide.csv"
    raw.to_csv(raw_path, index=False)
    logger.info("Data mentah: %d baris -> %s", len(raw), raw_path)
    if raw.empty:
        logger.warning("Tidak ada data mentah. Pipeline dihentikan.")
        return

    # ============================================================
    # 2. PREPROCESSING
    # ============================================================
    logger.info("[2/8] Quality control + konversi waktu + interpolasi...")
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
    clean.to_csv(outdir / "02_clean_ultrasonic_tide.csv")

    analysis_df = _prepare_clean_for_tidal_analysis(clean)
    logger.info("Data siap analisis pasut: %d baris", len(analysis_df))

    # ============================================================
    # 3. TIDAL ANALYSIS
    # ============================================================
    logger.info("[3/8] UTide harmonic analysis + Formzahl...")
    stats = cobatidal_analysis.compute_basic_statistics(analysis_df)
    _save_basic_stats(stats, outdir / "03_basic_tidal_statistics.csv")

    tidal_result = cobatidal_analysis.run_full_analysis(
        analysis_df,
        latitude=config.STATION_LATITUDE,
        reconstruct_on="observed",
    )
    pd.DataFrame({
        "formzahl": [tidal_result["formzahl"]],
        "classification": [tidal_result["classification"]],
    }).to_csv(outdir / "03_formzahl_classification.csv", index=False)

    reconstruction = tidal_result["prediction"].copy()
    reconstructed = analysis_df.merge(reconstruction, on=config.COL_TIME, how="left")
    reconstructed.to_csv(outdir / "03_tidal_reconstruction.csv", index=False)

    logger.info("Formzahl = %s | %s", tidal_result["formzahl"], tidal_result["classification"])

    # ============================================================
    # 4. VALIDATION
    # ============================================================
    logger.info("[4/8] Validasi...")
    prediction_for_validation = reconstruction
    if args.validation_csv:
        observed_validation = _load_external_validation_csv(
            args.validation_csv,
            args.validation_time_col,
            args.validation_value_col,
        )
        validation_label = "external"
    else:
        observed_validation = analysis_df[[config.COL_TIME, config.COL_WL]].copy()
        validation_label = "in_sample"
        logger.warning(
            "Tidak ada --validation-csv. Validasi menggunakan data yang juga dipakai untuk fitting UTide (in-sample), bukan validasi independen."
        )

    val_result = ini_validasi.run_full_validation(
        prediction_for_validation,
        observed_validation,
        tolerance=args.validation_tolerance,
    )
    ini_validasi.print_validation_report(val_result)
    ini_validasi.save_validation_report(
        val_result,
        output_dir=str(outdir / "04_validation"),
        prefix=f"{validation_label}_validation",
    )

    # ============================================================
    # 5. FORECAST
    # ============================================================
    logger.info("[5/8] Forecast %d hari, interval %s...", args.forecast_days, args.forecast_interval)
    forecast_df = fforecast.generate_forecast(
        coef=tidal_result["coef"],
        df=analysis_df,
        forecast_days=args.forecast_days,
        interval=args.forecast_interval,
    )
    forecast_df.to_csv(outdir / "05_forecast.csv", index=False)

    # ============================================================
    # 6. THRESHOLD
    # ============================================================
    logger.info("[6/8] Threshold %.3f m...", args.threshold)
    threshold_df = testthreshold.apply_threshold(forecast_df, threshold=args.threshold)
    threshold_df.to_csv(outdir / "06_forecast_threshold.csv", index=False)
    pd.DataFrame([testthreshold.get_threshold_summary(threshold_df)]).to_csv(
        outdir / "06_threshold_summary.csv", index=False
    )

    # ============================================================
    # 7. GRAPH
    # ============================================================
    logger.info("[7/8] Menyiapkan grafik...")
    plot_df = pd.concat(
        [
            reconstructed[[config.COL_TIME, config.COL_WL, config.COL_WL_PREDICTED]],
            forecast_df.assign(**{config.COL_WL: pd.NA})[[config.COL_TIME, config.COL_WL, config.COL_WL_PREDICTED]],
        ],
        ignore_index=True,
    )
    if not args.no_plot:
        ggrafik.plot_tide(
            plot_df,
            threshold=args.threshold,
            title="Observasi, Rekonstruksi UTide, dan Forecast Pasut",
        )

    # ============================================================
    # 8. CALENDAR
    # ============================================================
    logger.info("[8/8] Membuat kalender forecast...")
    calendar_df = calender.generate_hourly_calendar(threshold_df)
    calendar_df.to_csv(outdir / "08_tide_calendar.csv", index=False)
    pd.DataFrame([calender.get_calendar_summary(calendar_df)]).to_csv(
        outdir / "08_calendar_summary.csv", index=False
    )

    logger.info("PIPELINE SELESAI. Semua output berada di: %s", outdir.resolve())


if __name__ == "__main__":
    main()
