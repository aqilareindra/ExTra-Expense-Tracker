"""Definisi terpusat (Single Source of Truth) kategori pengeluaran ExTra (FR-24)."""

from typing import Literal, get_args

ExpenseCategory = Literal[
    "Makanan & Minuman",
    "Kebutuhan Pokok",
    "Transportasi",
    "Kesehatan & Perawatan",
    "Tagihan & Utilitas",
    "Hiburan & Belanja",
    "Lainnya",
]

EXPENSE_CATEGORIES: tuple[str, ...] = get_args(ExpenseCategory)
VALID_CATEGORY_SET: frozenset[str] = frozenset(EXPENSE_CATEGORIES)
DEFAULT_CATEGORY: ExpenseCategory = "Lainnya"


def normalize_category_lenient(value: object) -> str:
    """Tahap 1 (Ekstraksi AI): normalisasi kategori di luar daftar resmi menjadi 'Lainnya'."""
    if not isinstance(value, str):
        return DEFAULT_CATEGORY
    trimmed = value.strip()
    if trimmed in VALID_CATEGORY_SET:
        return trimmed
    return DEFAULT_CATEGORY


def validate_strict_category(value: object) -> str:
    """Tahap 2 (Penyimpanan/Update): tolak kategori di luar 7 kategori resmi."""
    if not isinstance(value, str):
        raise ValueError("Kategori barang harus berupa string.")
    trimmed = value.strip()
    if trimmed not in VALID_CATEGORY_SET:
        allowed_str = ", ".join(EXPENSE_CATEGORIES)
        raise ValueError(
            f"Kategori tidak valid: '{trimmed}'. Pilih salah satu dari: {allowed_str}."
        )
    return trimmed
