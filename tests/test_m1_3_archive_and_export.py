"""Integration & security tests untuk Gelombang 1 M1.3 (Ekspor CSV & Arsip Struk Lokal)."""

from collections.abc import Iterator
import csv
import io
import os
from pathlib import Path
import time
import uuid

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend.config import BASE_DIR
from backend.database import get_connection
from backend.main import app
from backend.schemas.receipt import (
    ExtractedItem,
    ReceiptExtractResponse,
    ReceiptPreviewData,
)
from backend.services import ai_service, export_service, image_service


def _make_sample_jpeg_bytes(width: int = 400, height: int = 600) -> bytes:
    """Buat gambar JPEG valid untuk simulasi unggah foto struk."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (245, 245, 245)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def isolated_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path, Path]]:
    """Sediakan TestClient dengan DATABASE_PATH & UPLOADS_DIR terisolasi di tmp_path."""
    db_file = tmp_path / "test_m1_3.db"
    uploads_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    monkeypatch.setenv("UPLOADS_DIR", str(uploads_dir))
    with TestClient(app) as api_client:
        yield api_client, db_file, uploads_dir


class TestReceiptArchiveLifecycleAndSecurity:
    """Pengujian siklus hidup arsip foto struk, TTL cleanup, dan proteksi path traversal."""

    def test_full_archive_lifecycle_and_cleanup_on_delete_and_orphan(
        self,
        isolated_env: tuple[TestClient, Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, _db_file, uploads_dir = isolated_env
        temp_dir = uploads_dir / "temp"
        receipts_dir = uploads_dir / "receipts"

        monkeypatch.setattr(
            ai_service,
            "extract_receipt_from_image",
            lambda **_kw: ReceiptExtractResponse(
                data=ReceiptPreviewData(
                    date="2026-11-26",
                    items=[
                        ExtractedItem(
                            name="Kopi Susu",
                            price=18000,
                            category="Makanan & Minuman",
                        ),
                        ExtractedItem(
                            name="Roti Keju",
                            price=12000,
                            category="Makanan & Minuman",
                        ),
                    ],
                ),
                warnings=[],
            ),
        )

        # 1. Extract menyimpan file terkompresi di uploads/temp/{token}.jpg
        extract_resp = client.post(
            "/api/receipts/extract",
            files={"file": ("struk_hp.jpg", _make_sample_jpeg_bytes(), "image/jpeg")},
        )
        assert extract_resp.status_code == 200
        extract_body = extract_resp.json()
        token = extract_body["temp_image_token"]
        assert str(uuid.UUID(token)) == token
        temp_file = temp_dir / f"{token}.jpg"
        assert temp_file.is_file()

        # 2. Simpan transaksi dengan temp_image_token -> pindah ke uploads/receipts/
        save_resp = client.post(
            "/api/transactions",
            json={
                "date": extract_body["data"]["date"],
                "items": extract_body["data"]["items"],
                "temp_image_token": token,
            },
        )
        assert save_resp.status_code == 201
        saved_data = save_resp.json()["data"]
        tx_id = saved_data["transaction_id"]
        item_1_id = saved_data["items"][0]["id"]
        item_2_id = saved_data["items"][1]["id"]
        assert saved_data["has_receipt"] is True
        assert not temp_file.exists()

        archived_files = list(receipts_dir.glob("*.jpg"))
        assert len(archived_files) == 1

        # 3. GET /api/transactions mengembalikan has_receipt=True tanpa path server
        list_resp = client.get("/api/transactions")
        assert list_resp.status_code == 200
        for row in list_resp.json()["data"]:
            assert row["has_receipt"] is True
            assert "receipt_image_path" not in row

        # 4. GET /api/transactions/{id}/receipt mengembalikan image/jpeg valid
        img_resp = client.get(f"/api/transactions/{tx_id}/receipt")
        assert img_resp.status_code == 200
        assert img_resp.headers["content-type"].startswith("image/jpeg")
        assert img_resp.content.startswith(b"\xff\xd8\xff")

        # 5. Split transaksi via PUT /api/items/{id} (ubah tanggal item 1) TIDAK boleh hapus struk induk
        split_resp = client.put(
            f"/api/items/{item_1_id}",
            json={"date": "2026-11-27"},
        )
        assert split_resp.status_code == 200
        assert split_resp.json()["data"]["has_receipt"] is False
        assert archived_files[0].is_file()
        assert client.get(f"/api/transactions/{tx_id}/receipt").status_code == 200

        # 6. Hapus item terakhir pada transaksi induk (orphan cleanup) -> file arsip ikut terhapus
        del_last_resp = client.delete(f"/api/items/{item_2_id}")
        assert del_last_resp.status_code == 200
        assert del_last_resp.json()["orphan_transaction_deleted"] is True
        assert not archived_files[0].exists()
        assert client.get(f"/api/transactions/{tx_id}/receipt").status_code == 404

        # 7. Uji DELETE /api/transactions/{id} juga menghapus file fisik arsip struk
        extract_2 = client.post(
            "/api/receipts/extract",
            files={"file": ("struk_2.jpg", _make_sample_jpeg_bytes(), "image/jpeg")},
        ).json()
        save_2 = client.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [{"name": "Air Mineral", "price": 4000}],
                "temp_image_token": extract_2["temp_image_token"],
            },
        ).json()["data"]
        tx_2_id = save_2["transaction_id"]
        archived_2 = list(receipts_dir.glob("*.jpg"))
        assert len(archived_2) == 1

        del_tx_2 = client.delete(f"/api/transactions/{tx_2_id}")
        assert del_tx_2.status_code == 200
        assert not archived_2[0].exists()

    def test_expired_or_missing_temp_token_returns_400_and_ttl_cleanup_preserves_fresh(
        self,
        isolated_env: tuple[TestClient, Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client, _db_file, uploads_dir = isolated_env
        temp_dir = uploads_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        expired_file = temp_dir / f"{uuid.uuid4()}.jpg"
        fresh_file = temp_dir / f"{uuid.uuid4()}.jpg"
        expired_file.write_bytes(_make_sample_jpeg_bytes(10, 10))
        fresh_file.write_bytes(_make_sample_jpeg_bytes(10, 10))

        now_ts = time.time()
        os.utime(expired_file, (now_ts - 7200, now_ts - 7200))
        os.utime(fresh_file, (now_ts - 30, now_ts - 30))

        removed = image_service.cleanup_expired_temp_images(
            ttl_seconds=3600, now_ts=now_ts
        )
        assert removed == 1
        assert not expired_file.exists()
        assert fresh_file.is_file()

        # Token UUID valid yang tidak ada / sudah kedaluwarsa harus membalas 400 RECEIPT_TEMP_NOT_FOUND
        monkeypatch.setenv("TEMP_RECEIPT_TTL_SECONDS", "3600")
        missing_token = str(uuid.uuid4())
        resp = client.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [{"name": "Parkir", "price": 2000}],
                "temp_image_token": missing_token,
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "RECEIPT_TEMP_NOT_FOUND"

    def test_rejects_path_traversal_tokens_and_hides_server_paths_on_404(
        self,
        isolated_env: tuple[TestClient, Path, Path],
    ) -> None:
        client, db_file, _uploads_dir = isolated_env

        # 1. Token path traversal ditolak 422 pada POST /api/transactions dan 400 pada service
        for bad_token in ["../../.env", "..\\backend\\config.py", "bukan-uuid"]:
            api_resp = client.post(
                "/api/transactions",
                json={
                    "date": "2026-11-26",
                    "items": [{"name": "Parkir", "price": 2000}],
                    "temp_image_token": bad_token,
                },
            )
            assert api_resp.status_code == 422
            assert api_resp.json()["error_code"] == "VALIDATION_ERROR"

            with pytest.raises(image_service.InvalidTempTokenError) as svc_exc:
                image_service.promote_temp_receipt_to_archive(bad_token)
            assert svc_exc.value.status_code == 400

        # 2. Transaksi manual tanpa foto struk -> has_receipt=False & GET receipt -> 404 aman
        manual_tx = client.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [{"name": "Parkir Tunai", "price": 3000}],
            },
        ).json()["data"]
        assert manual_tx["has_receipt"] is False
        assert manual_tx["items"][0]["has_receipt"] is False

        no_receipt_resp = client.get(
            f"/api/transactions/{manual_tx['transaction_id']}/receipt"
        )
        assert no_receipt_resp.status_code == 404
        assert no_receipt_resp.json()["error_code"] == "NOT_FOUND"
        assert str(BASE_DIR) not in no_receipt_resp.text
        assert str(db_file.parent) not in no_receipt_resp.text

        # 3. ID tidak ada -> 404 tanpa kebocoran path
        missing_resp = client.get("/api/transactions/99999/receipt")
        assert missing_resp.status_code == 404
        assert str(BASE_DIR) not in missing_resp.text

        # 4. Simulasi record DB dimanipulasi path traversal -> tetap ditolak 404 aman
        conn = get_connection(db_file)
        try:
            conn.execute(
                "UPDATE transactions SET receipt_image_path = '../../.env' WHERE id = ?",
                (manual_tx["transaction_id"],),
            )
            conn.commit()
        finally:
            conn.close()

        tampered_resp = client.get(
            f"/api/transactions/{manual_tx['transaction_id']}/receipt"
        )
        assert tampered_resp.status_code == 404
        assert tampered_resp.json()["error_code"] == "NOT_FOUND"


class TestCsvExportServiceAndEndpoint:
    """Pengujian ekspor CSV UTF-8 BOM, header kolom, filter periode/kategori/search, & dataset kosong."""

    def test_export_csv_utf8_bom_headers_filters_and_empty_dataset(
        self,
        isolated_env: tuple[TestClient, Path, Path],
    ) -> None:
        client, _db_file, _uploads_dir = isolated_env

        # 1. Dataset kosong -> tetap mengembalikan CSV valid dengan UTF-8 BOM & baris header
        empty_resp = client.get("/api/transactions/export")
        assert empty_resp.status_code == 200
        assert empty_resp.headers["content-type"].lower() == "text/csv; charset=utf-8"
        assert (
            empty_resp.headers["content-disposition"]
            == 'attachment; filename="extra-pengeluaran-semua.csv"'
        )
        assert empty_resp.content.startswith(b"\xef\xbb\xbf")
        empty_rows = list(csv.reader(io.StringIO(empty_resp.content.decode("utf-8-sig"))))
        assert empty_rows == [["Tanggal", "Nama Barang", "Kategori", "Harga"]]

        # 2. Isi data lintas bulan & kategori
        client.post(
            "/api/transactions",
            json={
                "date": "2026-10-15",
                "items": [
                    {
                        "name": "Beras 5kg",
                        "price": 68000,
                        "category": "Kebutuhan Pokok",
                    }
                ],
            },
        )
        client.post(
            "/api/transactions",
            json={
                "date": "2026-11-20",
                "items": [
                    {
                        "name": "Kopi Susu",
                        "price": 18000,
                        "category": "Makanan & Minuman",
                    },
                    {
                        "name": "MRT Jakarta",
                        "price": 14000,
                        "category": "Transportasi",
                    },
                ],
            },
        )
        client.post(
            "/api/transactions",
            json={
                "date": "2026-11-26",
                "items": [
                    {
                        "name": "Kopi Hitam",
                        "price": 12000,
                        "category": "Makanan & Minuman",
                    }
                ],
            },
        )

        # 3. Ekspor terfilter month, year, category, dan search
        filtered_resp = client.get(
            "/api/transactions/export",
            params={
                "month": 11,
                "year": 2026,
                "category": "Makanan & Minuman",
                "search": "kopi",
            },
        )
        assert filtered_resp.status_code == 200
        assert filtered_resp.headers["content-type"].lower() == "text/csv; charset=utf-8"
        assert (
            filtered_resp.headers["content-disposition"]
            == 'attachment; filename="extra-pengeluaran-2026-11.csv"'
        )
        assert filtered_resp.content.startswith(b"\xef\xbb\xbf")

        rows = list(csv.reader(io.StringIO(filtered_resp.content.decode("utf-8-sig"))))
        assert rows == [
            ["Tanggal", "Nama Barang", "Kategori", "Harga"],
            ["2026-11-26", "Kopi Hitam", "Makanan & Minuman", "12000"],
            ["2026-11-20", "Kopi Susu", "Makanan & Minuman", "18000"],
        ]

        # 4. Pastikan helper build_export_filename konsisten
        assert export_service.build_export_filename(year=2026) == "extra-pengeluaran-2026.csv"
        assert (
            export_service.build_export_filename(month=5)
            == "extra-pengeluaran-bulan-05.csv"
        )
