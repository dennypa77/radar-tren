# Radar Tren Desain (HOG)

CLI untuk mengumpulkan sinyal tren desain mingguan dari 4 sumber hulu (Pinterest
Trends, TikTok Creative Center, Google Trends, AniList) ke satu Google Sheet,
sebagai bahan penentuan produk/SKU baru di percetakan HOG.

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

3. Buat service account Google (sekali saja, ini yang dipakai `radar sync` untuk
   nulis ke Sheet tanpa perlu login interaktif tiap minggu):

   1. Buka [console.cloud.google.com](https://console.cloud.google.com/), login
      pakai akun Google yang sama dengan pemilik/pengelola Sheet (`hobjectgroup@gmail.com`).
   2. Buat project baru (pojok kiri atas, dropdown project -> **New Project**).
      Nama bebas, mis. `radar-tren-hog`.
   3. Di search bar atas, cari **"Google Sheets API"** -> buka -> klik **Enable**.
      Ulangi untuk **"Google Drive API"** (dibutuhkan library `gspread` untuk
      membuka file lewat ID).
   4. Masih di project yang sama, cari **"Service Accounts"** (atau menu
      **IAM & Admin -> Service Accounts**) -> **Create Service Account**.
      - Nama: mis. `radar-tren-bot`. Role/permission project bisa dilewati
        (skip) -- tidak perlu, karena aksesnya diatur lewat sharing Sheet,
        bukan lewat IAM project.
   5. Klik service account yang baru dibuat -> tab **Keys** -> **Add Key** ->
      **Create new key** -> pilih **JSON** -> download. File inilah yang jadi
      `service-account.json`.
   6. Simpan file itu di folder proyek ini (atau di mana saja), lalu **jangan
      pernah commit ke git** -- sudah otomatis diabaikan lewat `.gitignore`
      selama namanya mengandung `service-account` atau `credentials`.
   7. Buka file JSON-nya, cari field `"client_email"` -- itu email service
      account-nya (bentuknya `xxx@xxx.iam.gserviceaccount.com`).
   8. Buka Sheet **"Radar Tren"**, klik **Share**, tempel email dari langkah 7,
      beri akses **Editor**, lalu **Send/Share** (tidak perlu notifikasi email).
      Tanpa langkah ini, `radar sync` akan gagal dengan error izin ditolak.

4. Salin `.env.example` ke `.env` dan isi:

   ```bash
   copy .env.example .env
   ```

   - `GOOGLE_SERVICE_ACCOUNT_FILE` -- path ke file JSON dari langkah 3 di atas.
   - `GOOGLE_SHEETS_ID` -- ID spreadsheet tujuan (bagian antara `/d/` dan `/edit`
     di URL Sheet).

5. Cek `config/kata_pantau.yaml` -- daftar 10-15 kata pantau (campur Indonesia &
   Inggris) sudah diisi contoh awal. **Daftar ini terkunci sampai tanggal
   `dikunci_sampai`** supaya data antar-minggu bisa dibandingkan. Kalau memang
   perlu diubah lebih awal, jalankan `radar init --terima-perubahan-kata-pantau`
   setelah mengedit file untuk menyimpan baseline baru secara sengaja.

6. Jalankan:

   ```bash
   radar init
   ```

   Ini membuat `radar.db` (SQLite lokal, **jangan commit**, sudah masuk
   `.gitignore`) dan memvalidasi config.

## Cara ambil export dari tiga UI sumber

### Pinterest Trends (trends.pinterest.com)

> **Region Indonesia (ID) tidak tersedia** di Pinterest Trends (dicek langsung
> 2026-09-07). Denny memutuskan pakai **kedua** region terdekat: **Philippines
> (PH) dan Malaysia (MY)** -- bukan pilih salah satu.
>
> **Temuan penting (2026-09-07):** versi publik Pinterest Trends TIDAK punya
> alat cari-per-kata-kunci seperti Google Trends -- jadi kita **tidak bisa**
> cek skor spesifik untuk tiap kata pantau di `config/kata_pantau.yaml`. Yang
> tersedia tanpa login hanya tabel **"Search trends"**: 5 kata kunci yang
> SEDANG trending apa adanya (bukan hasil pencarian kita), dengan kolom
> perubahan mingguan/bulanan/tahunan dalam persen -- bukan indeks 0-100. Akses
> lebih dalam (daftar penuh) minta login ke akun Pinterest Business. Denny
> memutuskan: pakai daftar "Search trends" apa adanya sebagai sinyal budaya
> visual mentah, bukan dipaksa cocok dengan 12 kata pantau kita.

1. Buka [trends.pinterest.com](https://trends.pinterest.com), pilih region
   **Philippines**, scroll ke bagian **"Search trends"**, salin isi tabelnya
   (5 baris: Keywords, Weekly change, Monthly change, Yearly change) ke CSV.
   Ulangi untuk region **Malaysia**.
2. Impor kedua file terpisah (kolom `region` yang membedakan keduanya di DB,
   jadi tidak bentrok):

   ```bash
   radar impor --sumber pinterest --file pinterest_ph_2026-W37.csv --region PH
   radar impor --sumber pinterest --file pinterest_my_2026-W37.csv --region MY
   ```

   Contoh isi CSV yang valid:

   ```csv
   Keywords,Weekly change,Monthly change,Yearly change
   wikang filipino at al poster,20%,10000%+,10000%+
   lesbian space princess,6000%,10000%+,10000%+
   ```

### TikTok Creative Center (ads.tiktok.com/business/creativecenter)

> **Catatan (2026-09-07):** TikTok me-rebrand produk ini jadi "TikTok One
> Creative Suite" -- URL lama redirect ke halaman marketing umum. Trends
> sekarang ada di `ads.tiktok.com/creative/creativeCenter/trends/hashtag?region=ID`
> (ganti `hashtag` dengan bagian lain kalau tersedia). Pola aksesnya sama
> seperti sebelumnya: browsing dasar (top 3 per kategori) tanpa login, data
> lengkap + export CSV tetap butuh login akun TikTok biasa.

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

### Google Trends (trends.google.com)

Ditambahkan atas keputusan Denny (2026-09-07) supaya sinyal Indonesia lebih
kuat -- Pinterest Trends tidak punya region ID, Google Trends punya.

1. Buka [trends.google.com](https://trends.google.com/trends/explore), pilih
   region **Indonesia**, masukkan sampai 5 kata pantau sekaligus untuk
   dibandingkan (Google Trends batasi 5 per explore).
2. Klik tombol **export** (ikon unduh) di grafik "Interest over time" untuk
   unduh CSV mentahnya (jangan diedit manual).
3. Ulangi untuk sisa kata pantau (12 kata pantau = sekitar 3 file @ 4-5 istilah).
4. Impor tiap file:

   ```bash
   radar impor --sumber google-trends --file google_trends_batch1.csv
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

Dijalankan **manual** oleh operator, bukan lewat scheduler/cron (keputusan
Denny, 2026-09-07 -- sejalan dengan Non-Goal di brief: otomatisasi jadwal
belum diperlukan sampai ritme mingguannya terbukti jalan).

```bash
radar status                                          # cek minggu bolong dulu
radar impor --sumber pinterest --file pinterest_ph.csv --region PH
radar impor --sumber pinterest --file pinterest_my.csv --region MY
radar impor --sumber tiktok --file keyword.csv --bagian keyword
radar impor --sumber tiktok --file hashtags.csv --bagian hashtag
radar impor --sumber tiktok --file products.csv --bagian top_products
radar impor --sumber google-trends --file google_trends_batch1.csv
radar impor --sumber google-trends --file google_trends_batch2.csv
radar impor --sumber google-trends --file google_trends_batch3.csv
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
| `radar impor --sumber pinterest\|tiktok\|google-trends --file X.csv` | Impor export CSV |
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
