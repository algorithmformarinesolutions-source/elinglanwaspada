# Revisi waktu HOBO 25–27 Juli 2026

## Masalah sumber data

File HOBO memakai kolom `Time` berbentuk clock 12-jam, tetapi tidak menyimpan penanda AM/PM. Karena itu `01:29:00` secara tekstual ambigu: bisa berarti 01:29 atau 13:29.

Pada deployment ini logger diketahui mulai pada **25 Juli 2026 pukul 13:29**. Baris pertama `07/25/26;01:29:00;...` karena itu harus dibaca sebagai `2026-07-25 13:29:00`.

Solusi pada `ini_validasi.py` tidak sekadar menambahkan 12 jam ke semua baris. Parser menggunakan waktu awal aktual sebagai **anchor**, mengubah clock ke posisi dalam siklus 12 jam, lalu melakukan **unwrapping** berdasarkan urutan kronologis baris. Dengan cara ini tengah malam dan tengah hari dapat dibedakan dengan benar.

Contoh hasil:

```text
raw                         reconstructed
07/25/26 01:29:00    ->    2026-07-25 13:29:00
07/25/26 11:59:00    ->    2026-07-25 23:59:00
07/26/26 12:00:00    ->    2026-07-26 00:00:00
07/26/26 11:59:00    ->    2026-07-26 11:59:00
07/26/26 12:00:00    ->    2026-07-26 12:00:00
07/26/26 11:59:00    ->    2026-07-26 23:59:00
07/27/26 12:00:00    ->    2026-07-27 00:00:00
07/27/26 01:30:00    ->    2026-07-27 13:30:00
```

## Hasil QC pada file yang diberikan

Dengan anchor `2026-07-25 13:29:00`:

- input: 2.882 baris;
- output: 2.882 observasi;
- timestamp unik: 2.882;
- timestamp aktual duplikat: 0;
- rentang: 2026-07-25 13:29 sampai 2026-07-27 13:30;
- durasi: 2 hari 1 menit;
- ketidakcocokan tanggal ekspor: 0;
- interval sampling tidak sesuai 1 menit: 0.

File `04_validation/hobo_time_diagnostics.csv` akan menyimpan `raw_date`, `raw_time`, `reconstructed_time`, interval, dan hasil QC untuk audit.

## Menjalankan pipeline

Contoh Windows Command Prompt:

```bat
python run_pipeline.py ^
  --start "2026-07-25 00:00:00" ^
  --end "2026-07-27 23:59:59" ^
  --validation-csv "data pasut hobo 25-27 juli 2026.csv" ^
  --validation-time-mode 12h_no_ampm ^
  --validation-start-datetime "2026-07-25 13:29:00"
```

Untuk file HOBO lain yang sudah benar-benar memakai clock 24-jam, gunakan:

```bat
--validation-time-mode 24h
```

dan `--validation-start-datetime` tidak diperlukan.

## Prinsip validasi

Data HOBO hanya digunakan sebagai observasi eksternal. Setelah timestamp dan satuan HOBO dikoreksi, data HOBO disejajarkan dengan seri ThingSpeak hasil raw + preprocessing + interpolasi pada periode yang sama, kemudian dihitung RMSE, MAE, bias, korelasi, R², dan NSE. HOBO tidak memengaruhi grafik atau koefisien UTide utama.
