# WALHI Gelombang — SMB/CERC (VS Code)

Konversi modular dari notebook `peramalan_gelombang_SMB.ipynb` menjadi proyek Python `.py` yang dapat dijalankan ulang di VS Code.

## Struktur

- `main_script.py` — entry point seluruh pipeline satu bulan.
- `config.py` — konfigurasi `.env`.
- `thingspeak_loader.py` — mengambil data private ThingSpeak dengan rentang otomatis.
- `processing.py` — resampling jam-an + interpolasi gap kecil; arah menggunakan circular mean.
- `smb_wave.py` — rumus SMB/CERC untuk Hs, Ts, dan governing condition.
- `alerts.py` — status AMAN/WASPADA/BAHAYA dari Hs dan angin.
- `visualization.py` — membuat PNG tanpa `plt.show()` yang memblokir proses.
- `plot_viewer.py` — membuka ulang PNG kapan saja tanpa fetch/perhitungan ulang.
- `realtime_status.py` — opsional, satu kali cek feed terbaru; tidak polling.
- `outputs/` — CSV, PNG, metadata, statistik.

## Setup VS Code / terminal

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Menjalankan pipeline

```bash
python main_script.py
```

Rentang data ditentukan otomatis saat program dijalankan:

`date_start = waktu run - 1 bulan kalender`

`date_end = waktu run`

Tidak ada forecast ke waktu mendatang. SMB/CERC dipakai untuk mengestimasi kondisi gelombang dari observasi angin pada periode historis tersebut.

### Kontrol grafik

Default `.env` = `AUTO_OPEN_PLOTS=true`. Grafik dibuat dan disimpan lebih dulu, lalu dibuka melalui image viewer OS. Proses Python **tidak menunggu jendela grafik ditutup**.

Jika grafik sudah ditutup, buka lagi tanpa menjalankan pipeline:

```bash
python plot_viewer.py
```

Menjalankan pipeline tanpa membuka viewer:

```bash
python main_script.py --no-open-plots
```

## Output utama

- `outputs/raw_angin_thingspeak_1bulan.csv`
- `outputs/estimasi_gelombang_semarang_1bulan.csv`
- `outputs/ringkasan_statistik_1bulan.csv`
- `outputs/run_metadata.json`
- `outputs/grafik_gelombang_1bulan.png`
- `outputs/wave_rose_gelombang.png`

## Catatan field ThingSpeak

Notebook sumber menggunakan `field1 = wind_speed` dan `field2 = wind_dir`, sehingga itu dijadikan default. Jika Channel 3433995 menggunakan field berbeda, cukup ubah:

```env
WIND_SPEED_FIELD=field1
WIND_DIR_FIELD=field2
```

## Keamanan key

API key private disimpan di `.env`, bukan ditulis di source code Python. `.gitignore` sudah mengabaikan `.env`. Jangan mengunggah `.env` ke repository publik.
