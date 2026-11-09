# Revisi Pipeline Pasut — September 2026

## 1. Periode dinamis saat Direct Run

Ketika `run_pipeline.py` dijalankan, `config.py` otomatis membuat:

- `PERIOD_DATE_START` = waktu lokal saat script mulai dijalankan, sampai detik.
- `PERIOD_DATE_END` = tepat satu bulan kalender setelah `PERIOD_DATE_START`.

Contoh bila script mulai pada `2026-09-15 14:38:40`:

- start operasi/forecast: `2026-09-15 14:38:40`
- end operasi/forecast: `2026-10-15 14:38:40`

ThingSpeak tidak dapat menyediakan observasi masa depan. Karena itu data untuk harmonic fitting dipisahkan menjadi jendela historis satu bulan yang berakhir saat script dijalankan. Default:

- data history start = satu bulan sebelum run
- data history end = waktu run
- forecast = waktu run sampai +1 bulan kalender

## 2. Validasi HOBO menjadi sidecar independen

HOBO tidak lagi divalidasi terhadap rekonstruksi UTide. Target validasi sekarang adalah data sensor hasil preprocessing:

`raw observation -> QC -> regular time grid -> interpolation`

Validasi HOBO:

1. membaca CSV HOBO;
2. memperbaiki clock 12-jam tanpa AM/PM menggunakan anchor;
3. mengubah unit HOBO ke unit utama pipeline;
4. menerapkan koreksi vertical offset bila diaktifkan;
5. menentukan periode HOBO;
6. mengambil data ThingSpeak tersendiri pada periode HOBO;
7. preprocessing/interpolasi data ThingSpeak tersendiri;
8. menyamakan grid waktu HOBO dan sensor;
9. menghitung External HOBO Validation Report.

Default saat ini:

- HOBO input unit: `m`
- target unit: `cm`
- bottom offset: `20 cm`
- correction: `subtract`
- comparison grid: `15min`

Semua nilai tersebut bisa diubah di `config.py`.

Penting: validasi adalah sidecar. Jika validasi gagal (misalnya file HOBO tidak tersedia atau tidak ada data ThingSpeak pada periode tersebut), core pipeline tetap menyelesaikan forecast, threshold, visualisasi, dan kalender.

## 3. Visualisasi

Grafik utama tidak menggunakan data HOBO dan tidak menampilkan rekonstruksi historis UTide maupun forecast. Grafik hanya menampilkan satu garis kontinu:

- `Data pasut (observasi + interpolasi)` — gabungan titik observasi sensor yang tersedia dan nilai hasil interpolasi preprocessing pada grid waktu reguler.

Informasi asal data (`observed` atau `interpolated_*`) tetap tersimpan pada kolom `data_source` di output preprocessing untuk audit, tetapi tidak dipisahkan menjadi simbol/garis berbeda pada plot.

UTide tetap digunakan untuk analisis harmonik/Formzahl dan menghasilkan koefisien yang dipakai oleh modul forecast, namun rekonstruksi historis UTide tidak lagi dibuat atau ditampilkan sebagai komponen grafik. Threshold dan forecast tetap tersedia sebagai output numerik/kalender, tetapi tidak digambar pada grafik pasut utama.

## Direct Run VS Code

Tidak perlu command panjang:

1. Buka `run_pipeline.py`.
2. Klik **Run Python File (▶)**.
3. Konfigurasi efektif akan dicetak ke terminal.

CLI override tetap tersedia jika dibutuhkan.

## Fix pengambilan data historis 1 bulan penuh

`config.py` memang menghitung jendela historis sebagai **1 bulan kalender sebelum waktu Run**. Contoh Run pada 19 September menghasilkan request mulai 19 Agustus.

Masalah versi sebelumnya berasal dari batas ThingSpeak **8000 feed per request**. Loader awal meminta chunk 14 hari; pada logging yang rapat, satu chunk dapat melebihi 8000 data dan API hanya mengembalikan sebagian data terbaru dalam chunk tersebut. Akibatnya CSV/grafik dapat baru dimulai beberapa hari setelah tanggal awal yang diminta.

Versi ini mempertahankan jendela historis 1 bulan, tetapi `apiloader.fetch_range()` sekarang otomatis membagi ulang setiap window yang menyentuh 8000 record sampai semua data dapat diambil. Jadi CSV raw, preprocessing, dan garis historis pada grafik menggunakan seluruh data yang tersedia dari `DEFAULT_START` sampai waktu Run.
