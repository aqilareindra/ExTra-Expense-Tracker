"""Skema Pydantic v2 tahap ekstraksi AI (preview) untuk struk belanja."""

from datetime import date as calendar_date
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from backend.schemas.categories import (
    DEFAULT_CATEGORY,
    normalize_category_lenient,
)

_ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ExtractedItem(BaseModel):
    """Representasi satu item belanja hasil ekstraksi Gemini Vision."""

    name: str
    price: int = Field(..., ge=0)
    category: str = Field(default=DEFAULT_CATEGORY)

    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Nama barang hasil ekstraksi harus berupa string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Nama barang hasil ekstraksi tidak boleh kosong.")
        return trimmed

    @field_validator("price", mode="before")
    @classmethod
    def _validate_price(cls, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Harga barang hasil ekstraksi harus berupa integer.")
        if value < 0:
            raise ValueError("Harga barang hasil ekstraksi tidak boleh negatif.")
        return value

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: object) -> str:
        return normalize_category_lenient(value)


class ReceiptExtractionResult(BaseModel):
    """Skema tahap 1 untuk memvalidasi output JSON terstruktur dari Gemini API."""

    is_receipt: bool
    date: Optional[str] = None
    items: list[ExtractedItem] = Field(default_factory=list)
    error_reason: Optional[str] = None

    @field_validator("date", mode="before")
    @classmethod
    def _normalize_date_lenient(cls, value: object) -> Optional[str]:
        """Simpan tanggal jika valid YYYY-MM-DD; ubah ke None jika kosong/tidak valid."""
        if value is None or not isinstance(value, str):
            return None
        trimmed = value.strip()
        if not trimmed or not _ISO_DATE_REGEX.fullmatch(trimmed):
            return None
        try:
            calendar_date.fromisoformat(trimmed)
        except ValueError:
            return None
        return trimmed


class ReceiptPreviewData(BaseModel):
    """Data preview struk yang dikirim ke frontend (hanya date dan items)."""

    date: Optional[str] = None
    items: list[ExtractedItem]


class ReceiptExtractResponse(BaseModel):
    """Skema respons sukses untuk POST /api/receipts/extract."""

    status: Literal["success"] = "success"
    data: ReceiptPreviewData
    warnings: list[str] = Field(default_factory=list)
    temp_image_token: Optional[str] = None
