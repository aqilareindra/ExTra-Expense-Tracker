"""Layanan validasi dan kompresi gambar struk belanja menggunakan Pillow."""

import io
import logging
from pathlib import Path
import shutil
import time
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError

from backend import config as app_config
from backend.schemas.transaction import validate_strict_uuid_token

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_WIDTH = 1280
JPEG_QUALITY = 85
TARGET_MIME_TYPE = "image/jpeg"

JPEG_MAGIC_BYTES = b"\xff\xd8\xff"
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"


class ImageServiceError(Exception):
    """Base domain exception untuk validasi dan pemrosesan gambar struk."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class ImageTooLargeError(ImageServiceError):
    """Error ketika ukuran file unggahan melebihi batas maksimum 5 MB (HTTP 413)."""

    def __init__(
        self,
        message: str = "Ukuran file melebihi batas maksimal 5 MB.",
    ) -> None:
        super().__init__(
            status_code=413,
            error_code="FILE_TOO_LARGE",
            message=message,
        )


class InvalidImageError(ImageServiceError):
    """Error ketika format, magic bytes, atau isi gambar tidak valid/korup (HTTP 400)."""

    def __init__(
        self,
        message: str = (
            "Format file tidak valid. Harap unggah file gambar JPG, JPEG, "
            "atau PNG yang asli."
        ),
    ) -> None:
        super().__init__(
            status_code=400,
            error_code="INVALID_FILE_TYPE",
            message=message,
        )


class InvalidTempTokenError(ImageServiceError):
    """Error ketika token gambar struk sementara tidak valid atau mengandung karakter ilegal."""

    def __init__(
        self,
        message: str = "Token gambar struk sementara tidak valid.",
    ) -> None:
        super().__init__(
            status_code=400,
            error_code="INVALID_TEMP_TOKEN",
            message=message,
        )


class ReceiptTempNotFoundError(ImageServiceError):
    """Error ketika file struk sementara tidak ditemukan atau telah kedaluwarsa (HTTP 400)."""

    def __init__(
        self,
        message: str = (
            "File gambar struk sementara tidak ditemukan atau sudah kedaluwarsa. "
            "Silakan unggah ulang struk atau simpan tanpa arsip foto."
        ),
    ) -> None:
        super().__init__(
            status_code=400,
            error_code="RECEIPT_TEMP_NOT_FOUND",
            message=message,
        )


def _detect_expected_image_spec(
    image_bytes: bytes,
    filename: str | None,
    content_type: str | None,
) -> str:
    """Validasi magic bytes serta konsistensi ekstensi/MIME dan kembalikan format Pillow."""
    if image_bytes.startswith(JPEG_MAGIC_BYTES):
        expected_format = "JPEG"
        expected_mime = "image/jpeg"
        allowed_extensions = {".jpg", ".jpeg"}
    elif image_bytes.startswith(PNG_MAGIC_BYTES):
        expected_format = "PNG"
        expected_mime = "image/png"
        allowed_extensions = {".png"}
    else:
        raise InvalidImageError()

    if filename is not None:
        extension = Path(filename).suffix.lower()
        if extension not in allowed_extensions:
            raise InvalidImageError()

    if content_type is not None:
        normalized_mime = content_type.split(";")[0].strip().lower()
        if normalized_mime != expected_mime:
            raise InvalidImageError()

    return expected_format


def _convert_to_rgb_safely(image: Image.Image) -> Image.Image:
    """Konversi mode warna non-RGB ke RGB dengan latar putih untuk gambar transparan."""
    if image.mode == "RGB":
        return image

    has_alpha = image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )
    if has_alpha:
        rgba_image = image.convert("RGBA")
        white_bg = Image.new("RGB", rgba_image.size, (255, 255, 255))
        white_bg.paste(rgba_image, mask=rgba_image.getchannel("A"))
        return white_bg

    return image.convert("RGB")


def validate_and_compress_image(
    image_bytes: bytes,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[bytes, str]:
    """Validasi ukuran/format/integritas gambar, normalisasi EXIF, resize <=1280px, dan kompres ke JPEG."""
    if not isinstance(image_bytes, (bytes, bytearray)):
        raise InvalidImageError()

    raw_bytes = bytes(image_bytes)
    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise ImageTooLargeError()

    if not raw_bytes:
        raise InvalidImageError()

    expected_format = _detect_expected_image_spec(
        image_bytes=raw_bytes,
        filename=filename,
        content_type=content_type,
    )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as opened_img:
            actual_format = (opened_img.format or "").upper()
            if actual_format != expected_format:
                raise InvalidImageError()

            opened_img.load()
            if opened_img.width <= 0 or opened_img.height <= 0:
                raise InvalidImageError()

            normalized_img = ImageOps.exif_transpose(opened_img)

            if normalized_img.width > MAX_IMAGE_WIDTH:
                scale_ratio = MAX_IMAGE_WIDTH / normalized_img.width
                target_height = max(1, round(normalized_img.height * scale_ratio))
                resized_img = normalized_img.resize(
                    (MAX_IMAGE_WIDTH, target_height),
                    Image.Resampling.LANCZOS,
                )
            else:
                resized_img = normalized_img

            rgb_img = _convert_to_rgb_safely(resized_img)

            output_buffer = io.BytesIO()
            rgb_img.save(
                output_buffer,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
            )
            compressed_bytes = output_buffer.getvalue()
    except ImageServiceError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        logger.warning("File gambar ditolak karena korup atau tidak valid (%s).", type(exc).__name__)
        raise InvalidImageError() from exc

    return compressed_bytes, TARGET_MIME_TYPE


def cleanup_expired_temp_images(
    ttl_seconds: int | None = None,
    now_ts: float | None = None,
) -> int:
    """Hapus file JPEG sementara di uploads/temp/ yang usianya melampaui batas TTL."""
    temp_dir = app_config.get_temp_receipts_dir()
    if not temp_dir.is_dir():
        return 0

    ttl = app_config.get_temp_receipt_ttl_seconds() if ttl_seconds is None else ttl_seconds
    current_ts = time.time() if now_ts is None else now_ts
    removed_count = 0

    for candidate in temp_dir.glob("*.jpg"):
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            age_seconds = current_ts - candidate.stat().st_mtime
            if age_seconds > ttl:
                candidate.unlink(missing_ok=True)
                removed_count += 1
        except OSError as exc:
            logger.warning("Gagal membersihkan file temp kedaluwarsa (%s).", type(exc).__name__)

    return removed_count


def save_temp_receipt_image(compressed_jpeg_bytes: bytes) -> str:
    """Simpan gambar struk JPEG terkompresi ke uploads/temp/{uuid}.jpg dan kembalikan token UUID."""
    cleanup_expired_temp_images()

    temp_root = app_config.get_temp_receipts_dir().resolve()
    temp_root.mkdir(parents=True, exist_ok=True)

    token = str(uuid.uuid4())
    dest = (temp_root / f"{token}.jpg").resolve()
    if dest.parent != temp_root:
        raise InvalidTempTokenError()

    dest.write_bytes(compressed_jpeg_bytes)
    return token


def promote_temp_receipt_to_archive(temp_token: str) -> str:
    """Validasi token UUID, pindahkan file dari uploads/temp/ ke uploads/receipts/, dan kembalikan nama file."""
    cleanup_expired_temp_images()

    try:
        clean_token = validate_strict_uuid_token(temp_token)
    except ValueError as exc:
        raise InvalidTempTokenError() from exc

    temp_root = app_config.get_temp_receipts_dir().resolve()
    src = (temp_root / f"{clean_token}.jpg").resolve()
    if src.parent != temp_root or src.is_symlink() or not src.is_file():
        raise ReceiptTempNotFoundError()

    receipts_root = app_config.get_receipts_dir().resolve()
    receipts_root.mkdir(parents=True, exist_ok=True)

    archive_filename = f"{uuid.uuid4()}.jpg"
    dest = (receipts_root / archive_filename).resolve()
    if dest.parent != receipts_root:
        raise InvalidTempTokenError()

    shutil.move(str(src), str(dest))
    return archive_filename


def resolve_archived_receipt_path(stored_filename: str | None) -> Path | None:
    """Resolve nama file arsip struk secara aman dan cegah path traversal."""
    if not stored_filename or not isinstance(stored_filename, str):
        return None
    if (
        "/" in stored_filename
        or "\\" in stored_filename
        or ".." in stored_filename
        or Path(stored_filename).name != stored_filename
    ):
        return None

    receipts_root = app_config.get_receipts_dir().resolve()
    candidate = (receipts_root / stored_filename).resolve()
    if (
        candidate.parent != receipts_root
        or not candidate.is_relative_to(receipts_root)
        or candidate.is_symlink()
        or not candidate.is_file()
    ):
        return None

    return candidate


def delete_archived_receipt_file(stored_filename: str | None) -> bool:
    """Hapus file arsip struk fisik di uploads/receipts/ dengan aman."""
    target = resolve_archived_receipt_path(stored_filename)
    if target is None:
        return False

    try:
        target.unlink(missing_ok=True)
        return True
    except OSError as exc:
        logger.warning("Gagal menghapus file arsip struk (%s).", type(exc).__name__)
        return False
