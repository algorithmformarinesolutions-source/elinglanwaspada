"""Entry point pipeline gelombang WALHI.

Alur:
1) tentukan rentang satu bulan sebelum waktu run -> waktu run,
2) ambil observasi angin ThingSpeak,
3) resample jam-an dan interpolasi gap kecil,
4) estimasi Hs/Ts dengan SMB/CERC,
5) simpan CSV, statistik, metadata, dan grafik,
6) tampilkan status dari observasi terbaru,
7) buka file grafik secara non-blocking (opsional/default dari .env).
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from alerts import classify_realtime
from config import SETTINGS
from plot_viewer import open_saved_plots
from processing import resample_hourly
from smb_wave import add_wave_estimates
from thingspeak_loader import fetch_thingspeak_range, get_run_window
from visualization import save_monthly_timeseries, save_wave_rose

LOGGER = logging.getLogger("walhi_gelombang")


def _serialize_timestamp(ts: pd.Timestamp) -> str:
    return ts.isoformat()


def save_summary(df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    summary = df[["wind_speed", "Hs_m", "Ts_s"]].describe().loc[["mean", "min", "max", "std"]]
    summary.columns = ["Kec. Angin (m/s)", "Hs (m)", "Ts (s)"]
    summary.to_csv(output_path)
    return summary


def print_latest_status(df: pd.DataFrame) -> None:
    valid = df.dropna(subset=["wind_speed", "wind_dir", "Hs_m", "Ts_s"])
    if valid.empty:
        LOGGER.warning("Tidak ada observasi valid untuk status terbaru.")
        return

    latest = valid.iloc[-1]
    status, detail = classify_realtime(float(latest["Hs_m"]), float(latest["wind_speed"]))
    wind_knot = float(latest["wind_speed"]) * 1.94384

    print("\n" + "=" * 62)
    print("STATUS OBSERVASI TERBARU")
    print(f"Waktu data      : {latest['datetime']}")
    print(f"Kec. angin      : {latest['wind_speed']:.2f} m/s ({wind_knot:.1f} knot)")
    print(f"Arah angin/gel. : {latest['wind_dir']:.1f}°")
    print(f"Hs / Ts         : {latest['Hs_m']:.2f} m / {latest['Ts_s']:.2f} s")
    print(f"Governing       : {latest['kondisi']}")
    print(f"Status Hs       : {detail['Hs_m']['status']}")
    print(f"Status angin    : {detail['wind_knot']['status']}")
    print(f"STATUS AKHIR    : {status}")
    print("=" * 62)


def run_pipeline(open_plots: bool | None = None) -> dict[str, Path]:
    settings = SETTINGS
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    date_start, date_end = get_run_window(settings.local_timezone)
    LOGGER.info("Rentang otomatis: %s s.d. %s", date_start, date_end)

    raw_df = fetch_thingspeak_range(settings, date_start, date_end)
    if raw_df.empty:
        raise RuntimeError("ThingSpeak tidak mengembalikan observasi angin pada rentang satu bulan terakhir.")
    LOGGER.info("Data raw ThingSpeak: %d baris", len(raw_df))

    raw_path = settings.output_dir / "raw_angin_thingspeak_1bulan.csv"
    raw_df.to_csv(raw_path, index=False)

    hourly_df = resample_hourly(
        raw_df,
        frequency=settings.resample_frequency,
        interpolation_limit=settings.max_interpolation_gap,
    )
    wave_df = add_wave_estimates(hourly_df, settings.fetch_meter, settings.duration_hours)

    processed_path = settings.output_dir / "estimasi_gelombang_semarang_1bulan.csv"
    wave_df.to_csv(processed_path, index=False)

    timeseries_path = save_monthly_timeseries(
        wave_df, settings.output_dir / "grafik_gelombang_1bulan.png"
    )
    rose_path = save_wave_rose(
        wave_df, settings.output_dir / "wave_rose_gelombang.png"
    )

    summary_path = settings.output_dir / "ringkasan_statistik_1bulan.csv"
    summary = save_summary(wave_df, summary_path)

    condition_counts = wave_df["kondisi"].dropna().value_counts()
    governing_mode = condition_counts.index[0] if not condition_counts.empty else None

    metadata = {
        "run_time_local": _serialize_timestamp(date_end),
        "date_start_local": _serialize_timestamp(date_start),
        "date_end_local": _serialize_timestamp(date_end),
        "local_timezone": settings.local_timezone,
        "channel_id": settings.channel_id,
        "station_latitude": settings.station_latitude,
        "station_longitude": settings.station_longitude,
        "wind_speed_field": settings.wind_speed_field,
        "wind_dir_field": settings.wind_dir_field,
        "fetch_meter": settings.fetch_meter,
        "duration_hours": settings.duration_hours,
        "raw_rows": int(len(raw_df)),
        "hourly_rows": int(len(wave_df)),
        "governing_mode_most_common": governing_mode,
        "note": "Estimasi SMB/CERC dari observasi angin; bukan forecast ke waktu mendatang.",
    }
    metadata_path = settings.output_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== RINGKASAN STATISTIK 1 BULAN ===")
    print(summary.round(3))
    if wave_df["Hs_m"].notna().any():
        idx = wave_df["Hs_m"].idxmax()
        print(f"\nHs maksimum : {wave_df.loc[idx, 'Hs_m']:.2f} m pada {wave_df.loc[idx, 'datetime']}")
    print(f"Governing terbanyak: {governing_mode}")
    print_latest_status(wave_df)

    outputs = {
        "raw_csv": raw_path,
        "processed_csv": processed_path,
        "summary_csv": summary_path,
        "metadata_json": metadata_path,
        "timeseries_png": timeseries_path,
        "wave_rose_png": rose_path,
    }

    print("\nOutput tersimpan:")
    for name, path in outputs.items():
        print(f" - {name:16s}: {path}")

    should_open = settings.auto_open_plots if open_plots is None else open_plots
    if should_open:
        try:
            open_saved_plots(settings.output_dir)
            print("\nGrafik dibuka melalui image viewer OS secara non-blocking.")
            print("Setelah ditutup, buka lagi kapan saja dengan: python plot_viewer.py")
        except Exception as exc:  # output tetap sudah tersimpan meski viewer gagal
            LOGGER.warning("Tidak dapat membuka image viewer otomatis: %s", exc)
            print("Grafik tetap tersimpan; buka manual dari folder outputs/.")

    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline estimasi gelombang SMB/CERC dari ThingSpeak.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--open-plots", action="store_true", help="Paksa buka grafik setelah pipeline selesai.")
    group.add_argument("--no-open-plots", action="store_true", help="Jangan buka grafik setelah pipeline selesai.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args()
    override: bool | None = None
    if args.open_plots:
        override = True
    elif args.no_open_plots:
        override = False
    run_pipeline(open_plots=override)


if __name__ == "__main__":
    main()
