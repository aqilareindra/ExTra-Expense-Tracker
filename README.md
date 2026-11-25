# ExTra (Expense Tracker)

**ExTra** adalah aplikasi web pencatatan dan pemantauan pengeluaran pribadi berbasis foto struk belanja yang memanfaatkan **Google Gemini Flash Vision API** dengan pendekatan ***Human-in-the-Loop***.

Pengguna cukup mengunggah foto struk belanja (`JPG`, `JPEG`, atau `PNG`), memeriksa dan mengedit hasil pembacaan AI pada tabel pratinjau interaktif, lalu menyimpan data yang telah tervalidasi ke database lokal **SQLite**. Seluruh perhitungan riwayat dan ringkasan pengeluaran bulanan dijalankan 100% secara deterministik menggunakan Python dan SQL (tanpa kalkulasi LLM).

---

## Fitur Utama (MVP v1.0)

1. **Upload & Ekstraksi Struk Berbasis AI**
   - Mendukung *file picker* dan *drag-and-drop* untuk gambar `JPG`, `JPEG`, dan `PNG` (maksimal **5 MB**) beserta *thumbnail preview* dan indikator loading aktif.
   - Validasi berlapis di sisi klien dan backend (ukuran file, ekstensi, MIME type, dan *magic bytes* konten gambar).
   - Mengekstrak **hanya 3 informasi inti**: tanggal transaksi (`date`), nama barang (`name`), dan harga barang (`price`) melalui Structured Output Gemini Vision tanpa menyimpan foto struk ke disk.
2. **Validasi Dua Tahap & Tabel Preview Editable (*Human-in-the-Loop*)**
   - Validasi skema tahap 1 (`ReceiptExtractionResult`) untuk pratinjau — menyorot kolom tanggal disertai peringatan apabila tanggal pada struk tidak terbaca (`date: null`).
   - Pengguna bebas mengoreksi tanggal, mengedit nama/harga barang, menambah baris barang yang terlewat, atau menghapus baris sebelum menekan **Konfirmasi & Simpan**.
   - Validasi ketat tahap 2 (`TransactionCreateRequest`) sebelum penyimpanan ke SQLite (tanggal kalender ISO `YYYY-MM-DD` valid, minimal 1 item, nama tidak kosong, harga integer murni `>= 0`).
3. **Riwayat Transaksi Lengkap**
   - Menampilkan daftar barang tersimpan terurut dari tanggal terbaru (`DESC`).
   - Pencarian *case-insensitive substring* berdasarkan nama barang serta filter periode Bulan dan Tahun.
   - Edit item (`name`, `price`, `date`) dan hapus per item maupun hapus keseluruhan struk/transaksi dengan konfirmasi (*cascade delete* & *orphan cleanup* otomatis).
4. **Ringkasan Pengeluaran Bulanan & Grafik**
   - Kartu metrik **Total Pengeluaran Bulanan** dan **Jumlah Barang Tercatat** yang dihitung deterministik oleh SQLite + Python.
   - Grafik batang harian berbasis SVG murni (tanpa ketergantungan CDN eksternal, stabil saat offline) dan tabel rincian subtotal per tanggal.

---

## Tech Stack

| Layer | Teknologi |
| :--- | :--- |
| **Backend & Static Server** | Python 3.10+, FastAPI, Uvicorn |
| **Multimodal AI Layer** | Google Gemini Flash API via SDK resmi `google-genai` |
| **Validasi Data** | Pydantic v2 |
| **Database Lokal** | SQLite (`sqlite3` standar Python dengan `PRAGMA foreign_keys = ON`) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript, SVG Bar Chart |
| **Konfigurasi & Pengujian** | `python-dotenv`, `pytest`, FastAPI `TestClient` |

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

Buka file `.env` menggunakan teks editor dan isi `GEMINI_API_KEY` milik Anda:
```env
GEMINI_API_KEY=isi_dengan_gemini_api_key_anda
GEMINI_MODEL=gemini-3.5-flash-lite
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

## Batasan Ruang Lingkup MVP & Rencana Pengembangan

### Batasan MVP v1.0
Sesuai spesifikasi di [PRD.md](PRD.md), versi MVP v1.0 dirancang fokus untuk penggunaan personal lokal:
* Tanpa sistem registrasi, login, multi-user, atau autentikasi sesi/JWT.
* Ekstraksi struk dibatasi ketat hanya pada `date`, `items[].name`, dan `items[].price` (mengabaikan nama toko, alamat, kasir, metode pembayaran, pajak terpisah, dan kembalian).
* Tanpa kategorisasi pengeluaran, pencatatan pemasukan (*income tracking*), penyimpanan permanen foto struk di disk, maupun ekspor CSV/Excel.

### Rencana Pengembangan Berikutnya (*Future Improvements*)
* **Fase v1.1:** Kategorisasi belanja otomatis dengan koreksi manual, ekspor laporan bulanan ke CSV/Excel, dan opsi arsip foto struk.
* **Fase v2.0:** Autentikasi multi-user (JWT), pengaturan target anggaran bulanan (*budgeting* & pengingat batas pengeluaran), serta analitik tren pengeluaran lintas bulan.
