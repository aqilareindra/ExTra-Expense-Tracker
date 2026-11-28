"""Router REST API untuk operasi CRUD, ekspor CSV, dan arsip struk terisolasi per pengguna."""

from fastapi import APIRouter, Depends, Path, Query, Response, status
from fastapi.responses import FileResponse, JSONResponse

from backend.schemas.auth import UserPublic
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
from backend.services import export_service, image_service, transaction_service
from backend.services.auth_service import get_current_user
from backend.services.image_service import ImageServiceError

router = APIRouter(prefix="/api", tags=["Transactions"])


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Bangun respons JSON error yang konsisten dengan kontrak ExTra."""
    payload = ErrorResponse(error_code=error_code, message=message)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
    )


def _not_found_response(message: str) -> JSONResponse:
    """Bangun respons JSON 404 NOT_FOUND yang konsisten."""
    return _error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="NOT_FOUND",
        message=message,
    )


@router.post(
    "/transactions",
    response_model=TransactionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def create_transaction_endpoint(
    payload: TransactionCreateRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> TransactionCreateResponse | JSONResponse:
    """Simpan transaksi beserta daftar item milik pengguna yang sedang login."""
    try:
        created_data = transaction_service.create_transaction(
            payload,
            user_id=current_user.id,
        )
    except ImageServiceError as exc:
        return _error_response(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
        )
    return TransactionCreateResponse(data=created_data)


@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def list_transactions_endpoint(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1000, le=9999),
    category: ExpenseCategory | None = Query(default=None),
    search: str | None = Query(default=None),
    current_user: UserPublic = Depends(get_current_user),
) -> TransactionListResponse:
    """Ambil daftar riwayat item transaksi milik pengguna aktif."""
    items = transaction_service.get_transactions(
        user_id=current_user.id,
        month=month,
        year=year,
        category=category,
        search=search,
    )
    return TransactionListResponse(count=len(items), data=items)


@router.get(
    "/transactions/export",
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def export_transactions_csv_endpoint(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1000, le=9999),
    category: ExpenseCategory | None = Query(default=None),
    search: str | None = Query(default=None),
    current_user: UserPublic = Depends(get_current_user),
) -> Response:
    """Unduh riwayat pengeluaran terfilter milik pengguna aktif dalam format CSV."""
    csv_bytes = export_service.generate_transactions_csv(
        user_id=current_user.id,
        month=month,
        year=year,
        category=category,
        search=search,
    )
    filename = export_service.build_export_filename(month=month, year=year)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/transactions/{transaction_id}/receipt",
    response_model=None,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def get_transaction_receipt_endpoint(
    transaction_id: int = Path(..., ge=1),
    current_user: UserPublic = Depends(get_current_user),
) -> FileResponse | JSONResponse:
    """Ambil file foto struk terarsip milik transaksi pengguna aktif secara aman."""
    stored_filename = transaction_service.get_transaction_receipt_filename(
        transaction_id=transaction_id,
        user_id=current_user.id,
    )
    file_path = image_service.resolve_archived_receipt_path(stored_filename)
    if file_path is None:
        return _not_found_response(
            f"Arsip foto struk untuk transaksi dengan ID {transaction_id} tidak ditemukan."
        )
    return FileResponse(path=file_path, media_type="image/jpeg")


@router.put(
    "/items/{item_id}",
    response_model=ItemUpdateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def update_item_endpoint(
    payload: ItemUpdateRequest,
    item_id: int = Path(..., ge=1),
    current_user: UserPublic = Depends(get_current_user),
) -> ItemUpdateResponse | JSONResponse:
    """Perbarui nama barang, harga, kategori, dan/atau tanggal pada item milik pengguna aktif."""
    updated_item = transaction_service.update_item(
        item_id=item_id,
        payload=payload,
        user_id=current_user.id,
    )
    if updated_item is None:
        return _not_found_response(f"Item dengan ID {item_id} tidak ditemukan.")
    return ItemUpdateResponse(data=updated_item)


@router.delete(
    "/items/{item_id}",
    response_model=ItemDeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def delete_item_endpoint(
    item_id: int = Path(..., ge=1),
    current_user: UserPublic = Depends(get_current_user),
) -> ItemDeleteResponse | JSONResponse:
    """Hapus satu item milik pengguna aktif dan bersihkan transaksi yatim jika kosong."""
    result = transaction_service.delete_item(
        item_id=item_id,
        user_id=current_user.id,
    )
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
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def delete_transaction_endpoint(
    transaction_id: int = Path(..., ge=1),
    current_user: UserPublic = Depends(get_current_user),
) -> TransactionDeleteResponse | JSONResponse:
    """Hapus keseluruhan transaksi milik pengguna aktif beserta item dan arsip struknya."""
    deleted = transaction_service.delete_transaction(
        transaction_id=transaction_id,
        user_id=current_user.id,
    )
    if not deleted:
        return _not_found_response(
            f"Transaksi dengan ID {transaction_id} tidak ditemukan."
        )
    return TransactionDeleteResponse(
        message="Transaksi beserta seluruh item berhasil dihapus.",
        deleted_transaction_id=transaction_id,
    )
