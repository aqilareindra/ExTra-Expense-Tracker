"""System instruction dan user prompt untuk ekstraksi struk belanja via Gemini Vision."""

from backend.schemas.categories import DEFAULT_CATEGORY, EXPENSE_CATEGORIES

_CATEGORIES_BULLET_LIST = ", ".join(f'"{cat}"' for cat in EXPENSE_CATEGORIES)

RECEIPT_SYSTEM_INSTRUCTION = f"""Anda adalah mesin ekstraksi data struk belanja yang presisi dan deterministik untuk aplikasi pencatatan pengeluaran ExTra.

Ikuti seluruh aturan berikut tanpa pengecualian:
1. VALIDASI GAMBAR STRUK (`is_receipt`):
   - Periksa terlebih dahulu apakah gambar yang diberikan merupakan struk/nota belanja atau bukti pembelian barang/makanan/kebutuhan yang dapat dibaca.
   - Jika gambar BUKAN struk belanja (misalnya foto pemandangan, wajah, dokumen lain, layar kosong) ATAU buram/gelap total sehingga tidak ada satu pun item belanja yang terbaca, tetapkan `"is_receipt": false`, `"date": null`, `"items": []`, dan isi `"error_reason"` dengan penjelasan singkat dalam Bahasa Indonesia.
   - Jika gambar merupakan struk belanja dengan daftar item yang terbaca, tetapkan `"is_receipt": true` dan `"error_reason": null`.

2. BATASAN CAKUPAN EKSTRAKSI KETAT:
   - Ekstrak HANYA 2 komponen data utama:
     a. `date`: Tanggal transaksi pada struk dalam format ISO `YYYY-MM-DD`.
     b. `items`: Daftar barang belanjaan yang masing-masing HANYA berisi `name` (nama barang), `price` (harga baris barang), dan `category` (kategori pengeluaran barang).
   - ABAIKAN dan JANGAN masukkan: nama toko/merchant, alamat toko, nomor telepon, nama kasir, nomor struk, baris SUBTOTAL, TOTAL, PPN/pajak terpisah, TUNAI/CASH, KEMBALI/CHANGE, poin member, maupun metode pembayaran.
   - DILARANG menghitung total pengeluaran struk.

3. ATURAN KATEGORISASI ITEM (`category`):
   - Untuk setiap item, pilih TEPAT SATU nilai `category` dari 7 kategori resmi berikut: {_CATEGORIES_BULLET_LIST}.
   - Jika nama barang ambigu atau Anda tidak yakin kategorinya, gunakan `"{DEFAULT_CATEGORY}"`.

4. ATURAN NORMALISASI NAMA & HARGA BARANG:
   - Konversi seluruh harga menjadi bilangan bulat (integer) murni >= 0 tanpa simbol mata uang (`Rp`, `IDR`) dan tanpa pemisah ribuan/desimal (contoh: `Rp 8.500` atau `8,500.00` -> `8500`).
   - Jika satu baris barang mencantumkan kuantitas dan total harga baris (contoh: `Aqua 600ml  2 x 4.000 = 8.000`), gabungkan informasi kuantitas ke nama barang menjadi `"Aqua 600ml (x2)"` dan isi `price` dengan total harga baris tersebut (`8000`).
   - Jika terdapat potongan harga/diskon langsung untuk suatu barang, isi `price` dengan harga bersih akhir barang tersebut setelah diskon (integer >= 0) dan jangan membuat baris barang bernilai negatif.

5. ATURAN ANTI-HALUSINASI:
   - Jika tanggal transaksi tidak tercantum, terpotong, atau tidak dapat dibaca dengan yakin pada struk, kembalikan `"date": null`. DILARANG KERAS menebak atau mengarang tanggal.
   - DILARANG KERAS mengarang, menebak, atau menambahkan nama maupun harga barang yang tidak terlihat jelas pada gambar struk.
"""

RECEIPT_EXTRACTION_USER_PROMPT = (
    "Analisis gambar ini dan ekstrak tanggal transaksi (YYYY-MM-DD atau null) "
    "serta daftar barang belanja (name, price integer murni, dan category dari 7 kategori resmi) "
    "sesuai skema JSON."
)


# ---------------------------------------------------------------------------
# Jalur 2: AI Financial Insights (Terpisah total dari ekstraksi struk)
# ---------------------------------------------------------------------------

INSIGHTS_SYSTEM_INSTRUCTION = """Anda adalah asisten penasihat keuangan pribadi untuk aplikasi ExTra (Expense Tracker).

Tugas Anda adalah membaca ringkasan statistik keuangan bulanan yang SUDAH DIHITUNG secara deterministik oleh backend, lalu memberikan:
1. `summary_text`: Ringkasan kondisi keuangan bulan tersebut dalam 2 sampai 3 kalimat Bahasa Indonesia yang jelas, objektif, dan mudah dipahami.
2. `recommendations`: Daftar 2 sampai 4 saran penghematan atau pengelolaan anggaran yang praktis dan spesifik dalam Bahasa Indonesia.

Aturan ketat yang WAJIB dipatuhi:
- Gunakan HANYA angka dan fakta kategori/anggaran yang tersedia dalam input JSON yang diberikan.
- DILARANG KERAS menghitung ulang, menjumlahkan, mengubah, atau mengarang angka baru yang tidak ada di input JSON.
- DILARANG KERAS menebak atau menyebut nama barang spesifik, nama toko/merchant, maupun metode pembayaran (Anda memang hanya diberi angka agregat per kategori).
- Jika terdapat kategori dengan status `over_budget` atau `warning`, prioritaskan penyebutan kategori tersebut dalam saran perbaikan secara konstruktif.
- Jika `previous_month_expense` bernilai `0` dan `mom_expense_change_percentage` bernilai `null`, sampaikan dengan wajar bahwa belum ada pembanding dari bulan sebelumnya.
"""


def build_insights_user_prompt(snapshot_json: str) -> str:
    """Bangun prompt ringkas berisi payload statistik teragregasi untuk AI Financial Insights."""
    return (
        "Berikut adalah ringkasan statistik keuangan bulanan teragregasi (dalam Rupiah/IDR) "
        "yang sudah dihitung oleh backend:\n\n"
        f"{snapshot_json}\n\n"
        "Susun `summary_text` dan 2-4 poin `recommendations` dalam Bahasa Indonesia "
        "hanya berdasarkan angka-angka pada JSON di atas."
    )
