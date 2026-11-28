"""Layanan AI Financial Insights terpisah (Jalur 2 — hanya menerima statistik agregat)."""

import logging
from pathlib import Path
import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from backend import config as app_config
from backend.schemas.budget import (
    InsightsBudgetAlertItem,
    InsightsMetricsSnapshot,
    InsightsTopCategoryItem,
    LLMInsightsOutput,
    MonthlyInsightsResponse,
)
from backend.services import budget_service, summary_service
from backend.services.prompts import (
    INSIGHTS_SYSTEM_INSTRUCTION,
    build_insights_user_prompt,
)

logger = logging.getLogger(__name__)

AI_TIMEOUT_SECONDS = 30
AI_TIMEOUT_MS = AI_TIMEOUT_SECONDS * 1000

MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
TRANSIENT_HTTP_CODES = frozenset({429, 503})
TRANSIENT_ERROR_STATUSES = frozenset({"RESOURCE_EXHAUSTED", "UNAVAILABLE"})

EMPTY_INSIGHTS_MESSAGE = (
    "Belum ada data pengeluaran maupun pemasukan pada bulan ini. "
    "Catat transaksi atau pemasukan terlebih dahulu untuk mendapatkan analisis keuangan AI."
)


class InsightsServiceError(Exception):
    """Base domain exception untuk layer AI Financial Insights."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class InsightsConfigurationError(InsightsServiceError):
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


class InsightsParseError(InsightsServiceError):
    """Error ketika respons JSON AI insights tidak sesuai skema (HTTP 502)."""

    def __init__(
        self,
        message: str = "Gagal memproses format analisis AI. Silakan coba lagi.",
    ) -> None:
        super().__init__(
            status_code=502,
            error_code="AI_PARSE_ERROR",
            message=message,
        )


class InsightsServiceUnavailableError(InsightsServiceError):
    """Error ketika Gemini API sibuk (429/503), timeout, atau tidak terjangkau (HTTP 503)."""

    def __init__(
        self,
        message: str = (
            "Layanan AI Financial Insights sedang sibuk atau tidak dapat dijangkau sementara. "
            "Silakan coba lagi beberapa saat."
        ),
    ) -> None:
        super().__init__(
            status_code=503,
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
    """Periksa apakah APIError disebabkan kredensial/API key tidak valid."""
    err_status = (exc.status or "").upper()
    err_msg_upper = (exc.message or "").upper()
    return (
        exc.code in (401, 403)
        or "API_KEY_INVALID" in err_status
        or "API_KEY_INVALID" in err_msg_upper
        or "API KEY NOT VALID" in err_msg_upper
    )


def _is_transient_api_error(exc: genai_errors.APIError) -> bool:
    """Periksa apakah APIError bersifat sementara (429 / 503)."""
    if exc.code in TRANSIENT_HTTP_CODES:
        return True
    err_status = (exc.status or "").upper()
    return exc.code is None and err_status in TRANSIENT_ERROR_STATUSES


def _previous_period(month: int, year: int) -> tuple[int, int]:
    """Hitung bulan dan tahun sebelumnya secara aman (termasuk Januari -> Desember)."""
    if month == 1:
        return 12, year - 1
    return month - 1, year


def build_metrics_snapshot(
    month: int,
    year: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> tuple[InsightsMetricsSnapshot, bool]:
    """Susun statistik agregat deterministik untuk satu user tanpa menyentuh baris item mentah."""
    current_summary = summary_service.get_monthly_summary(
        month=month,
        year=year,
        user_id=user_id,
        db_path=db_path,
    )
    income_count = budget_service.count_monthly_incomes(
        month=month,
        year=year,
        user_id=user_id,
        db_path=db_path,
    )

    prev_month, prev_year = _previous_period(month, year)
    prev_summary = summary_service.get_monthly_summary(
        month=prev_month,
        year=prev_year,
        user_id=user_id,
        db_path=db_path,
    )
    budgets = budget_service.get_budgets(
        month=month,
        year=year,
        user_id=user_id,
        db_path=db_path,
    )

    mom_change_amount = current_summary.total_expense - prev_summary.total_expense
    if prev_summary.total_expense > 0:
        mom_change_pct: float | None = round(
            (mom_change_amount / prev_summary.total_expense) * 100.0,
            2,
        )
    else:
        mom_change_pct = None

    top_categories = [
        InsightsTopCategoryItem(
            category=cat.category,
            total=cat.total,
            share_percentage=(
                round((cat.total / current_summary.total_expense) * 100.0, 2)
                if current_summary.total_expense > 0
                else 0.0
            ),
            item_count=cat.item_count,
        )
        for cat in current_summary.category_breakdown[:3]
    ]

    budget_alerts = [
        InsightsBudgetAlertItem(
            category=b.category,
            limit_amount=b.limit_amount,
            spent_amount=b.spent_amount,
            remaining_amount=b.remaining_amount,
            usage_percentage=b.usage_percentage,
            status=b.status,
        )
        for b in budgets.data
    ]

    has_data = (current_summary.total_items > 0) or (income_count > 0)
    snapshot = InsightsMetricsSnapshot(
        month=month,
        year=year,
        total_income=current_summary.total_income,
        total_expense=current_summary.total_expense,
        net_balance=current_summary.net_balance,
        total_items=current_summary.total_items,
        previous_month=prev_month,
        previous_year=prev_year,
        previous_month_expense=prev_summary.total_expense,
        mom_expense_change_amount=mom_change_amount,
        mom_expense_change_percentage=mom_change_pct,
        top_categories=top_categories,
        budget_alerts=budget_alerts,
    )
    return snapshot, has_data


def _call_insights_model_once(
    client: Any,
    model_name: str,
    user_prompt: str,
    generation_config: types.GenerateContentConfig,
) -> Any:
    """Eksekusi satu panggilan generate_content untuk analisis keuangan teragregasi."""
    try:
        return client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=generation_config,
        )
    except genai_errors.APIError as exc:
        if _is_auth_api_error(exc):
            logger.error(
                "Autentikasi Gemini API gagal untuk insights pada model '%s' (HTTP %s).",
                model_name,
                exc.code,
            )
            raise InsightsConfigurationError() from exc

        if _is_transient_api_error(exc):
            raise

        logger.error(
            "Error non-transient Gemini API untuk insights pada model '%s' (HTTP %s).",
            model_name,
            exc.code,
        )
        raise InsightsServiceUnavailableError() from exc
    except TimeoutError as exc:
        logger.warning(
            "Permintaan insights ke Gemini API pada model '%s' melewati timeout 30 detik.",
            model_name,
        )
        raise InsightsServiceUnavailableError() from exc
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Kegagalan komunikasi Gemini API untuk insights pada model '%s' (%s).",
            model_name,
            type(exc).__name__,
        )
        raise InsightsServiceUnavailableError() from exc


def _generate_insights_with_retry_and_fallback(
    client: Any,
    user_prompt: str,
    generation_config: types.GenerateContentConfig,
) -> Any:
    """Jalankan panggilan Gemini insights dengan retry exponential backoff & model fallback."""
    primary_model = (
        (app_config.GEMINI_MODEL or "").strip() or app_config.DEFAULT_GEMINI_MODEL
    )
    fallback_model = app_config.get_gemini_fallback_model()
    has_fallback = bool(fallback_model and fallback_model != primary_model)

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            return _call_insights_model_once(
                client=client,
                model_name=primary_model,
                user_prompt=user_prompt,
                generation_config=generation_config,
            )
        except genai_errors.APIError as exc:
            if attempt < MAX_RETRY_ATTEMPTS:
                delay_seconds = RETRY_BACKOFF_SECONDS[attempt - 1]
                logger.warning(
                    "Error sementara Gemini insights pada model '%s' "
                    "(percobaan %d/%d, HTTP %s). Mencoba ulang dalam %.1f detik.",
                    primary_model,
                    attempt,
                    MAX_RETRY_ATTEMPTS,
                    exc.code,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
            else:
                logger.warning(
                    "Percobaan Gemini insights pada model '%s' habis (HTTP %s).",
                    primary_model,
                    exc.code,
                )

    if has_fallback and fallback_model is not None:
        fallback_delay = RETRY_BACKOFF_SECONDS[
            min(MAX_RETRY_ATTEMPTS - 1, len(RETRY_BACKOFF_SECONDS) - 1)
        ]
        logger.warning(
            "Mencoba fallback model '%s' untuk insights setelah menunggu %.1f detik.",
            fallback_model,
            fallback_delay,
        )
        time.sleep(fallback_delay)
        try:
            return _call_insights_model_once(
                client=client,
                model_name=fallback_model,
                user_prompt=user_prompt,
                generation_config=generation_config,
            )
        except genai_errors.APIError as fallback_exc:
            logger.error(
                "Fallback model '%s' untuk insights gagal karena error sementara (HTTP %s).",
                fallback_model,
                fallback_exc.code,
            )
            raise InsightsServiceUnavailableError() from fallback_exc

    raise InsightsServiceUnavailableError()


def generate_monthly_insights(
    month: int,
    year: int,
    user_id: int,
    db_path: str | Path | None = None,
) -> MonthlyInsightsResponse:
    """Bangun statistik agregat bulan terpilih dan hasilkan narasi analisis AI secara aman."""
    snapshot, has_data = build_metrics_snapshot(
        month=month,
        year=year,
        user_id=user_id,
        db_path=db_path,
    )

    if not has_data:
        return MonthlyInsightsResponse(
            status="success",
            month=month,
            year=year,
            has_data=False,
            summary_text=EMPTY_INSIGHTS_MESSAGE,
            recommendations=[],
            metrics_snapshot=snapshot,
        )

    try:
        api_key = app_config.get_gemini_api_key()
    except app_config.ConfigurationError as exc:
        logger.error("Kredensial Gemini belum terkonfigurasi untuk AI Financial Insights.")
        raise InsightsConfigurationError() from exc

    client = _create_genai_client(api_key)
    user_prompt = build_insights_user_prompt(snapshot.model_dump_json(indent=2))
    generation_config = types.GenerateContentConfig(
        system_instruction=INSIGHTS_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=LLMInsightsOutput,
        temperature=0.1,
    )

    response = _generate_insights_with_retry_and_fallback(
        client=client,
        user_prompt=user_prompt,
        generation_config=generation_config,
    )

    raw_json = (response.text or "").strip()
    if not raw_json:
        logger.error("Gemini API mengembalikan respons kosong untuk AI insights.")
        raise InsightsParseError()

    try:
        parsed = LLMInsightsOutput.model_validate_json(raw_json)
    except (ValidationError, ValueError) as exc:
        logger.error("Gagal memvalidasi JSON AI insights (%s).", type(exc).__name__)
        raise InsightsParseError() from exc

    return MonthlyInsightsResponse(
        status="success",
        month=month,
        year=year,
        has_data=True,
        summary_text=parsed.summary_text,
        recommendations=parsed.recommendations,
        metrics_snapshot=snapshot,
    )
