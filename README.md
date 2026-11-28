# ExTra (Expense Tracker) — v2.0.0

**ExTra** adalah aplikasi web pencatatan dan pemantauan keuangan pribadi berbasis foto struk belanja yang memanfaatkan **Google Gemini Flash Vision API** dengan pendekatan ***Human-in-the-Loop***.

Pengguna dapat mendaftar dan login secara aman, mengunggah foto struk belanja (`JPG`, `JPEG`, atau `PNG`) maupun mencatat pengeluaran secara manual, mengatur batas anggaran bulanan per kategori, mencatat pemasukan, serta meninjau ringkasan arus kas dan wawasan penghematan AI. Seluruh perhitungan angka keuangan (total bulanan, subtotal kategori, sisa anggaran, arus kas bersih) dijalankan 100% secara deterministik di backend Python & SQL (tanpa kalkulasi LLM).

---

## Fitur Utama (v2.0.0)

1. **Autentikasi Multi-User & Isolasi Data Ketat**
   - Registrasi, login, dan logout berbasis `bcrypt` + JWT `HttpOnly` cookie (dengan fallback `Authorization: Bearer`).
   - Setiap transaksi, pemasukan, anggaran, ekspor CSV, dan arsip foto struk terisolasi ketat berdasarkan `user_id`.
2. **Upload & Ekstraksi Struk Berbasis AI + Kompresi & Retry**
   - Mendukung *file picker* dan *drag-and-drop* (`JPG`, `JPEG`, `PNG`, maksimal **5 MB**) dengan validasi MIME/*magic bytes*, normalisasi EXIF, dan kompresi otomatis `Pillow` (lebar maksimum `1280px`).
   - Ketahanan panggilan Gemini Vision dengan timeout 30 detik, *auto-retry* *exponential backoff*, dan dukungan `GEMINI_FALLBACK_MODEL`.
   - Mengekstrak tanggal, nama barang, harga integer, dan saran kategori dari 7 kategori resmi tanpa menyimpan data toko/kasir/metode pembayaran.
3. **Tabel Preview Editable (*Human-in-the-Loop*) & Input Manual**
   - Pengguna dapat mengoreksi tanggal, nama barang, kategori, dan harga sebelum menekan **Konfirmasi & Simpan**, atau mencatat pengeluaran manual tanpa struk fisik.
   - Mendukung arsip opsional foto struk terkompresi di penyimpanan lokal terkelola (`uploads/receipts/`).
4. **Riwayat Transaksi & Ekspor CSV**
   - Pencarian *case-insensitive*, filter Bulan, Tahun, dan Kategori, edit item, hapus item/transaksi (*cascade delete* & *orphan cleanup*), penampil foto struk terarsip, serta unduhan laporan `.csv` (UTF-8 BOM).
5. **Pencatatan Pemasukan & Anggaran Bulanan (*Budgeting*)**
   - Pencatatan pemasukan (`incomes`) dan pengaturan batas anggaran per kategori per bulan/tahun (`budgets`).
   - Progress bar realisasi anggaran dengan indikator deterministik (`safe` < 80%, `warning` 80%–100%, `over_budget` > 100%).
6. **Ringkasan Arus Kas Bulanan, Grafik Modern, & AI Financial Insights**
   - Kartu metrik **Total Pemasukan**, **Total Pengeluaran**, **Arus Kas Bersih (*Net Balance*)**, dan **Kategori Terbesar**, dilengkapi grafik donat kategori & grafik batang harian (Recharts).
   - Modul terpisah **AI Financial Insights** (on-demand) yang menghasilkan narasi analisis & saran penghematan hanya dari statistik agregat backend tanpa mengakses baris transaksi mentah.

---

## Tech Stack

| Layer | Teknologi |
| :--- | :--- |
| **Backend & Static Server** | Python 3.10+, FastAPI, Uvicorn, Pydantic v2 |
| **Database & ORM Dual-Mode** | SQLAlchemy 2.x (SQLite lokal default + PostgreSQL `psycopg` v3 untuk produksi) |
| **Autentikasi & Keamanan** | `bcrypt`, `PyJWT` (`HS256` `HttpOnly` cookie / Bearer) |
| **Multimodal AI & Image** | Google Gemini Flash API (`google-genai`), `Pillow` |
| **Frontend Modern** | React 18, TypeScript, Vite, Tailwind CSS, Recharts |
| **Containerization & CI** | Docker (multi-stage), Docker Compose (`postgres:16-alpine`), GitHub Actions (`pytest` + `npm run build`) |

---

## Struktur Direktori

```text
ExTra/
├── .env.example                 # Template variabel environment
├── .gitignore                   # Mengabaikan .env, *.db, venv/, __pycache__/
├── requirements.txt             # Daftar dependensi Python minimal
├── PRD.md                       # Single Source of Truth spesifikasi produk
├── AGENTS.md                    # Panduan arsitektur & aturan pengembangan
├── README.md                    # Dokumentasi penggunaan proyek
├── test_connection.py           # Skrip verifikasi koneksi ke Google Gemini API
├── backend/
│   ├── main.py                  # Entry point FastAPI, static files, & error handlers
│   ├── config.py                # Pemuatan & validasi konfigurasi dari .env
│   ├── database.py              # Koneksi SQLite, PRAGMA foreign_keys, & DDL tabel
│   ├── schemas/
│   │   ├── receipt.py           # Skema Pydantic tahap 1 (ekstraksi preview AI)
│   │   ├── transaction.py       # Skema Pydantic tahap 2 (CRUD & penyimpanan)
│   │   └── summary.py           # Skema Pydantic ringkasan bulanan
│   ├── services/
│   │   ├── prompts.py           # System instruction & user prompt Gemini Vision
│   │   ├── ai_service.py        # Integrasi Gemini API & pemetaan domain error
│   │   ├── transaction_service.py # Operasi CRUD SQLite, filter, & orphan cleanup
│   │   └── summary_service.py   # Agregasi deterministik bulanan & harian
│   └── routers/
│       ├── receipts.py          # Endpoint POST /api/receipts/extract
│       ├── transactions.py      # Endpoint CRUD /api/transactions & /api/items
│       └── summary.py           # Endpoint GET /api/summary/monthly
├── frontend/
│   ├── index.html               # Antarmuka utama 3 tab (Upload, Riwayat, Ringkasan)
│   ├── css/
│   │   └── styles.css           # Styling responsif desktop & mobile
│   └── js/
│       ├── api.js               # Wrapper fetch REST API terpusat & helper format IDR
│       ├── upload.js            # Upload file, loading state, & tabel preview editable
│       ├── history.js           # Riwayat transaksi, search, filter, edit, & hapus
│       └── summary.js           # Kartu metrik bulanan & render grafik batang SVG
└── tests/
    ├── test_schemas.py          # Unit test skema Pydantic tahap ekstraksi & simpan
    ├── test_database.py         # Unit test CRUD SQLite, cascade delete, & orphan cleanup
    ├── test_summary.py          # Unit test akurasi agregasi bulanan & harian
    └── test_api.py              # Integration & full lifecycle test FastAPI (mock AI)
```

---

## Prasyarat

* **Python 3.10** atau versi lebih baru.
* **Google Gemini API Key** aktif yang diperoleh dari [Google AI Studio](https://aistudio.google.com/).

---

## Instalasi & Konfigurasi

### 1. Masuk ke Direktori Proyek & Buat Virtual Environment

**Windows (PowerShell):**
```powershell
cd ExTra
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux (Bash/Zsh):**
```bash
cd ExTra
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Konfigurasi Variabel Environment (`.env`)

Salin file `.env.example` menjadi `.env` di root proyek:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Buka file `.env` menggunakan teks editor dan isi `GEMINI_API_KEY` serta `JWT_SECRET` milik Anda:
```env
GEMINI_API_KEY=isi_dengan_gemini_api_key_anda
GEMINI_MODEL=gemini-3.5-flash-lite
JWT_SECRET=isi_dengan_random_secret_minimal_32_karakter
JWT_EXPIRE_MINUTES=1440
COOKIE_SECURE=false
# Kosongkan DATABASE_URL untuk memakai SQLite lokal (extra.db), atau isi URI PostgreSQL:
DATABASE_URL=
```
> **Catatan Keamanan:** Jangan pernah membagikan atau melakukan *commit* file `.env` ke repositori Git. File `.env` sudah masuk ke daftar `.gitignore`.

---

## Menguji Koneksi Gemini & Menjalankan Aplikasi

### 1. Uji Koneksi Google Gemini API (Opsional)
Pastikan API key dan koneksi ke model Gemini berfungsi sebelum menjalankan aplikasi:

```bash
python test_connection.py
```

### 2. Jalankan Server Aplikasi (Backend + Frontend)
Jalankan Uvicorn dari root folder proyek:

```bash
uvicorn backend.main:app --reload
```

*(Atau tanpa mengaktifkan venv di Windows PowerShell: `.\venv\Scripts\uvicorn.exe backend.main:app --reload`)*

Database SQLite (`extra.db`) beserta tabelnya akan dibuat secara otomatis saat aplikasi pertama kali dijalankan.

### 3. Akses Antarmuka Web & Dokumentasi API
* **Aplikasi Web ExTra:** http://127.0.0.1:8000
* **Swagger UI (OpenAPI Docs):** http://127.0.0.1:8000/docs
* **Health Check Endpoint:** http://127.0.0.1:8000/health

---

## Menjalankan dengan Docker

Pastikan [Docker Engine / Docker Desktop](https://docs.docker.com/get-docker/) telah terpasang dan file `.env` di root proyek sudah terisi `GEMINI_API_KEY` yang valid.

1. **Build image & jalankan container:**
   ```bash
   docker compose up --build
   ```
   *(Tambahkan `-d` jika ingin menjalankan di latar belakang: `docker compose up --build -d`)*
2. **Akses aplikasi:** Buka http://127.0.0.1:8000 di browser (endpoint status: http://127.0.0.1:8000/health).
3. **Persistensi data:** Docker Compose menjalankan service PostgreSQL (`postgres:16-alpine`) dengan volume persisten `postgres_data` untuk database serta bind mount `./uploads/` (`/app/uploads`) untuk arsip foto struk, sehingga data tetap aman meskipun container dihentikan atau dibangun ulang (`docker compose down && docker compose up`). Untuk pengembangan lokal tanpa Docker, aplikasi otomatis menggunakan SQLite (`extra.db`) apabila `DATABASE_URL` dikosongkan.
4. **Hentikan container:**
   ```bash
   docker compose down
   ```

---

## Menjalankan Suite Pengujian (`pytest`)

Seluruh unit test dan integration test menggunakan database SQLite sementara yang terisolasi (`tmp_path`) serta *mocking* pada layanan AI, sehingga aman dijalankan kapan saja tanpa mengubah `extra.db` maupun memotong kuota Gemini API.

**Windows (PowerShell):**
```powershell
.\venv\Scripts\pytest.exe -v
```

**macOS / Linux (atau dengan venv aktif):**
```bash
pytest -v
```

---

### Status Milestone Rilis
* **v1.0.0 (MVP):** Ekstraksi struk Gemini Vision, validasi Pydantic 2 tahap, tabel preview *human-in-the-loop*, CRUD SQLite, dan ringkasan bulanan deterministik.
* **v1.1.0 (Gelombang 1):** Kompresi `Pillow`, auto-retry/fallback model AI, 7 kategori pengeluaran, input manual, arsip foto struk lokal, dan ekspor CSV.
* **v1.5.0 (Gelombang 2):** Modernisasi frontend ke React + TypeScript + Vite + Tailwind CSS + Recharts (`frontend-v2/`).
* **v2.0.0 (Gelombang 3 — Selesai):** Docker + GitHub Actions CI, autentikasi multi-user (`bcrypt` + JWT), dual-mode SQLAlchemy (SQLite + PostgreSQL), pemasukan, budgeting per kategori, dan AI Financial Insights terpisah.
