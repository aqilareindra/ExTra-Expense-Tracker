"""Skema Pydantic v2 untuk validasi penyimpanan dan respons transaksi."""

from datetime import date as calendar_date
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.schemas.categories import (
    DEFAULT_CATEGORY,
    EXPENSE_CATEGORIES,
    ExpenseCategory,
    validate_strict_category,
)

_ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_non_empty_name(value: object) -> str:
    """Pastikan nama barang bertipe string, di-trim, dan tidak kosong."""
    if not isinstance(value, str):
        raise ValueError("Nama barang harus berupa string.")
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Nama barang tidak boleh kosong.")
    return trimmed


def validate_strict_non_negative_price(value: object) -> int:
    """Pastikan harga bertipe integer murni >= 0 (tolak bool, float, dan negatif)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Harga barang harus berupa bilangan bulat (integer).")
    if value < 0:
        raise ValueError("Harga barang tidak boleh bernilai negatif.")
    return value


def validate_iso_calendar_date(value: object) -> str:
    """Pastikan tanggal bertipe string ISO YYYY-MM-DD dan merupakan tanggal kalender nyata."""
    if not isinstance(value, str):
        raise ValueError("Tanggal transaksi harus berupa string berformat YYYY-MM-DD.")
    trimmed = value.strip()
    if not _ISO_DATE_REGEX.fullmatch(trimmed):
        raise ValueError("Format tanggal harus YYYY-MM-DD.")
    try:
        calendar_date.fromisoformat(trimmed)
    except ValueError as exc:
        raise ValueError(f"Tanggal kalender tidak valid: '{trimmed}'.") from exc
    return trimmed


class TransactionItemCreate(BaseModel):
    """Skema input satu item barang saat menyimpan transaksi."""

    model_config = ConfigDict(extra="forbid")

    name: str
    price: int
    category: str = DEFAULT_CATEGORY

    @field_validator("name", mode="before")
    @classmethod
    def _check_name(cls, value: object) -> str:
        return validate_non_empty_name(value)

    @field_validator("price", mode="before")
    @classmethod
    def _check_price(cls, value: object) -> int:
        return validate_strict_non_negative_price(value)

    @field_validator("category", mode="before")
    @classmethod
    def _check_category(cls, value: object) -> str:
        return validate_strict_category(value)


class TransactionCreateRequest(BaseModel):
    """Skema request penyimpanan transaksi baru ke SQLite."""

    model_config = ConfigDict(extra="forbid")

    date: str
    items: list[TransactionItemCreate] = Field(..., min_length=1)

    @field_validator("date", mode="before")
    @classmethod
    def _check_date(cls, value: object) -> str:
        return validate_iso_calendar_date(value)


class ItemUpdateRequest(BaseModel):
    """Skema request pembaruan item tersimpan (minimal satu field wajib diisi)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: int | None = None
    date: str | None = None
    category: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _check_optional_name(cls, value: object) -> str | None:
        if value is None:
            return None
        return validate_non_empty_name(value)

    @field_validator("price", mode="before")
    @classmethod
    def _check_optional_price(cls, value: object) -> int | None:
        if value is None:
            return None
        return validate_strict_non_negative_price(value)

    @field_validator("date", mode="before")
    @classmethod
    def _check_optional_date(cls, value: object) -> str | None:
        if value is None:
            return None
        return validate_iso_calendar_date(value)

    @field_validator("category", mode="before")
    @classmethod
    def _check_optional_category(cls, value: object) -> str | None:
        if value is None:
            return None
        return validate_strict_category(value)

    @model_validator(mode="after")
    def _check_at_least_one_field(self) -> "ItemUpdateRequest":
        if (
            self.name is None
            and self.price is None
            and self.date is None
            and self.category is None
        ):
            raise ValueError(
                "Minimal satu field (name, price, date, atau category) harus diisi."
            )
        return self


class TransactionItemRecord(BaseModel):
    """Representasi item transaksi hasil join tabel transactions & transaction_items."""

    id: int
    transaction_id: int
    date: str
    name: str
    category: str = DEFAULT_CATEGORY
    price: int
    created_at: str


class TransactionCreatedData(BaseModel):
    """Payload detail transaksi yang baru disimpan."""

    transaction_id: int
    date: str
    created_at: str
    items: list[TransactionItemRecord]


class TransactionCreateResponse(BaseModel):
    """Respons sukses untuk POST /api/transactions."""

    status: Literal["success"] = "success"
    data: TransactionCreatedData


class TransactionListResponse(BaseModel):
    """Respons sukses untuk GET /api/transactions."""

    status: Literal["success"] = "success"
    count: int
    data: list[TransactionItemRecord]


class ItemUpdateResponse(BaseModel):
    """Respons sukses untuk PUT /api/items/{item_id}."""

    status: Literal["success"] = "success"
    data: TransactionItemRecord


class ItemDeleteResponse(BaseModel):
    """Respons sukses untuk DELETE /api/items/{item_id}."""

    status: Literal["success"] = "success"
    message: str
    deleted_item_id: int
    orphan_transaction_deleted: bool


class TransactionDeleteResponse(BaseModel):
    """Respons sukses untuk DELETE /api/transactions/{transaction_id}."""

    status: Literal["success"] = "success"
    message: str
    deleted_transaction_id: int


class ValidationErrorDetail(BaseModel):
    """Detail field bermasalah ketika terjadi error validasi request."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """Format standar respons error JSON di seluruh endpoint API."""

    status: Literal["error"] = "error"
    error_code: str
    message: str
    details: list[ValidationErrorDetail] | None = None
