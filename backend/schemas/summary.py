"""Skema Pydantic v2 untuk respons ringkasan pengeluaran bulanan."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.schemas.transaction import (
    validate_iso_calendar_date,
    validate_strict_non_negative_price,
)


class DailyExpenseBreakdown(BaseModel):
    """Agregasi pengeluaran harian pada bulan dan tahun terpilih."""

    date: str
    total: int = Field(..., ge=0)
    item_count: int = Field(..., ge=0)

    @field_validator("date", mode="before")
    @classmethod
    def _check_date(cls, value: object) -> str:
        return validate_iso_calendar_date(value)

    @field_validator("total", "item_count", mode="before")
    @classmethod
    def _check_non_negative_int(cls, value: object) -> int:
        return validate_strict_non_negative_price(value)


class MonthlySummaryResponse(BaseModel):
    """Respons sukses untuk GET /api/summary/monthly sesuai Section 13 PRD."""

    status: Literal["success"] = "success"
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=1000, le=9999)
    total_expense: int = Field(..., ge=0)
    total_items: int = Field(..., ge=0)
    daily_breakdown: list[DailyExpenseBreakdown] = Field(default_factory=list)
