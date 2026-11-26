"""Unit test untuk auto-retry exponential backoff dan fallback model di ai_service (M1.1)."""

import logging
from types import SimpleNamespace

from google.genai import errors as genai_errors
import pytest

from backend import config as app_config
from backend.services import ai_service
from backend.services.ai_service import (
    AIConfigurationError,
    AIParseError,
    AIServiceUnavailableError,
    NotAReceiptError,
    extract_receipt_from_image,
)

SAMPLE_SUCCESS_JSON = (
    '{"is_receipt": true, "date": "2026-11-26", '
    '"items": [{"name": "Indomie Goreng", "price": 3500}, '
    '{"name": "Aqua 600ml", "price": 4000}]}'
)
SAMPLE_IMAGE_BYTES = b"\xff\xd8\xff\xdbdummy_compressed_jpeg"


def _make_api_error(code: int, status: str, message: str) -> genai_errors.APIError:
    """Bangun instance google.genai.errors.APIError untuk simulasi respons Gemini."""
    return genai_errors.APIError(
        code,
        {"error": {"status": status, "message": message}},
    )


class TestAIServiceRetryAndFallback:
    """Pengujian mekanisme retry 429/503, exponential backoff, dan GEMINI_FALLBACK_MODEL."""

    @pytest.mark.parametrize(
        ("first_err", "second_err"),
        [
            (
                _make_api_error(503, "UNAVAILABLE", "Model overloaded"),
                _make_api_error(503, "UNAVAILABLE", "Still overloaded"),
            ),
            (
                _make_api_error(429, "RESOURCE_EXHAUSTED", "Rate limit exceeded"),
                _make_api_error(429, "RESOURCE_EXHAUSTED", "Rate limit exceeded"),
            ),
            (
                _make_api_error(503, "UNAVAILABLE", "Temporary spike"),
                _make_api_error(429, "RESOURCE_EXHAUSTED", "Rate limit exceeded"),
            ),
        ],
    )
    def test_succeeds_on_third_attempt_after_two_transient_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
        first_err: genai_errors.APIError,
        second_err: genai_errors.APIError,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []
        outcomes: list[object] = [
            first_err,
            second_err,
            SimpleNamespace(text=SAMPLE_SUCCESS_JSON),
        ]

        def fake_generate_content(**kwargs: object) -> SimpleNamespace:
            called_models.append(str(kwargs["model"]))
            nxt = outcomes.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt  # type: ignore[return-value]

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=fake_generate_content)
            ),
        )

        response = extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert response.status == "success"
        assert response.data.date == "2026-11-26"
        assert len(response.data.items) == 2
        assert called_models == ["gemini-primary", "gemini-primary", "gemini-primary"]
        assert sleep_calls == [1.0, 2.0]

    @pytest.mark.parametrize(
        ("transient_code", "transient_status"),
        [
            (503, "UNAVAILABLE"),
            (429, "RESOURCE_EXHAUSTED"),
        ],
    )
    def test_falls_back_to_secondary_model_after_primary_exhausts_3_attempts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        transient_code: int,
        transient_status: str,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []

        def fake_generate_content(**kwargs: object) -> SimpleNamespace:
            model = str(kwargs["model"])
            called_models.append(model)
            if model == "gemini-primary":
                raise _make_api_error(transient_code, transient_status, "Busy")
            return SimpleNamespace(text=SAMPLE_SUCCESS_JSON)

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=fake_generate_content)
            ),
        )

        response = extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert response.status == "success"
        assert response.data.items[0].name == "Indomie Goreng"
        assert called_models == [
            "gemini-primary",
            "gemini-primary",
            "gemini-primary",
            "gemini-fallback",
        ]
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_raises_503_when_both_primary_and_fallback_fail_with_503(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []
        secret_api_key = "AIzaSySecretKeyNeverLeak12345"

        def always_overloaded(**kwargs: object) -> SimpleNamespace:
            called_models.append(str(kwargs["model"]))
            raise _make_api_error(503, "UNAVAILABLE", "Service unavailable")

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: secret_api_key)
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=always_overloaded)
            ),
        )

        with caplog.at_level(logging.WARNING):
            with pytest.raises(AIServiceUnavailableError) as exc_info:
                extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert exc_info.value.status_code == 503
        assert exc_info.value.error_code == "AI_SERVICE_UNAVAILABLE"
        assert called_models == [
            "gemini-primary",
            "gemini-primary",
            "gemini-primary",
            "gemini-fallback",
        ]
        assert sleep_calls == [1.0, 2.0, 4.0]
        assert "gemini-primary" in caplog.text
        assert "gemini-fallback" in caplog.text
        assert secret_api_key not in caplog.text

    @pytest.mark.parametrize("fallback_val", [None, "", "   ", "gemini-primary"])
    def test_skips_fallback_when_unconfigured_or_same_as_primary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fallback_val: str | None,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []

        def always_503(**kwargs: object) -> SimpleNamespace:
            called_models.append(str(kwargs["model"]))
            raise _make_api_error(503, "UNAVAILABLE", "Service unavailable")

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", fallback_val)
        monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=always_503)
            ),
        )

        with pytest.raises(AIServiceUnavailableError) as exc_info:
            extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert exc_info.value.status_code == 503
        assert exc_info.value.error_code == "AI_SERVICE_UNAVAILABLE"
        assert called_models == ["gemini-primary", "gemini-primary", "gemini-primary"]
        assert sleep_calls == [1.0, 2.0]


class TestAIServiceNonTransientNoRetry:
    """Pastikan error non-sementara gagal langsung tanpa retry dan tanpa fallback."""

    def test_http_400_error_fails_immediately_without_retry_or_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []

        def raise_400(**kwargs: object) -> SimpleNamespace:
            called_models.append(str(kwargs["model"]))
            raise _make_api_error(400, "INVALID_ARGUMENT", "Malformed image payload")

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=raise_400)
            ),
        )

        with pytest.raises(AIServiceUnavailableError):
            extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert called_models == ["gemini-primary"]
        assert sleep_calls == []

    def test_auth_401_or_403_fails_immediately_without_retry_or_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []

        def raise_403(**kwargs: object) -> SimpleNamespace:
            called_models.append(str(kwargs["model"]))
            raise _make_api_error(403, "PERMISSION_DENIED", "API key not valid")

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=raise_403)
            ),
        )

        with pytest.raises(AIConfigurationError) as exc_info:
            extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "CONFIGURATION_ERROR"
        assert called_models == ["gemini-primary"]
        assert sleep_calls == []

    def test_malformed_json_parse_error_fails_immediately_without_retry(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []

        def return_bad_json(**kwargs: object) -> SimpleNamespace:
            called_models.append(str(kwargs["model"]))
            return SimpleNamespace(text="{json_rusak_bukan_valid")

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=return_bad_json)
            ),
        )

        with pytest.raises(AIParseError) as exc_info:
            extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert exc_info.value.status_code == 502
        assert exc_info.value.error_code == "AI_PARSE_ERROR"
        assert called_models == ["gemini-primary"]
        assert sleep_calls == []

    def test_not_a_receipt_validation_fails_immediately_without_retry(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sleep_calls: list[float] = []
        called_models: list[str] = []

        def return_not_receipt(**kwargs: object) -> SimpleNamespace:
            called_models.append(str(kwargs["model"]))
            return SimpleNamespace(
                text=(
                    '{"is_receipt": false, "date": null, "items": [], '
                    '"error_reason": "Gambar merupakan foto kucing."}'
                )
            )

        monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "test-safe-key")
        monkeypatch.setattr(app_config, "GEMINI_MODEL", "gemini-primary")
        monkeypatch.setattr(app_config, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
        monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
        monkeypatch.setattr(
            ai_service,
            "_create_genai_client",
            lambda _key: SimpleNamespace(
                models=SimpleNamespace(generate_content=return_not_receipt)
            ),
        )

        with pytest.raises(NotAReceiptError) as exc_info:
            extract_receipt_from_image(SAMPLE_IMAGE_BYTES, "image/jpeg")

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_code == "NOT_A_RECEIPT"
        assert called_models == ["gemini-primary"]
        assert sleep_calls == []
