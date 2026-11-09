# EWS Bedono: backend sumber + frontend terbaru

## Struktur utama
- `frontend/html.html` dan `frontend/script.js`: file frontend dari ZIP terbaru yang diunggah.
- `src/`: Express API untuk `/weather`, `/climate`, dan `/tide`.
- `Pasut_Tes_1_FULL_MONTH_FIX/`, `Pasut_Tes_1_FIXED_DIR/`, `walhi_gelombang/`: modul Python yang disertakan pada backend sumber.
- `backend.env`: konfigurasi lokal ThingSpeak. Jangan unggah file ini ke repositori publik.

## Menjalankan backend
1. Pastikan Node.js sudah terpasang.
2. Dari folder proyek ini jalankan `npm install` bila diperlukan.
3. Jalankan `npm start`. Server berjalan di `http://localhost:3000`.
4. Buka `frontend/html.html` melalui Live Server VS Code.

Frontend meminta data ke `http://localhost:3000/weather`, `/climate`, dan `/tide`. Nilai live ditambahkan ke kartu frontend tanpa mengganti layout utamanya. Grafik iframe ThingSpeak yang sudah ada tetap menggunakan sumber aslinya. Tombol Hari Ini/7 Hari hanya mengubah status tombol; iframe sumber belum menyediakan endpoint arsip berbeda yang dapat dipastikan dari berkas yang diberikan.

## Catatan data
Endpoint pasut mengembalikan nilai terbaru dari field1 ThingSpeak dan tidak mengklaim sebagai prediksi. CSV HOBO yang ada di modul dipertahankan persis seperti pada backend sumber; keaslian/provenansinya tidak diverifikasi dalam proses penggabungan ini.


## Grafik berbasis backend (versi terbaru)
- `GET /tide?results=800`: nilai pasut terbaru dan deret waktu `series` dari feed ThingSpeak yang dikonfigurasi.
- `GET /weather/history?results=800`: riwayat arah angin (field2, derajat) dan kecepatan angin (field1, km/jam).
- Grafik pasut dan arah angin di frontend dirender dari dua endpoint tersebut, bukan iframe visualisasi ThingSpeak.
- Tombol `Hari Ini` dan `7 Hari` memfilter timestamp pasut yang tersedia di feed. Jika feed tidak mencakup periode tersebut, frontend menampilkan pesan bahwa data periode itu belum tersedia, bukan membuat data palsu.
- Kartu cuaca tidak lagi menampilkan iframe grafik kedua di bawah nilai terkini.
- Endpoint riwayat hanya dapat menampilkan jumlah/masa data yang memang masih tersedia di ThingSpeak; `results=800` meminta hingga 800 catatan, tetapi tidak menjamin feed memiliki catatan 7 hari penuh.
