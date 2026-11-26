# AGENTS.md — Panduan Kerja & Aturan Wajib AI Coding Assistant (ExTra)

Dokumen ini adalah aturan operasional wajib bagi AI coding assistant selama mengembangkan **ExTra (Expense Tracker)**. Rujukan spesifikasi produk tunggal (*Single Source of Truth*) adalah `PRD.md` (v2.0).

---

## 1. Status & Konteks Proyek

* **Baseline Selesai:** **MVP v1.0.0** sudah selesai, terverifikasi penuh, dan telah di-push ke GitHub. Jangan menghapus atau merusak fungsionalitas inti yang sudah berjalan pada `v1.0.0`.
* **Mode Pengembangan Saat Ini:** Ekspansi pasca-MVP yang dibagi secara ketat ke dalam **3 Gelombang** (lihat Section 7).
* **Alur Inti (*Human-in-the-Loop*) Tetap Wajib:**
  1. Ekstraksi AI dari foto struk (`JPG`/`JPEG`/`PNG`) wajib melalui validasi **Pydantic** dan ditampilkan di tabel *preview* agar pengguna memeriksa/mengoreksi sebelum disimpan ke database.
  2. Penyimpanan transaksi hanya terjadi setelah pengguna melakukan konfirmasi eksplisit (baik dari hasil ekstraksi struk maupun dari form **Input Manual**).
  3. Seluruh perhitungan angka keuangan (total bulanan, subtotal kategori, sisa anggaran, arus kas) wajib 100% deterministik di backend Python/SQL.

---

## 2. Batasan Ruang Lingkup & Aturan Perubahan Stack

### Diperbolehkan Sesuai Jadwal Gelombang
* **Gelombang 1 (v1.0.1 – v1.1):**
  * Kompresi & resize gambar menggunakan `Pillow` sebelum dikirim ke Gemini API.
  * Mekanisme *auto-retry* (*exponential backoff*) dan `GEMINI_FALLBACK_MODEL` di `ai_service.py`.
  * Penambahan atribut `category` (dari daftar enum kategori tetap) pada item transaksi dan prompt ekstraksi.
  * Fitur **Input Manual** tanpa foto struk menggunakan `POST /api/transactions`.
  * Fitur **Ekspor CSV** dan penyimpanan arsip foto struk terkompresi di folder lokal terkelola (`uploads/receipts/`).
* **Gelombang 2 (v1.5 — Migrasi Frontend):**
  * Menggunakan **React + Vite + Tailwind CSS** untuk membangun ulang antarmuka modern.
  * Selama proses migrasi berlangsung, bangun aplikasi baru di folder terpisah (`frontend-v2/`) agar folder `frontend/` lama yang sudah stabil tidak rusak di tengah jalan.
* **Gelombang 3 (v1.2 – v2.0 — Deployment & Skala Penuh):**
  * Pembuatan `Dockerfile`, `docker-compose.yml`, dan workflow GitHub Actions CI.
  * Sistem autentikasi multi-user (`users`, hashing password, JWT/cookie aman) dan isolasi data per `user_id`.
  * Abstraksi database agar mendukung **SQLite** (lokal) maupun **PostgreSQL** (`DATABASE_URL`, produksi).
  * Pencatatan pemasukan (`incomes`), anggaran bulanan (`budgets`), dan layanan terpisah `insights_service.py`.

### Tetap DILARANG Keras (Seluruh Gelombang)
* **DILARANG** mengekstrak atau menyimpan kolom nama toko (*merchant*/*store*), alamat toko, nomor telepon, nomor struk, kasir, atau metode pembayaran.
* **DILARANG** menambahkan integrasi langsung ke rekening bank, mutasi e-wallet, atau open banking API.
* **DILARANG** meminta LLM menghitung total pengeluaran, rata-rata harian, atau sisa anggaran.
* **DILARANG** melompat mengerjakan fitur dari Gelombang 2 atau Gelombang 3 saat sedang mengerjakan milestone di Gelombang 1.

---

## 3. Tech Stack & Struktur Direktori Target

* **Backend:** Python 3.10+, FastAPI, Uvicorn, Pydantic v2, `Pillow`, `google-genai`, `python-dotenv`, `python-multipart`, `pytest`.
* **Database:** SQLite (`sqlite3`) sebagai default lokal; dukungan PostgreSQL (`DATABASE_URL`) ditambahkan pada Gelombang 3.
* **Frontend:**
  * *Gelombang 1:* Pertahankan `frontend/` (HTML5, CSS3, Vanilla JS) untuk menguji API v1.0.1 & v1.1 dengan cepat.
  * *Gelombang 2 & 3:* **React + Vite + Tailwind CSS** di `frontend-v2/` (kemudian hasil build disajikan oleh FastAPI/reverse proxy).

```text
ExTra/
├── .env                         # Lokal only, DILARANG commit ke Git
├── .env.example                 # Template variabel environment
├── .gitignore                   # Abaikan .env, venv/, *.db, uploads/, node_modules/, dist/
├── Dockerfile                   # (Gelombang 3)
├── docker-compose.yml           # (Gelombang 3)
├── requirements.txt
├── PRD.md
├── AGENTS.md
├── README.md
├── uploads/                     # Arsip foto struk terkompresi (v1.1+, diabaikan Git)
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── schemas/
│   │   ├── receipt.py
│   │   ├── transaction.py
│   │   ├── summary.py
│   │   ├── auth.py              # (Gelombang 3)
│   │   └── budget.py            # (Gelombang 3)
│   ├── services/
│   │   ├── image_service.py     # Kompresi gambar Pillow (v1.0.1)
│   │   ├── ai_service.py        # Gemini Vision + retry/backoff + fallback (v1.0.1)
│   │   ├── prompts.py           # Prompt ekstraksi & prompt insights terpisah
│   │   ├── transaction_service.py
│   │   ├── summary_service.py
│   │   ├── export_service.py    # Ekspor CSV (v1.1)
│   │   ├── auth_service.py      # (Gelombang 3)
│   │   └── insights_service.py  # (Gelombang 3)
│   └── routers/
│       ├── receipts.py
│       ├── transactions.py
│       ├── summary.py
│       ├── auth.py              # (Gelombang 3)
│       └── budgets.py           # (Gelombang 3)
├── frontend/                    # UI Vanilla v1.0–v1.1
├── frontend-v2/                 # UI React + Vite + Tailwind CSS (Gelombang 2)
└── tests/
```

---

## 4. Pemisahan Tanggung Jawab (Separation of Concerns)

1. **Image & AI Extraction Layer (`image_service.py`, `prompts.py`, `ai_service.py`):**
   * `image_service.py` memvalidasi MIME/magic bytes dan mengompresi gambar dengan `Pillow` sebelum dikirim ke Gemini.
   * `ai_service.py` memanggil Gemini Flash (`google-genai`) dengan `response_mime_type="application/json"`, `response_schema`, timeout **30 detik**, serta *retry* dengan *exponential backoff* + `GEMINI_FALLBACK_MODEL` untuk error sementara (`429`/`503`).
   * **DILARANG** menulis langsung ke database atau melakukan perhitungan keuangan di layer ini.

2. **AI Financial Insights Layer (`insights_service.py` — Gelombang 3):**
   * Modul terpisah dari `ai_service.py`. Hanya menerima objek ringkasan statistik yang **sudah dihitung** oleh `summary_service.py` (total kategori, tren bulanan, status anggaran) untuk menghasilkan narasi saran keuangan.
   * **DILARANG** membaca baris transaksi mentah atau menghitung angka di dalam prompt/LLM.

3. **Validation Layer (`backend/schemas/`):**
   * Validasi Pydantic dua tahap tetap wajib: skema ekstraksi (toleran `date: null`, menormalisasi kategori tak dikenal ke `"Lainnya"`) dan skema penyimpanan (ketat: tanggal `YYYY-MM-DD` valid, `items` minimal 1, `name` non-kosong, `price` integer `>= 0`, `category` valid).

4. **Backend & Database Layer (`routers/`, `services/`, `database.py`):**
   * Menangani seluruh CRUD, pencarian, filter periode & kategori, ekspor CSV, serving aman arsip foto struk, autentikasi (Gelombang 3), dan seluruh kalkulasi ringkasan/anggaran secara deterministik.

5. **Frontend Layer (`frontend/` di Gelombang 1; `frontend-v2/` di Gelombang 2+):**
   * Hanya menangani UI, validasi form sisi klien, dan komunikasi ke endpoint `/api/*`.
   * Tidak boleh menyimpan API key eksternal atau memanggil Gemini API langsung.

---

## 5. Aturan Database & Migrasi Aman

* **Integritas Relasional:** Wajib mengeksekusi `PRAGMA foreign_keys = ON;` pada setiap koneksi SQLite, mempertahankan `ON DELETE CASCADE` pada `transaction_items`, dan melakukan *orphan cleanup* jika seluruh item pada transaksi dihapus.
* **Migrasi Backward-Compatible (v1.1):**
  * Penambahan kolom `receipt_image_path` pada `transactions` dan `category` (`DEFAULT 'Lainnya'`) pada `transaction_items` harus ditangani dengan aman saat `init_db()` berjalan sehingga file `extra.db` lama dari v1.0.0 tetap dapat dibaca tanpa error.
* **Isolasi Multi-User (Gelombang 3):**
  * Setelah fitur autentikasi aktif, setiap query `SELECT`, `UPDATE`, `DELETE`, ringkasan, dan akses file struk wajib memfilter berdasarkan `user_id` milik pengguna yang sedang login.

---

## 6. Aturan Keamanan

* Seluruh konfigurasi sensitif (`GEMINI_API_KEY`, `JWT_SECRET`, `DATABASE_URL`) wajib dimuat dari `.env` melalui `backend/config.py` dan **dilarang** di-hardcode atau di-commit ke Git.
* **Keamanan Arsip File Struk (v1.1+):**
  * Simpan file arsip dengan nama acak aman (misal UUID) di dalam direktori khusus `uploads/receipts/`, jangan pernah memakai nama file asli dari user secara langsung.
  * Endpoint akses foto struk wajib mencegah *path traversal* dan memverifikasi kepemilikan transaksi sebelum mengirim file.
* **Keamanan Autentikasi (Gelombang 3):**
  * Simpan password hanya dalam bentuk hash kuat (`bcrypt` atau `argon2`), gunakan token/cookie yang aman, dan jangan pernah mengembalikan `password_hash` di response API mana pun.

---

## 7. Workflow Eksekusi Bertahap (Wave & Milestone Discipline)

Seluruh pengembangan pasca-MVP mengikuti urutan berikut:
* **Gelombang 1 (Backend & AI):**
  * `M1.1`: AI Hardening (`image_service.py` kompresi Pillow, retry/backoff, fallback model).
  * `M1.2`: Kategori item & Input Manual tanpa struk.
  * `M1.3`: Ekspor laporan CSV & arsip foto struk lokal.
* **Gelombang 2 (Frontend Modernization):**
  * `M2.1`: Setup `frontend-v2/` (React + Vite + Tailwind CSS), API client, Upload/Preview & Input Manual.
  * `M2.2`: Halaman Riwayat, Ringkasan + grafik modern, lalu cutover build ke FastAPI.
* **Gelombang 3 (Deployment & Full Scale):**
  * `M3.1`: Docker (`Dockerfile`, `docker-compose.yml`) & GitHub Actions CI.
  * `M3.2`: Autentikasi Multi-User & dukungan PostgreSQL (`DATABASE_URL`).
  * `M3.3`: Pencatatan pemasukan, Budgeting per kategori, dan `insights_service.py`.

**Aturan Eksekusi Wajib:**
1. Kerjakan **HANYA satu sub-milestone pada satu waktu** sesuai instruksi pengguna.
2. **DILARANG** mencampur perubahan fitur backend baru dengan migrasi framework React dalam satu langkah yang sama.
3. Setiap kali menyelesaikan satu sub-milestone:
   * Jalankan `pytest -v` (dan `npm run build` apabila menyentuh `frontend-v2/`) untuk memastikan seluruh tes lama dan baru lulus.
   * Tampilkan ringkasan file yang dibuat/diubah, perilaku baru yang diimplementasikan, serta hasil pengujian sebelum melanjutkan ke tahap berikutnya.