"""Layanan pemanggilan Google Gemini Vision API untuk ekstraksi struk belanja."""

import logging
import time
from typing import Any

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

MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
TRANSIENT_HTTP_CODES = frozenset({429, 503})
TRANSIENT_ERROR_STATUSES = frozenset({"RESOURCE_EXHAUSTED", "UNAVAILABLE"})

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


def _is_auth_api_error(exc: genai_errors.APIError) -> bool:
    """Periksa apakah APIError disebabkan kredensial/API key yang tidak valid."""
    err_status = (exc.status or "").upper()
    err_msg_upper = (exc.message or "").upper()
    return (
        exc.code in (401, 403)
        or "API_KEY_INVALID" in err_status
        or "API_KEY_INVALID" in err_msg_upper
        or "API KEY NOT VALID" in err_msg_upper
    )


def _is_transient_api_error(exc: genai_errors.APIError) -> bool:
    """Periksa apakah APIError bersifat sementara (429 Rate Limit / 503 Unavailable)."""
    if exc.code in TRANSIENT_HTTP_CODES:
        return True
    err_status = (exc.status or "").upper()
    return exc.code is None and err_status in TRANSIENT_ERROR_STATUSES


def _raise_unavailable_from_transient_error(exc: genai_errors.APIError) -> None:
    """Petakan APIError sementara terakhir ke AIServiceUnavailableError yang sesuai."""
    if exc.code == 429:
        raise AIServiceUnavailableError(
            status_code=429,
            message=(
                "Batas permintaan layanan AI tercapai sementara. "
                "Silakan tunggu sebentar lalu coba lagi."
            ),
        ) from exc
    raise AIServiceUnavailableError(status_code=503) from exc


def _call_model_once(
    client: Any,
    model_name: str,
    image_part: types.Part,
    generation_config: types.GenerateContentConfig,
) -> Any:
    """Eksekusi satu panggilan generate_content dan petakan error non-transient secara langsung."""
    try:
        return client.models.generate_content(
            model=model_name,
            contents=[image_part, RECEIPT_EXTRACTION_USER_PROMPT],
            config=generation_config,
        )
    except genai_errors.APIError as exc:
        if _is_auth_api_error(exc):
            logger.error(
                "Autentikasi ke Gemini API gagal pada model '%s' (kode HTTP %s, status %s).",
                model_name,
                exc.code,
                exc.status,
            )
            raise AIConfigurationError() from exc

        if _is_transient_api_error(exc):
            raise

        logger.error(
            "Error non-transient Gemini API pada model '%s' (kode HTTP %s, status %s).",
            model_name,
            exc.code,
            exc.status,
        )
        raise AIServiceUnavailableError(status_code=503) from exc
    except TimeoutError as exc:
        logger.warning(
            "Permintaan ke Gemini API pada model '%s' melewati batas timeout 30 detik.",
            model_name,
        )
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
            logger.warning(
                "Timeout koneksi HTTP ke Gemini API pada model '%s' (%s).",
                model_name,
                type(exc).__name__,
            )
            raise AIServiceUnavailableError(
                status_code=503,
                message=(
                    "Pemrosesan struk melewati batas waktu 30 detik. "
                    "Silakan coba unggah ulang."
                ),
            ) from exc

        logger.error(
            "Kegagalan komunikasi ke layanan Gemini API pada model '%s' (%s).",
            model_name,
            type(exc).__name__,
        )
        raise AIServiceUnavailableError(status_code=503) from exc


def _generate_with_retry_and_fallback(
    client: Any,
    image_part: types.Part,
    generation_config: types.GenerateContentConfig,
) -> Any:
    """Jalankan generate_content dengan retry exponential backoff dan fallback model untuk 429/503."""
    primary_model = (
        (app_config.GEMINI_MODEL or "").strip() or app_config.DEFAULT_GEMINI_MODEL
    )
    fallback_model = app_config.get_gemini_fallback_model()
    has_fallback = bool(fallback_model and fallback_model != primary_model)

    last_transient_exc: genai_errors.APIError | None = None

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            return _call_model_once(
                client=client,
                model_name=primary_model,
                image_part=image_part,
                generation_config=generation_config,
            )
        except genai_errors.APIError as exc:
            last_transient_exc = exc
            if attempt < MAX_RETRY_ATTEMPTS:
                delay_seconds = RETRY_BACKOFF_SECONDS[attempt - 1]
                logger.warning(
                    "Error sementara Gemini API pada model '%s' "
                    "(percobaan %d/%d, kode HTTP %s, status %s, tipe %s). "
                    "Mencoba ulang dalam %.1f detik.",
                    primary_model,
                    attempt,
                    MAX_RETRY_ATTEMPTS,
                    exc.code,
                    exc.status,
                    type(exc).__name__,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
            else:
                logger.warning(
                    "Error sementara Gemini API pada model '%s' "
                    "(percobaan %d/%d habis, kode HTTP %s, status %s, tipe %s).",
                    primary_model,
                    attempt,
                    MAX_RETRY_ATTEMPTS,
                    exc.code,
                    exc.status,
                    type(exc).__name__,
                )

    if has_fallback and fallback_model is not None:
        fallback_delay = RETRY_BACKOFF_SECONDS[min(MAX_RETRY_ATTEMPTS - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
        logger.warning(
            "Seluruh %d percobaan pada model utama '%s' gagal karena error sementara; "
            "menunggu %.1f detik lalu mencoba fallback model '%s'.",
            MAX_RETRY_ATTEMPTS,
            primary_model,
            fallback_delay,
            fallback_model,
        )
        time.sleep(fallback_delay)
        try:
            return _call_model_once(
                client=client,
                model_name=fallback_model,
                image_part=image_part,
                generation_config=generation_config,
            )
        except genai_errors.APIError as fallback_exc:
            logger.error(
                "Fallback model '%s' juga gagal karena error sementara "
                "(kode HTTP %s, status %s, tipe %s).",
                fallback_model,
                fallback_exc.code,
                fallback_exc.status,
                type(fallback_exc).__name__,
            )
            _raise_unavailable_from_transient_error(fallback_exc)

    assert last_transient_exc is not None
    _raise_unavailable_from_transient_error(last_transient_exc)


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
    response = _generate_with_retry_and_fallback(
        client=client,
        image_part=image_part,
        generation_config=generation_config,
    )

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
