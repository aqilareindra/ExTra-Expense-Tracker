"""Router REST API untuk ringkasan pengeluaran bulanan ExTra."""

from fastapi import APIRouter, Query, status

from backend.schemas.summary import MonthlySummaryResponse
from backend.schemas.transaction import ErrorResponse
from backend.services import summary_service

router = APIRouter(prefix="/api/summary", tags=["Summary"])


@router.get(
    "/monthly",
    response_model=MonthlySummaryResponse,
    status_code=status.HTTP_200_OK,
    responses={422: {"model": ErrorResponse}},
)
def get_monthly_summary_endpoint(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
) -> MonthlySummaryResponse:
    """Ambil ringkasan total pengeluaran, jumlah barang, dan agregasi harian bulanan."""
    return summary_service.get_monthly_summary(month=month, year=year)
