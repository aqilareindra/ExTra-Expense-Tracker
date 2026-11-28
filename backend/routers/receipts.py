"""Router REST API untuk ekstraksi foto struk belanja via Gemini Vision."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.schemas.auth import UserPublic
from backend.schemas.receipt import ReceiptExtractResponse
from backend.schemas.transaction import ErrorResponse
from backend.services import ai_service, image_service
from backend.services.ai_service import AIServiceError
from backend.services.auth_service import get_current_user
from backend.services.image_service import ImageServiceError, MAX_UPLOAD_SIZE_BYTES

router = APIRouter(prefix="/api/receipts", tags=["Receipts"])


def _error_json(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Bangun respons JSON error konsisten sesuai kontrak ExTra."""
    payload = ErrorResponse(error_code=error_code, message=message)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
    )


@router.post(
    "/extract",
    response_model=ReceiptExtractResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def extract_receipt_endpoint(
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(get_current_user),
) -> ReceiptExtractResponse | JSONResponse:
    """Validasi, kompres foto struk, dan ekstrak tanggal serta barang terisolasi per user."""
    try:
        raw_image_bytes = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    finally:
        await file.close()

    try:
        compressed_bytes, target_mime = await run_in_threadpool(
            image_service.validate_and_compress_image,
            image_bytes=raw_image_bytes,
            filename=file.filename or "",
            content_type=file.content_type or "",
        )
    except ImageServiceError as exc:
        http_status = (
            (
                status.HTTP_413_CONTENT_TOO_LARGE
                if hasattr(status, "HTTP_413_CONTENT_TOO_LARGE")
                else 413
            )
            if exc.status_code == 413
            else exc.status_code
        )
        return _error_json(
            status_code=http_status,
            error_code=exc.error_code,
            message=exc.message,
        )

    try:
        result = await run_in_threadpool(
            ai_service.extract_receipt_from_image,
            image_bytes=compressed_bytes,
            mime_type=target_mime,
        )
    except AIServiceError as exc:
        return _error_json(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
        )

    temp_token = await run_in_threadpool(
        image_service.save_temp_receipt_image,
        compressed_bytes,
        current_user.id,
    )
    return result.model_copy(update={"temp_image_token": temp_token})
