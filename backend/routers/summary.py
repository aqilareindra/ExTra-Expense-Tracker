"""Router REST API untuk ringkasan pengeluaran bulanan ExTra."""

from fastapi import APIRouter, Depends, Query, status

from backend.schemas.auth import UserPublic
from backend.schemas.summary import MonthlySummaryResponse
from backend.schemas.transaction import ErrorResponse
from backend.services import summary_service
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/summary", tags=["Summary"])


@router.get(
    "/monthly",
    response_model=MonthlySummaryResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_monthly_summary_endpoint(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    current_user: UserPublic = Depends(get_current_user),
) -> MonthlySummaryResponse:
    """Ambil ringkasan total pengeluaran, jumlah barang, dan agregasi harian milik user aktif."""
    return summary_service.get_monthly_summary(
        month=month,
        year=year,
        user_id=current_user.id,
    )
