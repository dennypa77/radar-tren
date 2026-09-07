# Radar Tren Desain (HOG)

CLI untuk mengumpulkan sinyal tren desain mingguan dari 3 sumber hulu (Pinterest
Trends, TikTok Creative Center, AniList) ke satu Google Sheet, sebagai bahan
penentuan produk/SKU baru di percetakan HOG.

Tool ini sengaja **tipis**: hanya mengambil, menyimpan, dan menampilkan sinyal
mentah. Klasifikasi tema, skoring gabungan, dan keputusan produk dilakukan
manusia di tahap berikutnya (lihat brief).

## Setup (sekali di awal)

1. **Python 3.11+** harus terpasang.
2. Buat virtual environment dan install:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```

3. Salin `.env.example` ke `.env` dan isi:

   ```bash
   copy .env.example .env
   ```

   - `GOOGLE_SERVICE_ACCOUNT_FILE` -- path ke JSON service account Google (buat di
     Google Cloud Console, aktifkan Google Sheets API, download key JSON). **Jangan
     pernah commit file ini.**
   - `GOOGLE_SHEETS_ID` -- ID spreadsheet tujuan (bagian antara `/d/` dan `/edit`
     di URL). Kalau spreadsheet belum ada, buat manual dulu lalu share ke email
     service account (ada di dalam JSON-nya, field `client_email`) sebagai **Editor**.

4. Cek `config/kata_pantau.yaml` -- daftar 10-15 kata pantau (campur Indonesia &
   Inggris) sudah diisi contoh awal. **Daftar ini terkunci sampai tanggal
   `dikunci_sampai`** supaya data antar-minggu bisa dibandingkan. Kalau memang
   perlu diubah lebih awal, jalankan `radar init --terima-perubahan-kata-pantau`
   setelah mengedit file untuk menyimpan baseline baru secara sengaja.

5. Jalankan:

   ```bash
   radar init
   ```

   Ini membuat `radar.db` (SQLite lokal, **jangan commit**, sudah masuk
   `.gitignore`) dan memvalidasi config.

## Cara ambil export dari kedua UI sumber

### Pinterest Trends (trends.pinterest.com)

1. Buka [trends.pinterest.com](https://trends.pinterest.com), pilih region
   **Indonesia (ID)** kalau tersedia (kalau tidak, pakai region terdekat dan
   catat di config bahwa bobotnya akan diturunkan di tahap 2 -- ini bukan
   alasan berhenti).
2. Masukkan tiap kata pantau dari `config/kata_pantau.yaml`, catat/salin
   hasilnya (istilah, index 0-100, arah perubahan) ke CSV dengan kolom kira-kira:
   `Term, Index, WoW Change` (nama kolom boleh sedikit berbeda -- parser toleran
   terhadap variasi nama umum, tapi akan **gagal dengan pesan jelas** kalau
   kolom istilah/skor benar-benar tidak ditemukan).
3. Impor:

   ```bash
   radar impor --sumber pinterest --file pinterest_2026-W37.csv
   ```

### TikTok Creative Center (ads.tiktok.com/business/creativecenter)

1. Buka Creative Center, set region **Indonesia**. Browsing dasar tidak perlu
   login; untuk export butuh login akun TikTok biasa.
2. Export tiga bagian secara terpisah kalau tersedia: **Keyword Insights**,
   **Hashtags**, **Top Products**.
3. Impor tiap file (pakai `--bagian` kalau deteksi otomatis gagal):

   ```bash
   radar impor --sumber tiktok --file keyword_insights.csv --bagian keyword
   radar impor --sumber tiktok --file hashtags.csv --bagian hashtag
   radar impor --sumber tiktok --file top_products.csv --bagian top_products
   ```

### Kalender Rilis

Anime (otomatis, dari AniList -- tidak perlu file):

```bash
radar kalender-ambil --musim FALL --tahun 2026
```

Kategori lain (K-pop, film, game, kalender lokal) -- **diisi manual** dalam
CSV dengan kolom: `tanggal_rilis, kategori, judul, perkiraan_minat,
lini_hog_relevan, status_ip, catatan`:

```bash
radar kalender-impor --file kalender_manual_2026-W37.csv
```

## Alur mingguan (target ≤ 45 menit)

```bash
radar status                                          # cek minggu bolong dulu
radar impor --sumber pinterest --file pinterest.csv
radar impor --sumber tiktok --file keyword.csv --bagian keyword
radar impor --sumber tiktok --file hashtags.csv --bagian hashtag
radar impor --sumber tiktok --file products.csv --bagian top_products
radar kalender-ambil --musim FALL --tahun 2026        # sesuai musim berjalan
radar sync                                             # tulis ke Google Sheet
radar status                                           # verifikasi akhir
```

Kalau satu minggu memang tidak bisa diambil (libur, dsb), catat itu secara
sengaja supaya tidak terlihat seperti lubang data:

```bash
radar lewati --sumber pinterest --periode 2026-W38 --alasan "libur lebaran"
```

## Perintah

| Perintah | Fungsi |
|---|---|
| `radar init` | Buat DB + skema, validasi config |
| `radar impor --sumber pinterest\|tiktok --file X.csv` | Impor export CSV |
| `radar kalender-ambil --musim <WINTER\|SPRING\|SUMMER\|FALL> --tahun N` | Tarik data anime dari AniList |
| `radar kalender-impor --file X.csv` | Impor kalender rilis manual (non-anime) |
| `radar sync` | Tulis ulang SQLite -> Google Sheet |
| `radar status` | Ringkasan + minggu yang bolong (perintah paling sering dipakai) |
| `radar lewati --sumber S --periode P --alasan A` | Catat periode sengaja dilewati |

## Model data

SQLite (`radar.db`) adalah sumber kebenaran. Google Sheet hanya tampilan yang
ditulis ulang tiap `sync` -- **kecuali** tiga kolom di worksheet Kalender Rilis
yang diisi manusia langsung di Sheet (`lini_hog_relevan`, `status_ip`,
`catatan`), yang dibaca balik ke SQLite sebelum ditulis ulang supaya isian
manual tidak hilang. Ini satu-satunya jalur dua arah.

Tiga tabel: `sinyal`, `kalender_rilis`, `run_log`. `run_log` mencatat **setiap**
eksekusi termasuk yang gagal atau kosong -- lihat brief Bab 4 kenapa ini wajib.

## Yang sengaja TIDAK dibangun

Lihat Bab 2 brief. Ringkasnya: tidak ada klasifikasi tema/LLM, tidak ada skor
gabungan lintas sumber, tidak ada scraper Pinterest/TikTok, tidak ada analisis
gambar, tidak ada dashboard web, tidak ada normalisasi skor antar-sumber, dan
tidak ada scheduler otomatis. Semua itu tahap berikutnya di luar tool ini.
