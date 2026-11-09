# External HOBO Validation — Revised Architecture

Validasi HOBO sekarang merupakan **sidecar independen** dan tidak digunakan
untuk membuat atau mengubah grafik operasional, koefisien UTide, forecast,
threshold, maupun kalender.

## Apa yang divalidasi?

HOBO dibandingkan dengan seri sensor hasil:

`raw ThingSpeak -> QC -> regular time grid -> interpolation`

Jadi target validasi adalah **raw + interpolasi**, bukan rekonstruksi UTide.

## Periode validasi

Periode validasi ditentukan otomatis dari timestamp HOBO. Pipeline validasi
mengambil data ThingSpeak tersendiri pada rentang tersebut, sehingga file HOBO
lama tetap dapat divalidasi walaupun core pipeline sedang berjalan untuk data
hari ini.

## Penanganan HOBO

Default saat ini:

- clock export: 12 jam tanpa AM/PM;
- anchor awal: `2026-07-25 13:29:00`;
- input unit: `m`;
- target unit: `cm`;
- bottom offset: `20 cm`;
- correction: `subtract`;
- grid perbandingan: `15min`.

Semua parameter dapat diubah di `config.py`.

## Statistik

External HOBO Validation Report menghitung:

- RMSE
- MAE
- Bias
- Pearson correlation
- R²
- NSE
- residual min/max/std
- mean HOBO dan mean processed sensor
- jumlah pasangan observasi/interpolasi sensor yang masuk validasi

Output validasi disimpan terpisah di:

`output/validation_hobo/`

Jika validasi gagal, core pipeline tetap lanjut dan grafik/forecast tetap
tersedia.
