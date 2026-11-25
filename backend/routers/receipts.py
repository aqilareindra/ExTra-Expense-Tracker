"""Router REST API untuk ekstraksi foto struk belanja via Gemini Vision."""

from pathlib import Path as FilePath

from fastapi import APIRouter, File, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.schemas.receipt import ReceiptExtractResponse
from backend.schemas.transaction import ErrorResponse
from backend.services import ai_service
from backend.services.ai_service import AIServiceError

router = APIRouter(prefix="/api/receipts", tags=["Receipts"])

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
JPEG_MAGIC_BYTES = b"\xff\xd8\xff"
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"


def _error_json(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Bangun respons JSON error konsisten sesuai kontrak ExTra."""
    payload = ErrorResponse(error_code=error_code, message=message)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
    )


def _validate_and_detect_mime(
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> str | None:
    """Validasi ekstensi, MIME type, dan magic bytes gambar secara serentak."""
    if not content:
        return None

    extension = FilePath(filename or "").suffix.lower()
    normalized_mime = (content_type or "").split(";")[0].strip().lower()

    if (
        extension in {".jpg", ".jpeg"}
        and normalized_mime == "image/jpeg"
        and content.startswith(JPEG_MAGIC_BYTES)
    ):
        return "image/jpeg"

    if (
        extension == ".png"
        and normalized_mime == "image/png"
        and content.startswith(PNG_MAGIC_BYTES)
    ):
        return "image/png"

    return None


@router.post(
    "/extract",
    response_model=ReceiptExtractResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
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
) -> ReceiptExtractResponse | JSONResponse:
    """Validasi foto struk dan ekstrak tanggal serta daftar barang tanpa menyimpan ke DB."""
    try:
        image_bytes = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    finally:
        await file.close()

    if len(image_bytes) > MAX_UPLOAD_SIZE_BYTES:
        return _error_json(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE
            if hasattr(status, "HTTP_413_CONTENT_TOO_LARGE")
            else 413,
            error_code="FILE_TOO_LARGE",
            message="Ukuran file melebihi batas maksimal 5 MB.",
        )

    detected_mime = _validate_and_detect_mime(
        filename=file.filename,
        content_type=file.content_type,
        content=image_bytes,
    )
    if detected_mime is None:
        return _error_json(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_FILE_TYPE",
            message=(
                "Format file tidak valid. Harap unggah file gambar JPG, JPEG, "
                "atau PNG yang asli."
            ),
        )

    try:
        result = await run_in_threadpool(
            ai_service.extract_receipt_from_image,
            image_bytes=image_bytes,
            mime_type=detected_mime,
        )
    except AIServiceError as exc:
        return _error_json(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
        )

    return result
