# Pasut_Tes_1 — fixed modular pipeline

Urutan pipeline:
1. `apiloader.py` — ThingSpeak acquisition
2. `preprocessing.py` — QC, waktu, interpolasi
3. `cobatidal_analysis.py` — statistik dasar, UTide, Formzahl, rekonstruksi
4. `ini_validasi.py` — validation metrics
5. `fforecast.py` — forecast
6. `testthreshold.py` — threshold/status
7. `ggrafik.py` — visualization
8. `calender.py` — calendar output

`run_pipeline.py` adalah satu-satunya master/orchestrator.

## Instalasi

Gunakan environment Python yang sama dengan yang dipakai untuk menjalankan pipeline:

```bash
python -m pip install -r requirements.txt
```

atau minimal:

```bash
python -m pip install utide
```

## Menjalankan

```bash
python run_pipeline.py
```

Contoh mengambil rentang tanggal tertentu:

```bash
python run_pipeline.py --start "2026-07-01 00:00:00" --end "2026-07-31 23:59:59"
```

Contoh forecast 30 hari dengan interval 1 jam:

```bash
python run_pipeline.py --forecast-days 30 --forecast-interval 1h
```

Validasi eksternal:

```bash
python run_pipeline.py --validation-csv "hobo.csv" --validation-time-col time --validation-value-col water_level
```

## Perubahan utama

- Semua `!pip install ...` notebook syntax dihapus dari file `.py`.
- Tidak ada `google.colab` di level import.
- `cobatidal_analysis.py` tidak lagi mengambil data ThingSpeak saat di-import.
- Semua blok notebook `display(...)` dan eksekusi eksperimen dipisahkan dari fungsi library.
- `config.py` menjadi sumber konfigurasi kolom, lokasi stasiun, threshold, dan timezone.
- `run_pipeline.py` sekarang benar-benar menjalankan tahap 1–8 secara berurutan.
- `utide` dibuat sebagai dependency eksplisit di `requirements.txt`.

Catatan validasi: tanpa `--validation-csv`, pipeline melakukan validasi in-sample (rekonstruksi UTide dibanding data yang sama yang digunakan untuk fitting), sehingga bukan validasi independen. Untuk validasi HOBO, berikan file HOBO melalui `--validation-csv`.
