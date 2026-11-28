"""Layanan ekspor riwayat transaksi ExTra ke format CSV (UTF-8 with BOM)."""

import csv
import io
from pathlib import Path

from backend.services import transaction_service

CSV_HEADERS: tuple[str, str, str, str] = (
    "Tanggal",
    "Nama Barang",
    "Kategori",
    "Harga",
)


def build_export_filename(
    month: int | None = None,
    year: int | None = None,
) -> str:
    """Bangun nama file CSV unduhan sesuai filter periode aktif."""
    if year is not None and month is not None:
        return f"extra-pengeluaran-{year:04d}-{month:02d}.csv"
    if year is not None:
        return f"extra-pengeluaran-{year:04d}.csv"
    if month is not None:
        return f"extra-pengeluaran-bulan-{month:02d}.csv"
    return "extra-pengeluaran-semua.csv"


def generate_transactions_csv(
    user_id: int,
    month: int | None = None,
    year: int | None = None,
    category: str | None = None,
    search: str | None = None,
    db_path: str | Path | None = None,
) -> bytes:
    """Hasilkan file CSV UTF-8 with BOM berisi transaksi terfilter milik user_id."""
    items = transaction_service.get_transactions(
        user_id=user_id,
        month=month,
        year=year,
        category=category,
        search=search,
        db_path=db_path,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    for item in items:
        writer.writerow([item.date, item.name, item.category, item.price])

    return buffer.getvalue().encode("utf-8-sig")
