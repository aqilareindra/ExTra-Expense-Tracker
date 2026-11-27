"""Integration & E2E lifecycle test endpoint FastAPI Milestone 1 s/d Milestone 6."""

from collections.abc import Iterator
import io
from pathlib import Path
import re
from types import SimpleNamespace
import uuid

from fastapi.testclient import TestClient
from google.genai import errors as genai_errors
from PIL import Image
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
    """Jalankan TestClient dengan database & direktori uploads terisolasi di tmp_path."""
    test_db_file = tmp_path / "test_api.db"
    monkeypatch.setenv("DATABASE_PATH", str(test_db_file))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
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
        {"date": "2026-02-29", "items": [{"name": "Aqua", "price": 4000}]},
        {"date": "2026-02-30", "items": [{"name": "Aqua", "price": 4000}]},
        {"date": "2026-11-24", "items": []},
        {"date": "2026-11-24", "items": [{"name": "   ", "price": 4000}]},
        {"date": "2026-11-24", "items": [{"name": "Aqua", "price": -1}]},
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

def _build_minimal_image_bytes(fmt: str) -> bytes:
    """Buat bytes gambar 1x1 yang valid secara struktural untuk pengujian endpoint."""
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format=fmt)
    return buf.getvalue()


VALID_JPEG_BYTES = _build_minimal_image_bytes("JPEG")
VALID_PNG_BYTES = _build_minimal_image_bytes("PNG")


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
    body = resp.json()
    assert str(uuid.UUID(body["temp_image_token"])) == body["temp_image_token"]
    assert body == {
        "status": "success",
        "data": {
            "date": "2026-11-24",
            "items": [
                {
                    "name": "Indomie Goreng",
                    "price": 3500,
                    "category": "Lainnya",
                },
                {
                    "name": "Aqua 600ml",
                    "price": 4000,
                    "category": "Lainnya",
                },
            ],
        },
        "warnings": [],
        "temp_image_token": body["temp_image_token"],
    }
    assert len(captured_calls) == 1
    sent_bytes, sent_mime = captured_calls[0]
    assert sent_mime == "image/jpeg"
    assert sent_bytes.startswith(b"\xff\xd8\xff")

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
    assert body["data"]["items"] == [
        {"name": "Roti Coklat", "price": 8500, "category": "Lainnya"}
    ]
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
    monkeypatch.setattr(ai_service.time, "sleep", lambda _s: None)

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
        "category_breakdown": [],
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
        "category_breakdown": [
            {"category": "Lainnya", "total": 31000, "item_count": 4},
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


# ---------------------------------------------------------------------------
# Milestone 6: Hardening & Full API Lifecycle Integration Tests
# ---------------------------------------------------------------------------


def test_zero_price_item_allowed_end_to_end(client: TestClient) -> None:
    resp = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-24",
            "items": [
                {"name": "Kantong Belanja Promo", "price": 0},
                {"name": "Roti Tawar", "price": 14000},
            ],
        },
    )
    assert resp.status_code == 201
    summary = client.get(
        "/api/summary/monthly", params={"month": 11, "year": 2026}
    ).json()
    assert summary["total_expense"] == 14000
    assert summary["total_items"] == 2


def test_full_api_lifecycle_extract_confirm_edit_delete_and_orphan_cleanup(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Ekstraksi struk via AI (mock) -> tidak boleh otomatis tersimpan ke DB
    monkeypatch.setattr(
        ai_service,
        "extract_receipt_from_image",
        lambda **_kw: ReceiptExtractResponse(
            data=ReceiptPreviewData(
                date="2026-11-18",
                items=[
                    ExtractedItem(name="Susu UHT", price=6500),
                    ExtractedItem(name="Roti Gandum", price=15000),
                ],
            ),
            warnings=[],
        ),
    )

    extract_resp = client.post(
        "/api/receipts/extract",
        files={"file": ("struk_belanja.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert extract_resp.status_code == 200
    preview = extract_resp.json()["data"]
    assert client.get("/api/transactions").json()["count"] == 0
    assert (
        client.get("/api/summary/monthly", params={"month": 11, "year": 2026}).json()[
            "total_expense"
        ]
        == 0
    )

    # 2. Pengguna mengonfirmasi & menyimpan hasil preview -> POST /api/transactions
    save_resp = client.post("/api/transactions", json=preview)
    assert save_resp.status_code == 201
    saved_data = save_resp.json()["data"]
    tx_id = saved_data["transaction_id"]
    item_1_id = saved_data["items"][0]["id"]
    item_2_id = saved_data["items"][1]["id"]

    # 3. Verifikasi riwayat & ringkasan bulanan awal (6500 + 15000 = 21500, 2 item)
    history_after_save = client.get("/api/transactions").json()
    assert history_after_save["count"] == 2

    summary_after_save = client.get(
        "/api/summary/monthly", params={"month": 11, "year": 2026}
    ).json()
    assert summary_after_save == {
        "status": "success",
        "month": 11,
        "year": 2026,
        "total_expense": 21500,
        "total_items": 2,
        "daily_breakdown": [
            {"date": "2026-11-18", "total": 21500, "item_count": 2},
        ],
        "category_breakdown": [
            {"category": "Lainnya", "total": 21500, "item_count": 2},
        ],
    }

    # 4. Edit harga & tanggal item pertama -> PUT /api/items/{id}
    edit_resp = client.put(
        f"/api/items/{item_1_id}",
        json={"name": "Susu UHT 250ml", "price": 7000, "date": "2026-11-19"},
    )
    assert edit_resp.status_code == 200
    moved_tx_id = edit_resp.json()["data"]["transaction_id"]
    assert moved_tx_id != tx_id

    summary_after_edit = client.get(
        "/api/summary/monthly", params={"month": 11, "year": 2026}
    ).json()
    assert summary_after_edit == {
        "status": "success",
        "month": 11,
        "year": 2026,
        "total_expense": 22000,
        "total_items": 2,
        "daily_breakdown": [
            {"date": "2026-11-18", "total": 15000, "item_count": 1},
            {"date": "2026-11-19", "total": 7000, "item_count": 1},
        ],
        "category_breakdown": [
            {"category": "Lainnya", "total": 22000, "item_count": 2},
        ],
    }

    # 5. Hapus kedua item -> verifikasi orphan cleanup & summary kembali ke 0
    del_1 = client.delete(f"/api/items/{item_1_id}")
    assert del_1.status_code == 200
    assert del_1.json()["orphan_transaction_deleted"] is True

    del_2 = client.delete(f"/api/items/{item_2_id}")
    assert del_2.status_code == 200
    assert del_2.json()["orphan_transaction_deleted"] is True

    # Pastikan kedua transaksi induk sudah terhapus bersih (orphan cleanup)
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 404
    assert client.delete(f"/api/transactions/{moved_tx_id}").status_code == 404
    assert client.get("/api/transactions").json()["count"] == 0

    summary_final = client.get(
        "/api/summary/monthly", params={"month": 11, "year": 2026}
    ).json()
    assert summary_final == {
        "status": "success",
        "month": 11,
        "year": 2026,
        "total_expense": 0,
        "total_items": 0,
        "daily_breakdown": [],
        "category_breakdown": [],
    }


def test_unhandled_exception_returns_generic_500_without_stack_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.services import transaction_service

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "err_test.db"))

    def explode(**_kw: object) -> list[object]:
        raise RuntimeError("sensitif_internal_path_secret_xyz")

    monkeypatch.setattr(transaction_service, "get_transactions", explode)

    with TestClient(app, raise_server_exceptions=False) as safe_client:
        resp = safe_client.get("/api/transactions")
        assert resp.status_code == 500
        body = resp.json()
        assert body["status"] == "error"
        assert body["error_code"] == "INTERNAL_SERVER_ERROR"
        assert "Traceback" not in body["message"]
        assert "sensitif_internal_path_secret_xyz" not in body["message"]


def test_extract_receipt_compresses_large_rgba_png_and_recovers_from_transient_503(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-07 E2E: Gambar PNG RGBA >1280px dikompresi ke JPEG <=1280px & pulih dari 503."""
    png_buf = io.BytesIO()
    Image.new("RGBA", (2000, 2500), (255, 255, 255, 0)).save(png_buf, format="PNG")
    large_png_bytes = png_buf.getvalue()

    sleep_calls: list[float] = []
    received_parts: list[object] = []
    attempt_counter = 0

    def flaky_generate_content(**kwargs: object) -> SimpleNamespace:
        nonlocal attempt_counter
        attempt_counter += 1
        contents = kwargs["contents"]
        assert isinstance(contents, list)
        received_parts.append(contents[0])
        if attempt_counter == 1:
            raise genai_errors.APIError(
                503,
                {"error": {"status": "UNAVAILABLE", "message": "Overloaded"}},
            )
        return SimpleNamespace(
            text=(
                '{"is_receipt": true, "date": "2026-11-26", '
                '"items": [{"name": "Roti Tawar", "price": 14000}]}'
            )
        )

    monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "dummy-test-key")
    monkeypatch.setattr(ai_service.time, "sleep", sleep_calls.append)
    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(
            models=SimpleNamespace(generate_content=flaky_generate_content)
        ),
    )

    resp = client.post(
        "/api/receipts/extract",
        files={"file": ("struk_besar.png", large_png_bytes, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert str(uuid.UUID(body["temp_image_token"])) == body["temp_image_token"]
    assert body == {
        "status": "success",
        "data": {
            "date": "2026-11-26",
            "items": [
                {"name": "Roti Tawar", "price": 14000, "category": "Lainnya"}
            ],
        },
        "warnings": [],
        "temp_image_token": body["temp_image_token"],
    }
    assert attempt_counter == 2
    assert sleep_calls == [1.0]

    inline_data = getattr(received_parts[0], "inline_data", None)
    assert inline_data is not None
    assert inline_data.mime_type == "image/jpeg"
    with Image.open(io.BytesIO(inline_data.data)) as sent_img:
        assert sent_img.format == "JPEG"
        assert sent_img.mode == "RGB"
        assert sent_img.size == (1280, 1600)


def test_m1_2_manual_entry_category_filter_update_and_ai_category_normalization(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M1.2 E2E: Input manual dengan kategori, normalisasi AI tahap 1, validasi 422 tahap 2, filter & summary."""
    # 1. AI mengembalikan kategori valid + kategori halusinasi -> dinormalisasi ke 'Lainnya'
    monkeypatch.setattr(app_config, "get_gemini_api_key", lambda: "dummy-test-key")
    monkeypatch.setattr(
        ai_service,
        "_create_genai_client",
        lambda _key: SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kw: SimpleNamespace(
                    text=(
                        '{"is_receipt": true, "date": "2026-11-26", "items": ['
                        '{"name": "Kopi Kenangan", "price": 22000, "category": "Makanan & Minuman"}, '
                        '{"name": "Baterai AA", "price": 15000, "category": "Gadget & Elektronik"}'
                        "]}"
                    )
                )
            )
        ),
    )

    ext_resp = client.post(
        "/api/receipts/extract",
        files={"file": ("struk.jpg", VALID_JPEG_BYTES, "image/jpeg")},
    )
    assert ext_resp.status_code == 200
    assert ext_resp.json()["data"]["items"] == [
        {"name": "Kopi Kenangan", "price": 22000, "category": "Makanan & Minuman"},
        {"name": "Baterai AA", "price": 15000, "category": "Lainnya"},
    ]

    # 2. Input manual tanpa struk ke POST /api/transactions (dengan & tanpa category)
    manual_resp = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-26",
            "items": [
                {
                    "name": "MRT Jakarta",
                    "price": 14000,
                    "category": "Transportasi",
                },
                {
                    "name": "Token Listrik",
                    "price": 100000,
                    "category": "Tagihan & Utilitas",
                },
                {"name": "Parkir Minimarket", "price": 2000},
            ],
        },
    )
    assert manual_resp.status_code == 201
    created_items = manual_resp.json()["data"]["items"]
    assert len(created_items) == 3
    for row in created_items:
        assert {
            "id",
            "transaction_id",
            "date",
            "name",
            "category",
            "price",
            "created_at",
        }.issubset(row.keys())
    assert [r["category"] for r in created_items] == [
        "Transportasi",
        "Tagihan & Utilitas",
        "Lainnya",
    ]

    # 3. Kategori tidak valid pada POST /api/transactions & PUT /api/items/{id} harus 422
    bad_post = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-26",
            "items": [{"name": " Kopi ", "price": 10000, "category": "Kategori Palsu"}],
        },
    )
    assert bad_post.status_code == 422
    assert bad_post.json()["error_code"] == "VALIDATION_ERROR"

    parkir_id = created_items[2]["id"]
    bad_put = client.put(
        f"/api/items/{parkir_id}",
        json={"category": "Kategori Palsu"},
    )
    assert bad_put.status_code == 422
    assert bad_put.json()["error_code"] == "VALIDATION_ERROR"

    # 4. Update kategori Parkir ke Transportasi & filter GET /api/transactions?category=Transportasi
    ok_put = client.put(
        f"/api/items/{parkir_id}",
        json={"category": "Transportasi"},
    )
    assert ok_put.status_code == 200
    assert ok_put.json()["data"]["category"] == "Transportasi"

    filtered = client.get(
        "/api/transactions",
        params={"month": 11, "year": 2026, "category": "Transportasi"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 2
    assert {r["name"] for r in filtered.json()["data"]} == {
        "MRT Jakarta",
        "Parkir Minimarket",
    }

    bad_filter = client.get("/api/transactions", params={"category": "Ngawur"})
    assert bad_filter.status_code == 422
    assert bad_filter.json()["error_code"] == "VALIDATION_ERROR"

    # 5. Verifikasi category_breakdown di GET /api/summary/monthly terurut DESC
    summary_resp = client.get(
        "/api/summary/monthly", params={"month": 11, "year": 2026}
    )
    assert summary_resp.status_code == 200
    assert summary_resp.json()["category_breakdown"] == [
        {"category": "Tagihan & Utilitas", "total": 100000, "item_count": 1},
        {"category": "Transportasi", "total": 16000, "item_count": 2},
    ]


def test_m2_2_frontend_v2_cutover_serves_dist_assets_and_falls_back_safely(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifikasi cutover frontend-v2/dist di GET /, /assets/*, route API/docs, dan fallback ke frontend/."""
    import backend.main as backend_main

    # 1. Saat frontend-v2/dist tersedia, GET / menyajikan React build dan aset /assets/*
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "text/html" in root_resp.headers["content-type"]
    assert 'id="root"' in root_resp.text
    asset_urls = re.findall(r'(/assets/[^"\'\s>]+)', root_resp.text)
    assert len(asset_urls) >= 1
    for asset_url in asset_urls:
        asset_resp = client.get(asset_url)
        assert asset_resp.status_code == 200

    # 2. Path traversal pada /assets/* wajib ditolak 404
    traversal_resp = client.get("/assets/../../.env")
    assert traversal_resp.status_code == 404

    # 3. Route /health, /docs, dan /openapi.json tetap aktif dan tidak tertimpa
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200

    # 4. Jika frontend-v2/dist belum ada, fallback aman ke frontend/index.html lama
    monkeypatch.setattr(
        backend_main,
        "FRONTEND_V2_DIST_DIR",
        tmp_path / "missing_dist",
    )
    fallback_resp = client.get("/")
    assert fallback_resp.status_code == 200
    assert "text/html" in fallback_resp.headers["content-type"]
    assert "Catat Pengeluaran" in fallback_resp.text
    assert "/assets/" not in fallback_resp.text
