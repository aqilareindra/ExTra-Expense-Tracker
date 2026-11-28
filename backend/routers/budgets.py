"""Router REST API untuk pemasukan (incomes), anggaran (budgets), dan AI Financial Insights (M3.3)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.schemas.auth import UserPublic
from backend.schemas.budget import (
    BudgetDeleteResponse,
    BudgetListResponse,
    BudgetUpsert,
    BudgetUpsertResponse,
    IncomeCreate,
    IncomeDeleteResponse,
    IncomeListResponse,
    IncomeResponse,
    MonthlyInsightsResponse,
)
from backend.schemas.transaction import ErrorResponse
from backend.services import budget_service, insights_service
from backend.services.auth_service import get_current_user
from backend.services.insights_service import InsightsServiceError

router = APIRouter(prefix="/api", tags=["Budgets & Incomes"])


def _not_found_response(message: str) -> JSONResponse:
    """Bangun respons JSON 404 NOT_FOUND konsisten."""
    payload = ErrorResponse(error_code="NOT_FOUND", message=message)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=payload.model_dump(exclude_none=True),
    )


def _error_json(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Bangun respons JSON error konsisten."""
    payload = ErrorResponse(error_code=error_code, message=message)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
    )


@router.post(
    "/incomes",
    response_model=IncomeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_income_endpoint(
    payload: IncomeCreate,
    current_user: UserPublic = Depends(get_current_user),
) -> IncomeResponse:
    """Catat pemasukan baru milik pengguna aktif."""
    created = budget_service.create_income(payload, user_id=current_user.id)
    return IncomeResponse(data=created)


@router.get(
    "/incomes",
    response_model=IncomeListResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def list_incomes_endpoint(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1000, le=9999),
    current_user: UserPublic = Depends(get_current_user),
) -> IncomeListResponse:
    """Ambil daftar pemasukan milik pengguna aktif beserta total pemasukan deterministik."""
    return budget_service.get_incomes(
        user_id=current_user.id,
        month=month,
        year=year,
    )


@router.delete(
    "/incomes/{income_id}",
    response_model=IncomeDeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def delete_income_endpoint(
    income_id: int = Path(..., ge=1),
    current_user: UserPublic = Depends(get_current_user),
) -> IncomeDeleteResponse | JSONResponse:
    """Hapus catatan pemasukan milik pengguna aktif."""
    deleted = budget_service.delete_income(income_id=income_id, user_id=current_user.id)
    if not deleted:
        return _not_found_response(
            f"Pemasukan dengan ID {income_id} tidak ditemukan."
        )
    return IncomeDeleteResponse(
        message="Catatan pemasukan berhasil dihapus.",
        deleted_income_id=income_id,
    )


@router.get(
    "/budgets",
    response_model=BudgetListResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_budgets_endpoint(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1000, le=9999),
    current_user: UserPublic = Depends(get_current_user),
) -> BudgetListResponse:
    """Ambil status anggaran bulanan per kategori milik pengguna aktif."""
    now = datetime.now(timezone.utc)
    resolved_month = month if month is not None else now.month
    resolved_year = year if year is not None else now.year
    return budget_service.get_budgets(
        month=resolved_month,
        year=resolved_year,
        user_id=current_user.id,
    )


@router.put(
    "/budgets",
    response_model=BudgetUpsertResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def upsert_budget_endpoint(
    payload: BudgetUpsert,
    current_user: UserPublic = Depends(get_current_user),
) -> BudgetUpsertResponse:
    """Simpan atau perbarui batas anggaran bulanan per kategori milik pengguna aktif."""
    budget_item = budget_service.upsert_budget(payload, user_id=current_user.id)
    return BudgetUpsertResponse(
        message="Anggaran kategori berhasil disimpan.",
        data=budget_item,
    )


@router.delete(
    "/budgets/{budget_id}",
    response_model=BudgetDeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def delete_budget_endpoint(
    budget_id: int = Path(..., ge=1),
    current_user: UserPublic = Depends(get_current_user),
) -> BudgetDeleteResponse | JSONResponse:
    """Hapus batas anggaran kategori milik pengguna aktif."""
    deleted = budget_service.delete_budget(budget_id=budget_id, user_id=current_user.id)
    if not deleted:
        return _not_found_response(
            f"Anggaran dengan ID {budget_id} tidak ditemukan."
        )
    return BudgetDeleteResponse(
        message="Anggaran kategori berhasil dihapus.",
        deleted_budget_id=budget_id,
    )


@router.get(
    "/insights/monthly",
    response_model=MonthlyInsightsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def get_monthly_insights_endpoint(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    current_user: UserPublic = Depends(get_current_user),
) -> MonthlyInsightsResponse | JSONResponse:
    """Hasilkan analisis & saran penghematan AI berbasis statistik agregat bulanan."""
    try:
        return await run_in_threadpool(
            insights_service.generate_monthly_insights,
            month=month,
            year=year,
            user_id=current_user.id,
        )
    except InsightsServiceError as exc:
        return _error_json(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
        )
