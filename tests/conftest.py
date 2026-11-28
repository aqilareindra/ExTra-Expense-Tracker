"""Konfigurasi fixture global pytest agar test lokal selalu terisolasi dari PostgreSQL eksternal."""

import pytest

from backend import config as app_config


@pytest.fixture(autouse=True)
def _force_isolated_sqlite_unless_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kosongkan DATABASE_URL secara default di pytest agar seluruh test memakai SQLite tmp_path."""
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(app_config, "DATABASE_URL", "")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-pytest-32bytes")
    monkeypatch.setattr(
        app_config,
        "JWT_SECRET",
        "test-jwt-secret-key-for-pytest-32bytes",
    )
