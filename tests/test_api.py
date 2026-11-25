"""Integration test endpoint FastAPI Milestone 1 s/d Milestone 5."""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from google.genai import errors as genai_errors
import pytest

from backend import config as app_config
from backend.config import BASE_DIR, ConfigurationError
from backend.main import app
from backend.schemas.receipt import (
    ExtractedItem,
    ReceiptExtractResponse,
    ReceiptPreviewData,
)
from backend.services import ai_service


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Jalankan TestClient dengan database SQLite terisolasi tanpa menyentuh extra.db."""
    test_db_file = tmp_path / "test_api.db"
    monkeypatch.setenv("DATABASE_PATH", str(test_db_file))
    with TestClient(app) as api_client:
        yield api_client


def test_health_check_endpoint(client: TestClient) -> None:
    main_db = BASE_DIR / "extra.db"
    existed_before = main_db.exists()
    mtime_before = main_db.stat().st_mtime_ns if existed_before else None

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ExTra API"}

    if not existed_before:
        assert not main_db.exists()
    else:
        assert main_db.stat().st_mtime_ns == mtime_before


def test_create_and_list_transactions_flow(client: TestClient) -> None:
    main_db = BASE_DIR / "extra.db"
    mtime_before = main_db.stat().st_mtime_ns if main_db.exists() else None

    create_resp = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-24",
            "items": [
                {"name": "  Indomie Goreng  ", "price": 3500},
                {"name": "Aqua 600ml", "price": 4000},
            ],
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["status"] == "success"
    assert body["data"]["date"] == "2026-11-24"
    assert len(body["data"]["items"]) == 2
    assert body["data"]["items"][0]["name"] == "Indomie Goreng"

    list_resp = client.get("/api/transactions")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["status"] == "success"
    assert list_body["count"] == 2
    assert [row["name"] for row in list_body["data"]] == [
        "Aqua 600ml",
        "Indomie Goreng",
    ]

    if mtime_before is None:
        assert not main_db.exists()
    else:
        assert main_db.stat().st_mtime_ns == mtime_before


def test_get_transactions_filters_and_search(client: TestClient) -> None:
    client.post(
        "/api/transactions",
        json={
            "date": "2026-10-12",
            "items": [{"name": "Kopi Hitam", "price": 12000}],
        },
    )
    client.post(
        "/api/transactions",
        json={
            "date": "2026-11-24",
            "items": [
                {"name": "Roti Coklat", "price": 8500},
                {"name": "Kopi Susu", "price": 15000},
            ],
        },
    )

    nov_resp = client.get("/api/transactions", params={"month": 11, "year": 2026})
    assert nov_resp.status_code == 200
    assert nov_resp.json()["count"] == 2

    search_resp = client.get("/api/transactions", params={"search": "KOPI"})
    assert search_resp.status_code == 200
    assert [r["name"] for r in search_resp.json()["data"]] == [
        "Kopi Susu",
        "Kopi Hitam",
    ]

    bad_month_resp = client.get("/api/transactions", params={"month": 13})
    assert bad_month_resp.status_code == 422
    assert bad_month_resp.json()["status"] == "error"
    assert bad_month_resp.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"date": "2026-02-30", "items": [{"name": "Aqua", "price": 4000}]},
        {"date": "2026-11-24", "items": []},
        {"date": "2026-11-24", "items": [{"name": "   ", "price": 4000}]},
        {"date": "2026-11-24", "items": [{"name": "Aqua", "price": -500}]},
        {"date": "2026-11-24", "items": [{"name": "Aqua", "price": 4000.5}]},
    ],
)
def test_create_transaction_validation_errors_return_consistent_422(
    client: TestClient, invalid_payload: dict[str, object]
) -> None:
    resp = client.post("/api/transactions", json=invalid_payload)
    assert resp.status_code == 422
    err = resp.json()
    assert err["status"] == "error"
    assert err["error_code"] == "VALIDATION_ERROR"
    assert isinstance(err["message"], str) and err["message"]

    # Pastikan tidak ada data korup yang masuk ke database
    assert client.get("/api/transactions").json()["count"] == 0


def test_update_item_and_not_found_handling(client: TestClient) -> None:
    created = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-20",
            "items": [
                {"name": "Susu Kotak", "price": 6000},
                {"name": "Biskuit", "price": 9000},
            ],
        },
    ).json()["data"]
    first_item_id = created["items"][0]["id"]

    update_resp = client.put(
        f"/api/items/{first_item_id}",
        json={"name": "Susu Full Cream", "price": 7500, "date": "2026-11-22"},
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()["data"]
    assert updated_data["name"] == "Susu Full Cream"
    assert updated_data["price"] == 7500
    assert updated_data["date"] == "2026-11-22"
    assert updated_data["transaction_id"] != created["transaction_id"]

    empty_update = client.put(f"/api/items/{first_item_id}", json={})
    assert empty_update.status_code == 422
    assert empty_update.json()["error_code"] == "VALIDATION_ERROR"

    not_found_resp = client.put("/api/items/99999", json={"price": 5000})
    assert not_found_resp.status_code == 404
    assert not_found_resp.json() == {
        "status": "error",
        "error_code": "NOT_FOUND",
        "message": "Item dengan ID 99999 tidak ditemukan.",
    }


def test_delete_item_orphan_cleanup_and_delete_transaction_cascade(
    client: TestClient,
) -> None:
    # Uji delete_item + orphan cleanup
    single_tx = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-24",
            "items": [{"name": "Air Mineral", "price": 3500}],
        },
    ).json()["data"]
    single_item_id = single_tx["items"][0]["id"]
    single_tx_id = single_tx["transaction_id"]

    del_item_resp = client.delete(f"/api/items/{single_item_id}")
    assert del_item_resp.status_code == 200
    assert del_item_resp.json()["orphan_transaction_deleted"] is True

    # Karena orphan header sudah ikut terhapus, delete transaksi induk harus 404
    del_orphan_tx = client.delete(f"/api/transactions/{single_tx_id}")
    assert del_orphan_tx.status_code == 404
    assert del_orphan_tx.json()["error_code"] == "NOT_FOUND"

    # Uji delete item yang tidak ada -> 404
    del_missing_item = client.delete(f"/api/items/{single_item_id}")
    assert del_missing_item.status_code == 404
    assert del_missing_item.json()["error_code"] == "NOT_FOUND"

    # Uji delete_transaction cascade
    multi_tx = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-25",
            "items": [
                {"name": "Sabun", "price": 5000},
                {"name": "Shampoo", "price": 18000},
            ],
        },
    ).json()["data"]

    del_tx_resp = client.delete(f"/api/transactions/{multi_tx['transaction_id']}")
    assert del_tx_resp.status_code == 200
    assert del_tx_resp.json()["deleted_transaction_id"] == multi_tx["transaction_id"]
    assert client.get("/api/transactions").json()["count"] == 0


# ---------------------------------------------------------------------------
# Milestone 3: Integration Tests untuk POST /api/receipts/extract (Mock AI)
# ---------------------------------------------------------------------------

VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"


@pytest.mark.parametrize(
    ("filename", "mime_type", "raw_bytes"),
    [
        ("struk.jpg", "image/jpeg", VALID_JPEG_BYTES),
        ("struk.jpeg", "image/jpeg", VALID_JPEG_BYTES),
        ("struk.png", "image/png", VALID_PNG_BYTES),
    ],
)
def test_extract_receipt_success_jpeg_and_png_without_saving_to_db(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    mime_type: str,
    raw_bytes: bytes,
) -> None:
    captured_calls: list[tuple[bytes, str]] = []

    def fake_extract(image_bytes: bytes, mime_type: str) -> ReceiptExtractResponse:
        captured_calls.append((image_bytes, mime_type))
        return ReceiptExtractResponse(
            data=ReceiptPreviewData(
                date="2026-11-24",
                items=[
                    ExtractedItem(name="Indomie Goreng", price=3500),
                    ExtractedItem(name="Aqua 600ml", price=4000),
                ],
            ),
            warnings=[],
        )

    monkeypatch.setattr(ai_service, "extract_receipt_from_image", fake_extract)

    resp = client.post(
        "/api/receipts/extract",
        files={"file": (filename, raw_bytes, mime_type)},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "success",
        "data": {
            "date": "2026-11-24",
            "items": [
                {"name": "Indomie Goreng", "price": 3500},
                {"name": "Aqua 600ml", "price": 4000},
            ],
        },
        "warnings": [],
    }
    assert captured_calls == [(raw_bytes, mime_type)]

    # Pastikan POST /api/receipts/extract TIDAK menyimpan data ke SQLite
    assert client.get("/api/transactions").json()["count"] == 0


def test_extract_receipt_with_null_date_returns_warning(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModels:
        def generate_content(self, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                text=(
                    '{"is_receipt": true, "date": null, '
                    '"items": [{"name": "Roti Coklat", "price": 8500}]}'
                )
            )

    monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "dummy-test-key")
    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(models=FakeModels()),
    )

    resp = client.post(
        "/api/receipts/extract",
        files={"file": ("struk.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["date"] is None
    assert body["data"]["items"] == [{"name": "Roti Coklat", "price": 8500}]
    assert body["warnings"] == [ai_service.MISSING_DATE_WARNING]
    assert client.get("/api/transactions").json()["count"] == 0


@pytest.mark.parametrize(
    ("filename", "mime_type", "payload"),
    [
        ("catatan.txt", "text/plain", b"Ini file teks biasa"),
        ("palsu.jpg", "image/jpeg", b"Teks yang di-rename menjadi .jpg"),
        ("palsu.png", "image/png", b"Bukan header PNG asli"),
        ("salah_mime.jpg", "image/png", VALID_JPEG_BYTES),
        ("kosong.jpg", "image/jpeg", b""),
    ],
)
def test_extract_receipt_rejects_invalid_or_renamed_files_before_calling_ai(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    mime_type: str,
    payload: bytes,
) -> None:
    ai_called = False

    def should_not_be_called(**_kwargs: object) -> ReceiptExtractResponse:
        nonlocal ai_called
        ai_called = True
        raise AssertionError("ai_service tidak boleh dipanggil untuk file invalid.")

    monkeypatch.setattr(ai_service, "extract_receipt_from_image", should_not_be_called)

    resp = client.post(
        "/api/receipts/extract",
        files={"file": (filename, payload, mime_type)},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_code"] == "INVALID_FILE_TYPE"
    assert ai_called is False


def test_extract_receipt_rejects_file_larger_than_5mb(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ai_called = False

    def should_not_be_called(**_kwargs: object) -> ReceiptExtractResponse:
        nonlocal ai_called
        ai_called = True
        raise AssertionError("ai_service tidak boleh dipanggil untuk file > 5 MB.")

    monkeypatch.setattr(ai_service, "extract_receipt_from_image", should_not_be_called)

    oversized_bytes = VALID_JPEG_BYTES + (b"\x00" * (5 * 1024 * 1024))
    resp = client.post(
        "/api/receipts/extract",
        files={"file": ("besar.jpg", oversized_bytes, "image/jpeg")},
    )
    assert resp.status_code == 413
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_code"] == "FILE_TOO_LARGE"
    assert ai_called is False


def test_extract_receipt_maps_not_a_receipt_and_unreadable_receipt_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "dummy-test-key")

    # 1. Simulasi is_receipt == False -> 422 NOT_A_RECEIPT
    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kw: SimpleNamespace(
                    text=(
                        '{"is_receipt": false, "date": null, "items": [], '
                        '"error_reason": "Gambar merupakan foto pemandangan."}'
                    )
                )
            )
        ),
    )
    resp_not_receipt = client.post(
        "/api/receipts/extract",
        files={"file": ("foto.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp_not_receipt.status_code == 422
    assert resp_not_receipt.json() == {
        "status": "error",
        "error_code": "NOT_A_RECEIPT",
        "message": "Gambar merupakan foto pemandangan.",
    }

    # 2. Simulasi is_receipt == True namun items kosong -> 422 UNREADABLE_RECEIPT
    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kw: SimpleNamespace(
                    text='{"is_receipt": true, "date": "2026-11-24", "items": []}'
                )
            )
        ),
    )
    resp_unreadable = client.post(
        "/api/receipts/extract",
        files={"file": ("buram.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp_unreadable.status_code == 422
    assert resp_unreadable.json()["status"] == "error"
    assert resp_unreadable.json()["error_code"] == "UNREADABLE_RECEIPT"


def test_extract_receipt_maps_parse_unavailable_rate_limit_and_config_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Simulasi JSON rusak -> 502 AI_PARSE_ERROR
    monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "dummy-test-key")
    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kw: SimpleNamespace(text="{bukan_json_valid")
            )
        ),
    )
    resp_parse = client.post(
        "/api/receipts/extract",
        files={"file": ("struk.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp_parse.status_code == 502
    assert resp_parse.json()["error_code"] == "AI_PARSE_ERROR"

    # 2. Simulasi Timeout -> 503 AI_SERVICE_UNAVAILABLE
    def raise_timeout(**_kw: object) -> SimpleNamespace:
        raise TimeoutError("Request timed out")

    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(
            models=SimpleNamespace(generate_content=raise_timeout)
        ),
    )
    resp_timeout = client.post(
        "/api/receipts/extract",
        files={"file": ("struk.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp_timeout.status_code == 503
    assert resp_timeout.json()["error_code"] == "AI_SERVICE_UNAVAILABLE"

    # 3. Simulasi Rate Limit Gemini 429 -> 429 AI_SERVICE_UNAVAILABLE
    def raise_rate_limit(**_kw: object) -> SimpleNamespace:
        raise genai_errors.APIError(
            429,
            {"error": {"status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded"}},
        )

    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(
            models=SimpleNamespace(generate_content=raise_rate_limit)
        ),
    )
    resp_429 = client.post(
        "/api/receipts/extract",
        files={"file": ("struk.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp_429.status_code == 429
    assert resp_429.json()["error_code"] == "AI_SERVICE_UNAVAILABLE"

    # 4. Simulasi API Key belum disetel -> 500 CONFIGURATION_ERROR tanpa bocor detail sensitif
    def raise_missing_key() -> str:
        raise ConfigurationError("GEMINI_API_KEY kosong")

    monkeypatch.setattr(app_config, "get_gemini_api_key", raise_missing_key)
    resp_cfg = client.post(
        "/api/receipts/extract",
        files={"file": ("struk.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert resp_cfg.status_code == 500
    cfg_body = resp_cfg.json()
    assert cfg_body["status"] == "error"
    assert cfg_body["error_code"] == "CONFIGURATION_ERROR"
    assert "Traceback" not in cfg_body["message"]


# ---------------------------------------------------------------------------
# Milestone 4: Integration Tests untuk GET /api/summary/monthly
# ---------------------------------------------------------------------------


def test_monthly_summary_endpoint_with_data_and_empty_month(
    client: TestClient,
) -> None:
    # Bulan kosong terlebih dahulu
    empty_resp = client.get("/api/summary/monthly", params={"month": 11, "year": 2026})
    assert empty_resp.status_code == 200
    assert empty_resp.json() == {
        "status": "success",
        "month": 11,
        "year": 2026,
        "total_expense": 0,
        "total_items": 0,
        "daily_breakdown": [],
    }

    # Tambahkan transaksi di bulan lain (Oktober) dan bulan target (November)
    client.post(
        "/api/transactions",
        json={
            "date": "2026-10-30",
            "items": [{"name": "Belanja Oktober", "price": 50000}],
        },
    )
    client.post(
        "/api/transactions",
        json={
            "date": "2026-11-24",
            "items": [
                {"name": "Indomie Goreng", "price": 3500},
                {"name": "Aqua 600ml", "price": 4000},
            ],
        },
    )
    client.post(
        "/api/transactions",
        json={
            "date": "2026-11-10",
            "items": [{"name": "Kopi Susu", "price": 15000}],
        },
    )
    client.post(
        "/api/transactions",
        json={
            "date": "2026-11-24",
            "items": [{"name": "Roti Coklat", "price": 8500}],
        },
    )

    nov_resp = client.get("/api/summary/monthly", params={"month": 11, "year": 2026})
    assert nov_resp.status_code == 200
    assert nov_resp.json() == {
        "status": "success",
        "month": 11,
        "year": 2026,
        "total_expense": 31000,
        "total_items": 4,
        "daily_breakdown": [
            {"date": "2026-11-10", "total": 15000, "item_count": 1},
            {"date": "2026-11-24", "total": 16000, "item_count": 3},
        ],
    }


@pytest.mark.parametrize(
    "invalid_params",
    [
        {},
        {"month": 11},
        {"year": 2026},
        {"month": 0, "year": 2026},
        {"month": 13, "year": 2026},
        {"month": 11, "year": 99},
        {"month": 11, "year": 2200},
    ],
)
def test_monthly_summary_rejects_missing_or_invalid_query_params(
    client: TestClient,
    invalid_params: dict[str, int],
) -> None:
    resp = client.get("/api/summary/monthly", params=invalid_params)
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Milestone 5: Integration Test untuk Frontend Root & Static Assets
# ---------------------------------------------------------------------------


def test_frontend_root_and_static_assets_served(client: TestClient) -> None:
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "text/html" in root_resp.headers["content-type"]
    assert "ExTra" in root_resp.text

    css_resp = client.get("/css/styles.css")
    assert css_resp.status_code == 200
    assert "text/css" in css_resp.headers["content-type"]

    for js_file in ("api.js", "upload.js", "history.js", "summary.js"):
        js_resp = client.get(f"/js/{js_file}")
        assert js_resp.status_code == 200
