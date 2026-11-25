"""Layanan pemanggilan Google Gemini Vision API untuk ekstraksi struk belanja."""

import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from backend import config as app_config
from backend.schemas.receipt import (
    ReceiptExtractionResult,
    ReceiptExtractResponse,
    ReceiptPreviewData,
)
from backend.services.prompts import (
    RECEIPT_EXTRACTION_USER_PROMPT,
    RECEIPT_SYSTEM_INSTRUCTION,
)

logger = logging.getLogger(__name__)

AI_TIMEOUT_SECONDS = 30
AI_TIMEOUT_MS = AI_TIMEOUT_SECONDS * 1000

MISSING_DATE_WARNING = (
    "Tanggal transaksi tidak terbaca pada struk. Silakan isi manual sebelum menyimpan."
)


class AIServiceError(Exception):
    """Base domain exception untuk seluruh kegagalan pada layer ekstraksi AI."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class AIConfigurationError(AIServiceError):
    """Error konfigurasi kredensial AI di sisi server (HTTP 500)."""

    def __init__(
        self,
        message: str = "Konfigurasi layanan AI pada server belum lengkap atau tidak valid.",
    ) -> None:
        super().__init__(
            status_code=500,
            error_code="CONFIGURATION_ERROR",
            message=message,
        )


class NotAReceiptError(AIServiceError):
    """Error ketika gambar bukan merupakan struk belanja (HTTP 422)."""

    def __init__(
        self,
        message: str = "Gambar yang diunggah bukan merupakan struk belanja yang dapat diproses.",
    ) -> None:
        super().__init__(
            status_code=422,
            error_code="NOT_A_RECEIPT",
            message=message,
        )


class UnreadableReceiptError(AIServiceError):
    """Error ketika struk terlalu buram/gelap sehingga tidak ada item terbaca (HTTP 422)."""

    def __init__(
        self,
        message: str = (
            "Tidak ada item belanja yang terbaca pada struk. "
            "Pastikan foto struk cukup terang dan fokus lalu coba lagi."
        ),
    ) -> None:
        super().__init__(
            status_code=422,
            error_code="UNREADABLE_RECEIPT",
            message=message,
        )


class AIParseError(AIServiceError):
    """Error ketika output JSON dari AI rusak atau gagal validasi skema (HTTP 502)."""

    def __init__(
        self,
        message: str = (
            "Gagal memproses format hasil ekstraksi AI. Silakan coba unggah ulang struk."
        ),
    ) -> None:
        super().__init__(
            status_code=502,
            error_code="AI_PARSE_ERROR",
            message=message,
        )


class AIServiceUnavailableError(AIServiceError):
    """Error ketika Gemini API rate-limited (429), timeout, atau gangguan jaringan (503)."""

    def __init__(
        self,
        status_code: int = 503,
        message: str = (
            "Layanan ekstraksi AI sedang sibuk atau tidak dapat dijangkau sementara. "
            "Silakan coba lagi beberapa saat."
        ),
    ) -> None:
        super().__init__(
            status_code=status_code,
            error_code="AI_SERVICE_UNAVAILABLE",
            message=message,
        )


def _create_genai_client(api_key: str) -> genai.Client:
    """Inisialisasi client Google GenAI dengan batas timeout 30 detik (30.000 ms)."""
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=AI_TIMEOUT_MS),
    )


def extract_receipt_from_image(
    image_bytes: bytes,
    mime_type: str,
) -> ReceiptExtractResponse:
    """Kirim inline bytes gambar struk ke Gemini Flash dan validasi hasilnya."""
    try:
        api_key = app_config.get_gemini_api_key()
    except app_config.ConfigurationError as exc:
        logger.error("Kredensial Gemini belum terkonfigurasi dengan benar.")
        raise AIConfigurationError() from exc

    client = _create_genai_client(api_key)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    generation_config = types.GenerateContentConfig(
        system_instruction=RECEIPT_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=ReceiptExtractionResult,
        temperature=0.0,
    )

    try:
        response = client.models.generate_content(
            model=app_config.GEMINI_MODEL,
            contents=[image_part, RECEIPT_EXTRACTION_USER_PROMPT],
            config=generation_config,
        )
    except genai_errors.APIError as exc:
        if exc.code == 429:
            logger.warning("Rate limit Gemini API tercapai (HTTP 429).")
            raise AIServiceUnavailableError(
                status_code=429,
                message=(
                    "Batas permintaan layanan AI tercapai sementara. "
                    "Silakan tunggu sebentar lalu coba lagi."
                ),
            ) from exc

        err_status = (exc.status or "").upper()
        err_msg_upper = (exc.message or "").upper()
        if (
            exc.code in (401, 403)
            or "API_KEY_INVALID" in err_status
            or "API_KEY_INVALID" in err_msg_upper
            or "API KEY NOT VALID" in err_msg_upper
        ):
            logger.error(
                "Autentikasi ke Gemini API gagal (kode HTTP %s, status %s).",
                exc.code,
                exc.status,
            )
            raise AIConfigurationError() from exc

        logger.error(
            "Gangguan eksternal Gemini API (kode HTTP %s, status %s).",
            exc.code,
            exc.status,
        )
        raise AIServiceUnavailableError(status_code=503) from exc
    except TimeoutError as exc:
        logger.warning("Permintaan ke Gemini API melewati batas timeout 30 detik.")
        raise AIServiceUnavailableError(
            status_code=503,
            message=(
                "Pemrosesan struk melewati batas waktu 30 detik. "
                "Silakan coba unggah ulang."
            ),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        exc_type_name = type(exc).__name__.lower()
        if "timeout" in exc_type_name:
            logger.warning("Timeout koneksi HTTP ke Gemini API (%s).", type(exc).__name__)
            raise AIServiceUnavailableError(
                status_code=503,
                message=(
                    "Pemrosesan struk melewati batas waktu 30 detik. "
                    "Silakan coba unggah ulang."
                ),
            ) from exc

        logger.error(
            "Kegagalan komunikasi ke layanan Gemini API (%s).",
            type(exc).__name__,
        )
        raise AIServiceUnavailableError(status_code=503) from exc

    raw_json = (response.text or "").strip()
    if not raw_json:
        logger.error("Gemini API mengembalikan teks respons kosong.")
        raise AIParseError()

    try:
        parsed = ReceiptExtractionResult.model_validate_json(raw_json)
    except (ValidationError, ValueError) as exc:
        logger.error("Gagal memvalidasi JSON ekstraksi dari Gemini: %s", type(exc).__name__)
        raise AIParseError() from exc

    if not parsed.is_receipt:
        reason = (parsed.error_reason or "").strip()
        raise NotAReceiptError(
            message=reason
            if reason
            else "Gambar yang diunggah bukan merupakan struk belanja yang dapat dibaca."
        )

    if not parsed.items:
        reason = (parsed.error_reason or "").strip()
        raise UnreadableReceiptError(
            message=reason
            if reason
            else (
                "Tidak ada daftar barang yang terbaca pada struk. "
                "Silakan ambil ulang foto struk dengan lebih jelas."
            )
        )

    warnings: list[str] = []
    if parsed.date is None:
        warnings.append(MISSING_DATE_WARNING)

    return ReceiptExtractResponse(
        status="success",
        data=ReceiptPreviewData(
            date=parsed.date,
            items=parsed.items,
        ),
        warnings=warnings,
    )
