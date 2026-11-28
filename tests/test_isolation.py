"""Integration & security tests untuk isolasi ketat data antar-pengguna (M3.2)."""

from collections.abc import Iterator
import csv
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend.main import app
from backend.schemas.receipt import (
    ExtractedItem,
    ReceiptExtractResponse,
    ReceiptPreviewData,
)
from backend.services import ai_service


def _sample_jpeg_bytes() -> bytes:
    """Buat bytes JPEG valid berukuran kecil untuk pengujian upload & arsip struk."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (240, 240, 240)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def two_user_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, TestClient, Path]]:
    """Buat dua sesi TestClient terpisah (User A & User B) berbagi DB dan UPLOADS_DIR yang sama."""
    db_file = tmp_path / "shared_multiuser.db"
    uploads_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    monkeypatch.setenv("UPLOADS_DIR", str(uploads_dir))

    with TestClient(app) as client_a, TestClient(app) as client_b:
        reg_a = client_a.post(
            "/api/auth/register",
            json={"email": "usera@example.com", "password": "passwordA123"},
        )
        reg_b = client_b.post(
            "/api/auth/register",
            json={"email": "userb@example.com", "password": "passwordB123"},
        )
        assert reg_a.status_code == 201
        assert reg_b.status_code == 201
        yield client_a, client_b, uploads_dir


class TestMultiUserDataIsolation:
    """Pastikan User A dan User B terisolasi total pada transaksi, summary, CSV, & arsip struk."""

    def test_transactions_summary_csv_mutations_and_receipt_archive_isolated(
        self,
        two_user_clients: tuple[TestClient, TestClient, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client_a, client_b, _uploads_dir = two_user_clients

        monkeypatch.setattr(
            ai_service,
            "extract_receipt_from_image",
            lambda **_kw: ReceiptExtractResponse(
                data=ReceiptPreviewData(
                    date="2026-11-26",
                    items=[
                        ExtractedItem(
                            name="Belanja Rahasia User A",
                            price=75000,
                            category="Kebutuhan Pokok",
                        )
                    ],
                ),
                warnings=[],
            ),
        )

        # User A scan & simpan transaksi berarsip struk
        extract_a = client_a.post(
            "/api/receipts/extract",
            files={"file": ("struk_a.jpg", _sample_jpeg_bytes(), "image/jpeg")},
        )
        assert extract_a.status_code == 200
        token_a = extract_a.json()["temp_image_token"]

        save_a = client_a.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [
                    {
                        "name": "Belanja Rahasia User A",
                        "price": 75000,
                        "category": "Kebutuhan Pokok",
                    }
                ],
                "temp_image_token": token_a,
            },
        )
        assert save_a.status_code == 201
        tx_a_id = save_a.json()["data"]["transaction_id"]
        item_a_id = save_a.json()["data"]["items"][0]["id"]

        # User B simpan transaksi miliknya sendiri
        save_b = client_b.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [
                    {
                        "name": "Parkir User B",
                        "price": 5000,
                        "category": "Transportasi",
                    }
                ],
            },
        )
        assert save_b.status_code == 201

        # 1. GET /api/transactions terisolasi penuh
        list_a = client_a.get("/api/transactions").json()
        list_b = client_b.get("/api/transactions").json()
        assert [r["name"] for r in list_a["data"]] == ["Belanja Rahasia User A"]
        assert [r["name"] for r in list_b["data"]] == ["Parkir User B"]

        # 2. GET /api/summary/monthly terisolasi penuh
        sum_a = client_a.get(
            "/api/summary/monthly", params={"month": 11, "year": 2026}
        ).json()
        sum_b = client_b.get(
            "/api/summary/monthly", params={"month": 11, "year": 2026}
        ).json()
        assert sum_a["total_expense"] == 75000
        assert sum_a["total_items"] == 1
        assert sum_b["total_expense"] == 5000
        assert sum_b["total_items"] == 1

        # 3. GET /api/transactions/export CSV User B tidak mengandung data User A
        csv_b = client_b.get("/api/transactions/export")
        assert csv_b.status_code == 200
        rows_b = list(csv.reader(io.StringIO(csv_b.content.decode("utf-8-sig"))))
        assert rows_b == [
            ["Tanggal", "Nama Barang", "Kategori", "Harga"],
            ["2026-11-26", "Parkir User B", "Transportasi", "5000"],
        ]

        # 4. User B dilarang mengedit, menghapus item/transaksi, atau mengintip arsip struk User A
        assert (
            client_b.put(f"/api/items/{item_a_id}", json={"price": 1}).status_code
            == 404
        )
        assert client_b.delete(f"/api/items/{item_a_id}").status_code == 404
        assert client_b.delete(f"/api/transactions/{tx_a_id}").status_code == 404
        assert client_b.get(f"/api/transactions/{tx_a_id}/receipt").status_code == 404

        # 5. Pastikan data & file arsip foto struk User A tetap 100% utuh
        verify_a_list = client_a.get("/api/transactions").json()
        assert verify_a_list["count"] == 1
        assert verify_a_list["data"][0]["price"] == 75000
        receipt_a_resp = client_a.get(f"/api/transactions/{tx_a_id}/receipt")
        assert receipt_a_resp.status_code == 200
        assert receipt_a_resp.content.startswith(b"\xff\xd8\xff")

    def test_temp_image_token_cannot_be_claimed_by_another_user(
        self,
        two_user_clients: tuple[TestClient, TestClient, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client_a, client_b, _uploads_dir = two_user_clients

        monkeypatch.setattr(
            ai_service,
            "extract_receipt_from_image",
            lambda **_kw: ReceiptExtractResponse(
                data=ReceiptPreviewData(
                    date="2026-11-26",
                    items=[ExtractedItem(name="Susu UHT", price=12000)],
                ),
                warnings=[],
            ),
        )

        ext_a = client_a.post(
            "/api/receipts/extract",
            files={"file": ("struk_a.jpg", _sample_jpeg_bytes(), "image/jpeg")},
        )
        assert ext_a.status_code == 200
        token_a = ext_a.json()["temp_image_token"]

        # User B mencoba mencuri temp_image_token milik User A -> harus gagal 400
        steal_resp = client_b.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [{"name": "Item Bajakan", "price": 1000}],
                "temp_image_token": token_a,
            },
        )
        assert steal_resp.status_code == 400
        assert steal_resp.json()["error_code"] == "RECEIPT_TEMP_NOT_FOUND"
        assert client_b.get("/api/transactions").json()["count"] == 0

        # Pemilik asli (User A) tetap dapat mengarsipkan token tersebut dengan sukses
        own_save = client_a.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [{"name": "Susu UHT", "price": 12000}],
                "temp_image_token": token_a,
            },
        )
        assert own_save.status_code == 201
        assert own_save.json()["data"]["has_receipt"] is True
