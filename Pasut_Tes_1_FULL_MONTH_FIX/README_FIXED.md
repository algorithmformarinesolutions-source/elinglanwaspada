# Pasut_Tes_1 — modular direct-run pipeline

Core pipeline:

1. `apiloader.py` — historical ThingSpeak acquisition
2. `preprocessing.py` — QC, grid waktu, interpolation
3. `cobatidal_analysis.py` — statistics, UTide, Formzahl, reconstruction
4. `fforecast.py` — operational forecast
5. `testthreshold.py` — threshold/status
6. `ggrafik.py` — visualization
7. `calender.py` — calendar output

`ini_validasi.py` berjalan sebagai **external validation sidecar**, bukan bagian
dari aliran data yang membentuk grafik/forecast.

## Direct run

```bash
python run_pipeline.py
```

Atau klik **Run Python File (▶)** pada `run_pipeline.py` di VS Code.

Default direct-run:

- operational start = waktu script dijalankan;
- operational end = +1 bulan kalender;
- historical fitting window = 1 bulan sebelum waktu run sampai waktu run;
- threshold = 125 cm;
- HOBO validation terpisah dari visualisasi.

CLI tetap bisa dipakai untuk override kebutuhan pengujian.

Lihat `README_REVISION_SEP2026.md` untuk detail revisi terbaru.
