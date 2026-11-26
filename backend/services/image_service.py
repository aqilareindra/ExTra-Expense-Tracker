"""Layanan validasi dan kompresi gambar struk belanja menggunakan Pillow."""

import io
import logging
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

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
