"""Buka kembali grafik hasil tanpa mengambil/mengolah data ulang."""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from config import SETTINGS

PLOT_FILES = (
    "grafik_gelombang_1bulan.png",
    "wave_rose_gelombang.png",
)


def open_file_nonblocking(path: Path) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_saved_plots(output_dir: Path | None = None) -> list[Path]:
    output_dir = output_dir or SETTINGS.output_dir
    opened: list[Path] = []
    missing: list[Path] = []

    for name in PLOT_FILES:
        path = output_dir / name
        if path.exists():
            open_file_nonblocking(path)
            opened.append(path)
        else:
            missing.append(path)

    if missing:
        print("Grafik berikut belum ada (jalankan main_script.py minimal sekali):")
        for path in missing:
            print(" -", path)
    return opened


if __name__ == "__main__":
    opened = open_saved_plots()
    if opened:
        print("Grafik dibuka tanpa menjalankan ulang fetch/perhitungan:")
        for path in opened:
            print(" -", path)
