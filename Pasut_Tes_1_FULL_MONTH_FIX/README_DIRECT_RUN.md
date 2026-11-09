# Direct Run Pipeline Pasut di VS Code

Versi ini dapat dijalankan langsung dengan tombol **Run Python File (▶)** pada `run_pipeline.py`.

## Periode otomatis

Saat script dijalankan:

- periode operasi/forecast dimulai pada waktu run sampai detik;
- akhir periode otomatis satu bulan kalender kemudian;
- data historis untuk fitting diambil dari satu bulan sebelum waktu run sampai waktu run.

Dengan demikian pipeline tidak mencoba meminta data observasi masa depan dari ThingSpeak.

## Validasi HOBO

Validasi adalah proses sidecar yang terpisah dari grafik dan forecast utama. HOBO dibandingkan dengan data ThingSpeak hasil raw + preprocessing + interpolation pada periode HOBO itu sendiri, bukan dengan rekonstruksi UTide.

Default HOBO saat ini dapat diedit di `config.py`, termasuk unit input, unit target, bottom offset, correction, dan grid validasi.

## Grafik

Grafik utama menampilkan satu garis kontinu Data pasut (observasi + interpolasi). Rekonstruksi historis UTide, forecast, threshold, dan data HOBO tidak ditampilkan pada grafik ini; forecast/threshold tetap diproses untuk output numerik dan kalender.

Lihat `README_REVISION_SEP2026.md` untuk detail perubahan.
