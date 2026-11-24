# AGENTS.md — Panduan Kerja & Aturan Wajib AI Coding Assistant (ExTra)

Dokumen ini adalah aturan operasional wajib bagi AI coding assistant selama mengembangkan **ExTra (Expense Tracker)**. Rujukan spesifikasi produk tunggal (*Single Source of Truth*) adalah `PRD.md`.

---

## 1. Ringkasan Project & Tujuan MVP

* **Produk:** **ExTra (Expense Tracker)** — aplikasi web *AI-powered* untuk pencatatan dan pemantauan pengeluaran pribadi berbasis foto struk belanja (penggunaan tunggal/lokal, MVP v1.0).
* **Alur Inti (*Human-in-the-Loop*):**
  1. Pengguna mengunggah foto struk (`JPG`/`JPEG`/`PNG`, maks 5 MB).
  2. Backend mengirim gambar ke **Google Gemini Flash API** untuk mengekstrak `date`, `items[].name`, dan `items[].price`.
  3. Hasil ekstraksi divalidasi **Pydantic**, lalu ditampilkan di tabel *preview* agar pengguna memeriksa/mengedit sebelum disimpan.
  4. Penyimpanan ke **SQLite** hanya terjadi setelah pengguna menekan **Konfirmasi & Simpan**.
  5. Halaman **Riwayat Transaksi** dan **Ringkasan Bulanan** menampilkan data tersimpan dengan kalkulasi 100% deterministik di backend Python/SQL.
* **Tujuan MVP:** Memangkas waktu input (< 30 detik untuk 5–10 item), menjamin 100% data tersimpan lolos validasi skema & konfirmasi pengguna, menghilangkan halusinasi LLM pada kalkulasi angka, serta menjaga arsitektur modular yang bersih.

---

## 2. Batasan Ketat Ruang Lingkup (In-Scope & Out-of-Scope)

### In-Scope (Wajib Ada di MVP v1.0)
* Upload foto struk (`JPG`, `JPEG`, `PNG`, maksimal **5 MB**) dengan indikator loading & pencegahan double-submit.
* Ekstraksi AI terbatas **hanya** pada 3 informasi: tanggal transaksi (`date`), nama barang (`name`), dan harga barang (`price`).
* Validasi Pydantic dua tahap + tabel preview *editable* (edit nama/harga/tanggal, tambah/hapus baris) + konfirmasi simpan eksplisit.
* Riwayat transaksi: daftar item tersimpan (urut default tanggal terbaru), pencarian nama barang (*case-insensitive substring*), filter bulan & tahun, edit item/tanggal, hapus item/transaksi (dengan konfirmasi & *orphan cleanup*).
* Ringkasan bulanan: filter bulan & tahun (default bulan/tahun berjalan), total pengeluaran, jumlah barang tercatat, daftar pengeluaran per tanggal, dan 1 grafik sederhana (Canvas/SVG atau Chart.js via CDN).
* Navigasi maksimal **3 halaman/tab utama**: Upload & Preview, Riwayat, Ringkasan Bulanan.

### Out-of-Scope (DILARANG Keras Ditambahkan)
* **TANPA** autentikasi, login, registrasi, multi-user, sesi, atau JWT.
* **TANPA** kolom atau ekstraksi nama toko (*merchant*/*store*), alamat, telepon, nomor struk, kasir, metode pembayaran, pajak terpisah, subtotal, atau kembalian.
* **TANPA** kategorisasi pengeluaran otomatis maupun manual.
* **TANPA** pencatatan pemasukan (*income tracking*), manajemen saldo, budgeting, rekomendasi finansial AI, arsip file foto struk permanen di disk, ekspor CSV/Excel, atau integrasi bank/e-wallet/Google Sheets.
* **TANPA** framework frontend tambahan (DILARANG memakai React, Vue, Next.js, Angular, Svelte, Tailwind CSS, Bootstrap, atau bundler JS seperti Vite/Webpack).
* **TANPA** penambahan fitur, endpoint, atau library di luar `PRD.md` tanpa instruksi eksplisit pengguna.

---

## 3. Tech Stack & Struktur Direktori Modular

### Tech Stack Wajib (Sesuai Section 11 `PRD.md`)
* **Backend:** Python 3.10+, FastAPI, Uvicorn (sekaligus menyajikan *static files* frontend)
* **AI Layer:** Google Gemini Flash API via SDK resmi `google-genai`
* **Validasi Skema:** Pydantic v2
* **Database:** SQLite (`sqlite3` standar Python)
* **Frontend:** HTML5, CSS3, Vanilla JavaScript (opsional Canvas/SVG atau Chart.js CDN untuk grafik ringkasan)
* **Konfigurasi & Dependensi:** `python-dotenv`; daftar paket di `requirements.txt` mengacu pada `fastapi`, `uvicorn`, `google-genai`, `pydantic`, `python-dotenv`, `python-multipart`, `pytest`

### Struktur Direktori Target
```text
ExTra/
├── .env                         # Lokal only, DILARANG commit ke Git
├── .env.example                 # Template variabel environment (GEMINI_API_KEY)
├── .gitignore                   # Abaikan .env, __pycache__/, *.db, venv/
├── requirements.txt             # Dependensi minimal proyek
├── PRD.md                       # Single Source of Truth spesifikasi produk
├── AGENTS.md                    # Panduan kerja & aturan wajib AI assistant
├── README.md                    # Dokumentasi akhir (dibuat di Milestone 6)
├── backend/
│   ├── main.py                  # Entry point FastAPI, mount static files & routers
│   ├── config.py                # Load & validasi konfigurasi dari .env
│   ├── database.py              # Koneksi SQLite, PRAGMA foreign_keys, inisialisasi tabel
│   ├── schemas/
│   │   ├── receipt.py           # Skema Pydantic hasil ekstraksi AI (tahap preview)
│   │   ├── transaction.py       # Skema Pydantic create/update/response transaksi
│   │   └── summary.py           # Skema Pydantic ringkasan bulanan
│   ├── services/
│   │   ├── ai_service.py        # Pemanggilan Gemini Vision API & error handling
│   │   ├── prompts.py           # System instruction & prompt ekstraksi struk
│   │   ├── transaction_service.py # Logika CRUD SQLite & filter pencarian
│   │   └── summary_service.py   # Kalkulasi total bulanan, jumlah item, agregasi harian
│   └── routers/
│       ├── receipts.py          # Endpoint ekstraksi struk
│       ├── transactions.py      # Endpoint CRUD & riwayat transaksi
│       └── summary.py           # Endpoint ringkasan bulanan
├── frontend/
│   ├── index.html               # Halaman UI utama (Upload/Preview, History, Summary)
│   ├── css/
│   │   └── styles.css           # Styling bersih & responsif (desktop/mobile)
│   └── js/
│       ├── api.js               # Wrapper fetch API terpusat
│       ├── upload.js            # Logika upload, loading state, & tabel preview editable
│       ├── history.js           # Logika riwayat, search, filter, edit, delete
│       └── summary.js           # Logika metrik bulanan & render grafik sederhana
└── tests/
    ├── test_schemas.py          # Unit test validasi Pydantic
    ├── test_database.py         # Unit test CRUD & foreign key cascade
    ├── test_summary.py          # Unit test akurasi perhitungan bulanan
    └── test_api.py              # Integration test endpoint FastAPI (mock ai_service)
```

---

## 4. Pemisahan Tanggung Jawab (Separation of Concerns)

1. **AI Layer (`prompts.py`, `ai_service.py`):**
   * Hanya bertugas mengonversi *inline image bytes* (+ MIME type) foto struk menjadi JSON terstruktur via Gemini Flash (`google-genai`) dengan `response_mime_type="application/json"`, `response_schema`, dan timeout backend **30 detik**.
   * Prompt wajib berada di `prompts.py`, mengecek `is_receipt`, melarang ekstraksi data toko/pembayaran, melarang mengarang barang, menormalisasi harga ke integer murni, dan mengembalikan `date: null` jika tanggal tidak terbaca.
   * **DILARANG** menghitung total bulanan, agregasi harian, atau logika analitik keuangan apa pun.
   * **DILARANG** menulis langsung ke database SQLite atau memanggil service database.
   * Wajib menangkap error eksternal/format dan memetakannya ke HTTP/domain error (`422 NOT_A_RECEIPT`, `422 UNREADABLE_RECEIPT`, `502 AI_PARSE_ERROR`, `503`/`429 AI_SERVICE_UNAVAILABLE`).

2. **Validasi Pydantic Dua Tahap (`backend/schemas/`):**
   * **Tahap 1 — Extraction Schema (`ReceiptExtractionResult` di `receipt.py`):** Memvalidasi output mentah Gemini untuk preview. Toleran terhadap `date: null` (memicu `warnings` pada payload preview agar UI menyorot field tanggal).
   * **Tahap 2 — Persistence Schema (`TransactionCreateRequest` & skema tulis di `transaction.py`):** Validasi ketat sebelum masuk SQLite. Wajib mewajibkan `date` valid (`YYYY-MM-DD`), `items` minimal 1 item, `name` non-kosong setelah trim whitespace, dan `price` integer `>= 0`.

3. **Backend FastAPI + SQLite (`routers/`, `transaction_service.py`, `summary_service.py`, `database.py`):**
   * Memvalidasi ulang tipe MIME/konten & ukuran file upload (`<= 5 MB`; tolak dengan `400 INVALID_FILE_TYPE` / `413 FILE_TOO_LARGE`).
   * `POST /api/receipts/extract` **tidak boleh** menyimpan ke DB.
   * Menangani seluruh CRUD, pencarian substring nama barang, filter bulan/tahun, serta menghitung **total pengeluaran bulanan**, **jumlah barang**, dan **breakdown harian** secara deterministik via Python/SQL.

4. **Frontend (`frontend/`):**
   * Hanya menangani rendering UI, validasi ringan sisi klien (ekstensi/ukuran file, field kosong/harga negatif), status loading + disable tombol saat request berjalan, tabel preview *editable*, dan pemanggilan REST API terpusat melalui `api.js`.
   * Tidak boleh memanggil Gemini API langsung atau menyimpan logika bisnis/agregasi database.

---

## 5. Aturan Database & Kontrak Data

* **Hanya 2 Tabel (Tanpa Kolom Nama Toko):**
  1. `transactions`:
     * `id` `INTEGER PRIMARY KEY AUTOINCREMENT`
     * `transaction_date` `TEXT NOT NULL` (format wajib `YYYY-MM-DD`)
     * `created_at` `TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
  2. `transaction_items`:
     * `id` `INTEGER PRIMARY KEY AUTOINCREMENT`
     * `transaction_id` `INTEGER NOT NULL` (`FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE`)
     * `item_name` `TEXT NOT NULL CHECK (length(trim(item_name)) > 0)`
     * `price` `INTEGER NOT NULL CHECK (price >= 0)`
* **Integritas Relasional:**
  * Wajib menjalankan `PRAGMA foreign_keys = ON;` pada **setiap** koneksi SQLite.
  * **Cascade Delete:** Menghapus transaksi di `transactions` otomatis menghapus seluruh item terkait.
  * **Orphan Cleanup:** Menghapus item terakhir dari sebuah transaksi wajib menghapus baris header terkait di `transactions`.
* **Kontrak Endpoint & Format Data:**
  * Endpoint wajib sesuai Section 13 `PRD.md`: `POST /api/receipts/extract`, `POST /api/transactions`, `GET /api/transactions`, `PUT /api/items/{item_id}`, `DELETE /api/items/{item_id}`, `DELETE /api/transactions/{transaction_id}`, `GET /api/summary/monthly` (ditambah `GET /health` pada Milestone 1).
  * Tanggal selalu string ISO `YYYY-MM-DD`; harga selalu integer `>= 0` (IDR tanpa pemisah ribuan/simbol).
  * **Human-in-the-Loop:** Data hasil AI dilarang disimpan otomatis; wajib melalui review/edit pengguna dan konfirmasi eksplisit ke `POST /api/transactions`.

---

## 6. Aturan Keamanan

* `GEMINI_API_KEY` **wajib** dimuat dari file `.env` di sisi server melalui `python-dotenv` (`backend/config.py`).
* **DILARANG** melakukan *hardcode* API key di file kode, test, skrip, atau dokumentasi mana pun.
* File `.env` **wajib** tercantum di `.gitignore` dan **tidak boleh** di-commit ke Git (gunakan `.env.example` tanpa nilai rahasia sebagai template).
* `GEMINI_API_KEY` dan stack trace internal **tidak boleh** terekspos ke frontend maupun payload error HTTP (kredensial hilang/invalid dicatat di log server dan dikembalikan sebagai `500 CONFIGURATION_ERROR` generik).
* Validasi upload wajib memeriksa tipe konten/MIME (`image/jpeg`, `image/png`) dan batas 5 MB di backend, serta tidak menyimpan gambar struk mentah secara permanen ke disk.

---

## 7. Aturan Workflow Pengembangan Bertahap

Pengembangan mengikuti roadmap 6 milestone pada Section 17 `PRD.md`:
1. **Milestone 1:** Setup Project & Gemini API (`requirements.txt`, `.env.example`, `.gitignore`, `config.py`, FastAPI `/health`, tes koneksi Gemini)
2. **Milestone 2:** Database Layer & Core CRUD (`database.py`, Pydantic schemas, `transaction_service.py`, `transactions.py` router, unit & integration tests)
3. **Milestone 3:** AI Processing Layer (`prompts.py`, `ai_service.py`, `receipts.py` router)
4. **Milestone 4:** Monthly Summary Backend (`summary_service.py`, `summary.py` router)
5. **Milestone 5:** Frontend UI Integration (`index.html`, `styles.css`, `api.js`, `upload.js`, `history.js`, `summary.js`)
6. **Milestone 6:** Testing & Hardening (full `pytest` suite, evaluasi edge cases, `README.md`, verifikasi AC-01 s/d AC-06)

**Aturan Eksekusi Wajib:**
* Kerjakan **HANYA satu milestone pada satu waktu** sesuai instruksi pengguna.
* **DILARANG** membuat file, folder, atau menulis kode untuk milestone berikutnya sebelum milestone aktif selesai dan pengguna memberi arahan lanjut.
* Setiap kali menyelesaikan tugas pada suatu milestone: jalankan verifikasi/tes terkait yang relevan, lalu **jelaskan dengan ringkas seluruh file yang dibuat/diubah, perilaku yang diimplementasikan, serta hasil pengujian** sebelum melanjutkan ke tahap berikutnya.
* Jika ditemukan ambiguitas atau konflik terhadap `PRD.md`, hentikan implementasi dan konfirmasi ke pengguna terlebih dahulu.
