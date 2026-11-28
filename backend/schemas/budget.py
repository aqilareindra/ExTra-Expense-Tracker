"""Skema Pydantic v2 untuk pemasukan (incomes), anggaran (budgets), dan AI insights (M3.3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.schemas.categories import validate_strict_category
from backend.schemas.transaction import (
    validate_iso_calendar_date,
    validate_strict_non_negative_price,
)

BudgetStatus = Literal["safe", "warning", "over_budget"]


def _validate_strict_int_range(
    value: object,
    *,
    min_val: int,
    max_val: int,
    field_label: str,
) -> int:
    """Validasi integer murni dalam rentang tertentu (menolak bool, float, dan string)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_label} harus berupa bilangan bulat (integer).")
    if not min_val <= value <= max_val:
        raise ValueError(
            f"{field_label} harus bernilai antara {min_val} hingga {max_val}."
        )
    return value


def _validate_non_empty_trimmed_text(
    value: object,
    *,
    field_label: str,
    max_length: int | None = None,
) -> str:
    """Pastikan nilai bertipe string non-kosong setelah trim."""
    if not isinstance(value, str):
        raise ValueError(f"{field_label} harus berupa string.")
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_label} tidak boleh kosong.")
    if max_length is not None and len(trimmed) > max_length:
        raise ValueError(f"{field_label} maksimal {max_length} karakter.")
    return trimmed


# ---------------------------------------------------------------------------
# Incomes Schemas
# ---------------------------------------------------------------------------


class IncomeCreate(BaseModel):
    """Skema input pencatatan pemasukan baru."""

    model_config = ConfigDict(extra="forbid")

    income_date: str
    source_name: str
    amount: int

    @field_validator("income_date", mode="before")
    @classmethod
    def _check_income_date(cls, value: object) -> str:
        return validate_iso_calendar_date(value)

    @field_validator("source_name", mode="before")
    @classmethod
    def _check_source_name(cls, value: object) -> str:
        return _validate_non_empty_trimmed_text(
            value,
            field_label="Sumber pemasukan",
            max_length=200,
        )

    @field_validator("amount", mode="before")
    @classmethod
    def _check_amount(cls, value: object) -> int:
        return validate_strict_non_negative_price(value)


class IncomeRecord(BaseModel):
    """Representasi satu catatan pemasukan tersimpan."""

    id: int
    income_date: str
    source_name: str
    amount: int
    created_at: str


class IncomeResponse(BaseModel):
    """Respons sukses untuk POST /api/incomes."""

    status: Literal["success"] = "success"
    data: IncomeRecord


class IncomeListResponse(BaseModel):
    """Respons sukses untuk GET /api/incomes."""

    status: Literal["success"] = "success"
    count: int
    total_income: int = Field(..., ge=0)
    data: list[IncomeRecord] = Field(default_factory=list)


class IncomeDeleteResponse(BaseModel):
    """Respons sukses untuk DELETE /api/incomes/{income_id}."""

    status: Literal["success"] = "success"
    message: str
    deleted_income_id: int


# ---------------------------------------------------------------------------
# Budgets Schemas
# ---------------------------------------------------------------------------


class BudgetUpsert(BaseModel):
    """Skema input pengaturan/pembaruan batas anggaran bulanan per kategori."""

    model_config = ConfigDict(extra="forbid")

    month: int
    year: int
    category: str
    limit_amount: int

    @field_validator("month", mode="before")
    @classmethod
    def _check_month(cls, value: object) -> int:
        return _validate_strict_int_range(
            value,
            min_val=1,
            max_val=12,
            field_label="Bulan",
        )

    @field_validator("year", mode="before")
    @classmethod
    def _check_year(cls, value: object) -> int:
        return _validate_strict_int_range(
            value,
            min_val=1000,
            max_val=9999,
            field_label="Tahun",
        )

    @field_validator("category", mode="before")
    @classmethod
    def _check_category(cls, value: object) -> str:
        return validate_strict_category(value)

    @field_validator("limit_amount", mode="before")
    @classmethod
    def _check_limit_amount(cls, value: object) -> int:
        return validate_strict_non_negative_price(value)


class BudgetStatusItem(BaseModel):
    """Status realisasi anggaran deterministik untuk satu kategori pada periode tertentu."""

    id: int
    month: int
    year: int
    category: str
    limit_amount: int
    spent_amount: int
    remaining_amount: int
    usage_percentage: float
    status: BudgetStatus


class BudgetUpsertResponse(BaseModel):
    """Respons sukses untuk PUT /api/budgets."""

    status: Literal["success"] = "success"
    message: str
    data: BudgetStatusItem


class BudgetListResponse(BaseModel):
    """Respons sukses untuk GET /api/budgets."""

    status: Literal["success"] = "success"
    month: int
    year: int
    total_budget: int
    total_spent: int
    total_remaining: int
    data: list[BudgetStatusItem] = Field(default_factory=list)


class BudgetDeleteResponse(BaseModel):
    """Respons sukses untuk DELETE /api/budgets/{budget_id}."""

    status: Literal["success"] = "success"
    message: str
    deleted_budget_id: int


# ---------------------------------------------------------------------------
# AI Financial Insights Schemas
# ---------------------------------------------------------------------------


class InsightsTopCategoryItem(BaseModel):
    """Ringkasan agregat top kategori pengeluaran tanpa data item mentah."""

    category: str
    total: int
    share_percentage: float
    item_count: int


class InsightsBudgetAlertItem(BaseModel):
    """Ringkasan status anggaran kategori untuk konteks rekomendasi AI."""

    category: str
    limit_amount: int
    spent_amount: int
    remaining_amount: int
    usage_percentage: float
    status: BudgetStatus


class InsightsMetricsSnapshot(BaseModel):
    """Snapshot statistik deterministik hasil perhitungan Python/SQL (tanpa baris mentah)."""

    month: int
    year: int
    total_income: int
    total_expense: int
    net_balance: int
    total_items: int
    previous_month: int
    previous_year: int
    previous_month_expense: int
    mom_expense_change_amount: int
    mom_expense_change_percentage: float | None = None
    top_categories: list[InsightsTopCategoryItem] = Field(default_factory=list)
    budget_alerts: list[InsightsBudgetAlertItem] = Field(default_factory=list)


class LLMInsightsOutput(BaseModel):
    """Skema validasi output JSON terstruktur dari Gemini Flash untuk AI Financial Insights."""

    summary_text: str
    recommendations: list[str] = Field(..., min_length=1, max_length=5)

    @field_validator("summary_text", mode="before")
    @classmethod
    def _check_summary_text(cls, value: object) -> str:
        return _validate_non_empty_trimmed_text(
            value,
            field_label="Ringkasan narasi AI",
        )

    @field_validator("recommendations", mode="before")
    @classmethod
    def _check_recommendations(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Rekomendasi harus berupa daftar string.")
        cleaned: list[str] = []
        for entry in value:
            if isinstance(entry, str) and entry.strip():
                cleaned.append(entry.strip())
        if not cleaned:
            raise ValueError("Rekomendasi AI harus berisi minimal 1 poin saran.")
        return cleaned[:5]


class MonthlyInsightsResponse(BaseModel):
    """Respons sukses untuk GET /api/insights/monthly."""

    status: Literal["success"] = "success"
    month: int
    year: int
    has_data: bool
    summary_text: str
    recommendations: list[str] = Field(default_factory=list)
    metrics_snapshot: InsightsMetricsSnapshot
