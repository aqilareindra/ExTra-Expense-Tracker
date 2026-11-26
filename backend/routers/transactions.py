"""Router REST API untuk operasi CRUD dan riwayat transaksi ExTra."""

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import JSONResponse

from backend.schemas.categories import ExpenseCategory
from backend.schemas.transaction import (
    ErrorResponse,
    ItemDeleteResponse,
    ItemUpdateRequest,
    ItemUpdateResponse,
    TransactionCreateRequest,
    TransactionCreateResponse,
    TransactionDeleteResponse,
    TransactionListResponse,
)
from backend.services import transaction_service

router = APIRouter(prefix="/api", tags=["Transactions"])


def _not_found_response(message: str) -> JSONResponse:
    """Bangun respons JSON 404 NOT_FOUND yang konsisten."""
    payload = ErrorResponse(error_code="NOT_FOUND", message=message)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=payload.model_dump(exclude_none=True),
    )


@router.post(
    "/transactions",
    response_model=TransactionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
)
def create_transaction_endpoint(
    payload: TransactionCreateRequest,
) -> TransactionCreateResponse:
    """Simpan transaksi beserta daftar item yang telah dikonfirmasi pengguna."""
    created_data = transaction_service.create_transaction(payload)
    return TransactionCreateResponse(data=created_data)


@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    status_code=status.HTTP_200_OK,
    responses={422: {"model": ErrorResponse}},
)
def list_transactions_endpoint(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1000, le=9999),
    category: ExpenseCategory | None = Query(default=None),
    search: str | None = Query(default=None),
) -> TransactionListResponse:
    """Ambil daftar riwayat item transaksi dengan filter opsional month, year, category, dan search."""
    items = transaction_service.get_transactions(
        month=month,
        year=year,
        category=category,
        search=search,
    )
    return TransactionListResponse(count=len(items), data=items)


@router.put(
    "/items/{item_id}",
    response_model=ItemUpdateResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_item_endpoint(
    payload: ItemUpdateRequest,
    item_id: int = Path(..., ge=1),
) -> ItemUpdateResponse | JSONResponse:
    """Perbarui nama barang, harga, dan/atau tanggal transaksi pada item tersimpan."""
    updated_item = transaction_service.update_item(item_id=item_id, payload=payload)
    if updated_item is None:
        return _not_found_response(f"Item dengan ID {item_id} tidak ditemukan.")
    return ItemUpdateResponse(data=updated_item)


@router.delete(
    "/items/{item_id}",
    response_model=ItemDeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def delete_item_endpoint(
    item_id: int = Path(..., ge=1),
) -> ItemDeleteResponse | JSONResponse:
    """Hapus satu item pengeluaran dan bersihkan header transaksi jika yatim."""
    result = transaction_service.delete_item(item_id=item_id)
    if result is None:
        return _not_found_response(f"Item dengan ID {item_id} tidak ditemukan.")
    return ItemDeleteResponse(
        message="Item berhasil dihapus.",
        deleted_item_id=int(result["deleted_item_id"]),
        orphan_transaction_deleted=bool(result["orphan_transaction_deleted"]),
    )


@router.delete(
    "/transactions/{transaction_id}",
    response_model=TransactionDeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def delete_transaction_endpoint(
    transaction_id: int = Path(..., ge=1),
) -> TransactionDeleteResponse | JSONResponse:
    """Hapus keseluruhan transaksi beserta seluruh item terkait."""
    deleted = transaction_service.delete_transaction(transaction_id=transaction_id)
    if not deleted:
        return _not_found_response(
            f"Transaksi dengan ID {transaction_id} tidak ditemukan."
        )
    return TransactionDeleteResponse(
        message="Transaksi beserta seluruh item berhasil dihapus.",
        deleted_transaction_id=transaction_id,
    )
