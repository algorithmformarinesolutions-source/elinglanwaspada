# EWS Bedono — integrasi prediksi rob

## Komponen
- Frontend: `frontend/html.html` dan `frontend/script.js`.
- Backend: Node.js/Express pada `src/`.
- Pipeline pasut: `Pasut_Tes_1_FULL_MONTH_FIX/run_pipeline.py`.
- Threshold mengikuti konfigurasi pipeline `TIDE_THRESHOLD` (default 125 cm).

## Persiapan pertama kali
1. Install Node.js LTS dan Python 3.10+.
2. Dari root folder proyek, jalankan `npm install`.
3. Install dependensi pipeline: `python -m pip install -r Pasut_Tes_1_FULL_MONTH_FIX/requirements.txt`.
4. Periksa `backend.env`. Gunakan channel ID dan read API key ThingSpeak yang benar; jangan membagikan file ini ke repositori publik.
5. Jalankan backend dengan `npm start`.
6. Buka `frontend/html.html` memakai VS Code Live Server.

## API prediksi
- `GET /tide/forecast` mengembalikan hasil pipeline yang tersimpan jika belum berumur 30 menit; jika belum ada atau kedaluwarsa, backend menjalankan pipeline Python.
- `GET /tide/forecast?refresh=1` memaksa perhitungan ulang.
- `GET /tide?results=800` tetap untuk data observasi ThingSpeak, bukan prediksi.

Pipeline menggunakan data historis ThingSpeak, menjalankan preprocessing/analisis/forecast, menerapkan threshold, lalu menghasilkan kalender per jam. Validasi HOBO dimatikan untuk proses dashboard agar file validasi eksternal tidak ikut memengaruhi atau menghalangi prediksi operasional.

## Cara membaca kalender
- Merah berarti setidaknya satu jam pada tanggal itu berstatus `TINGGI` menurut fungsi threshold pipeline.
- Hijau berarti titik prediksi yang tersedia pada tanggal itu tidak melewati threshold.
- Abu-abu berarti tidak ada prediksi untuk tanggal itu.
- Ini adalah hasil model dan threshold konfigurasi, bukan jaminan keselamatan atau peringatan resmi. Validasi ambang fisik untuk lokasi Bedono tetap diperlukan.

## Jika prediksi belum muncul
Periksa terminal backend. Penyebab yang umum: Python belum terpasang/terdeteksi, dependensi (terutama UTide) belum diinstal, koneksi ThingSpeak gagal, atau data historis tidak mencukupi untuk analisis harmonik. Frontend sengaja tidak mengisi status dummy saat pipeline gagal.
