"""Unit & integration tests untuk sistem autentikasi multi-user & konfigurasi dual-mode DB (M3.2)."""

from collections.abc import Iterator
from datetime import timedelta
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend import config as app_config
from backend.database import get_connection, resolve_database_url
from backend.main import app
from backend.services import auth_service


@pytest.fixture()
def auth_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path]]:
    """Sediakan TestClient bersih tanpa login dengan SQLite & uploads terisolasi."""
    db_file = tmp_path / "test_auth.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    with TestClient(app) as client:
        yield client, db_file


class TestDualModeDatabaseConfig:
    """Verifikasi normalisasi DATABASE_URL PostgreSQL dan fallback ke SQLite lokal."""

    def test_database_url_normalizes_postgres_schemes_and_falls_back_to_sqlite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        local_db = tmp_path / "fallback.db"
        monkeypatch.setenv("DATABASE_URL", "")
        monkeypatch.setattr(app_config, "DATABASE_URL", "")
        monkeypatch.setenv("DATABASE_PATH", str(local_db))

        assert app_config.get_database_url() == ""
        assert resolve_database_url().startswith("sqlite:///")

        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@db:5432/extra")
        assert (
            app_config.get_database_url()
            == "postgresql+psycopg://user:pass@db:5432/extra"
        )
        assert (
            resolve_database_url()
            == "postgresql+psycopg://user:pass@db:5432/extra"
        )

        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/extra")
        assert (
            app_config.get_database_url()
            == "postgresql+psycopg://user:pass@db:5432/extra"
        )


class TestAuthEndpointsAndSecurity:
    """Pengujian register, login, logout, /me, JWT, cookie HttpOnly, & proteksi endpoint."""

    def test_register_normalizes_email_sets_cookie_and_never_exposes_password_hash(
        self, auth_client: tuple[TestClient, Path]
    ) -> None:
        client, db_file = auth_client

        resp = client.post(
            "/api/auth/register",
            json={"email": "  Raka.Putra@Example.COM ", "password": "PasswordKuat123"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["email"] == "raka.putra@example.com"
        assert isinstance(body["data"]["id"], int)
        assert "password_hash" not in body["data"]
        assert "PasswordKuat123" not in resp.text

        set_cookie_header = resp.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie_header
        assert "httponly" in set_cookie_header.lower()

        # Pastikan password tersimpan sebagai hash bcrypt di database, bukan plaintext
        conn = get_connection(db_file)
        try:
            row = conn.execute(
                "SELECT email, password_hash FROM users WHERE id = ?",
                (body["data"]["id"],),
            ).fetchone()
            assert row is not None
            assert row["email"] == "raka.putra@example.com"
            assert row["password_hash"] != "PasswordKuat123"
            assert row["password_hash"].startswith("$2")
        finally:
            conn.close()

        # /api/auth/me otomatis berhasil karena cookie HttpOnly aktif
        me_resp = client.get("/api/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["data"]["email"] == "raka.putra@example.com"
        assert "password_hash" not in me_resp.text

    def test_register_rejects_duplicate_email_409_short_password_422_and_bad_email_422(
        self, auth_client: tuple[TestClient, Path]
    ) -> None:
        client, _ = auth_client

        first = client.post(
            "/api/auth/register",
            json={"email": "dina@example.com", "password": "password123"},
        )
        assert first.status_code == 201

        dup = client.post(
            "/api/auth/register",
            json={"email": "DINA@EXAMPLE.COM", "password": "password999"},
        )
        assert dup.status_code == 409
        assert dup.json()["error_code"] == "EMAIL_ALREADY_EXISTS"

        short_pw = client.post(
            "/api/auth/register",
            json={"email": "baru@example.com", "password": "1234567"},
        )
        assert short_pw.status_code == 422
        assert short_pw.json()["error_code"] == "VALIDATION_ERROR"

        bad_email = client.post(
            "/api/auth/register",
            json={"email": "bukan-email", "password": "password123"},
        )
        assert bad_email.status_code == 422
        assert bad_email.json()["error_code"] == "VALIDATION_ERROR"

    def test_login_logout_me_bearer_fallback_and_invalid_tokens(
        self, auth_client: tuple[TestClient, Path]
    ) -> None:
        client, _ = auth_client

        # Register lalu logout untuk membersihkan sesi
        reg = client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "secretpassword"},
        )
        assert reg.status_code == 201
        user_id = reg.json()["data"]["id"]

        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["status"] == "success"
        assert client.get("/api/auth/me").status_code == 401

        # Login password salah -> 401 generik
        wrong_pw = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )
        assert wrong_pw.status_code == 401
        assert wrong_pw.json()["error_code"] == "INVALID_CREDENTIALS"

        # Login email tidak terdaftar -> pesan generik identik
        unknown_email = client.post(
            "/api/auth/login",
            json={"email": "tidakada@example.com", "password": "secretpassword"},
        )
        assert unknown_email.status_code == 401
        assert unknown_email.json()["error_code"] == "INVALID_CREDENTIALS"
        assert unknown_email.json()["message"] == wrong_pw.json()["message"]

        # Login sukses -> cookie aktif
        ok_login = client.post(
            "/api/auth/login",
            json={"email": "USER@example.com", "password": "secretpassword"},
        )
        assert ok_login.status_code == 200
        assert ok_login.json()["data"]["email"] == "user@example.com"
        assert client.get("/api/auth/me").status_code == 200

        # Logout ulang -> cookie terhapus
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/auth/me").status_code == 401

        # Bearer token valid tetap didukung untuk Swagger / API client
        bearer_token = auth_service.create_access_token(user_id=user_id)
        bearer_me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {bearer_token}"},
        )
        assert bearer_me.status_code == 200
        assert bearer_me.json()["data"]["id"] == user_id

        # Token kedaluwarsa & token rusak ditolak 401
        expired_token = auth_service.create_access_token(
            user_id=user_id,
            expires_delta=timedelta(seconds=-10),
        )
        assert (
            client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer invalid.jwt.token"},
            ).status_code
            == 401
        )

    def test_all_protected_endpoints_require_authentication_while_health_stays_public(
        self, auth_client: tuple[TestClient, Path]
    ) -> None:
        client, _ = auth_client

        # /health tetap publik
        assert client.get("/health").status_code == 200

        buf = io.BytesIO()
        Image.new("RGB", (4, 4), (255, 255, 255)).save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        assert client.get("/api/auth/me").status_code == 401
        assert (
            client.post(
                "/api/receipts/extract",
                files={"file": ("struk.jpg", img_bytes, "image/jpeg")},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/transactions",
                json={
                    "date": "2026-11-26",
                    "items": [{"name": "Kopi", "price": 15000}],
                },
            ).status_code
            == 401
        )
        assert client.get("/api/transactions").status_code == 401
        assert client.get("/api/transactions/export").status_code == 401
        assert client.get("/api/transactions/1/receipt").status_code == 401
        assert client.put("/api/items/1", json={"price": 1000}).status_code == 401
        assert client.delete("/api/items/1").status_code == 401
        assert client.delete("/api/transactions/1").status_code == 401
        assert (
            client.get("/api/summary/monthly", params={"month": 11, "year": 2026}).status_code
            == 401
        )
