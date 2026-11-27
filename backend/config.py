"""Konfigurasi aplikasi ExTra yang dimuat dari file .env."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE_PATH)

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_DATABASE_PATH = str(BASE_DIR / "extra.db")
DEFAULT_UPLOADS_DIR = BASE_DIR / "uploads"
DEFAULT_RECEIPTS_DIR = DEFAULT_UPLOADS_DIR / "receipts"
DEFAULT_TEMP_RECEIPTS_DIR = DEFAULT_UPLOADS_DIR / "temp"
DEFAULT_TEMP_RECEIPT_TTL_SECONDS = 3600
_PLACEHOLDER_API_KEYS = {"your_gemini_api_key_here"}
_INITIAL_ENV_DATABASE_PATH = (
    os.getenv("DATABASE_PATH", "").strip() or os.getenv("DB_PATH", "").strip()
)
_INITIAL_ENV_UPLOADS_DIR = os.getenv("UPLOADS_DIR", "").strip()
_INITIAL_ENV_RECEIPTS_DIR = os.getenv("RECEIPTS_DIR", "").strip()
_INITIAL_ENV_TEMP_RECEIPTS_DIR = os.getenv("TEMP_RECEIPTS_DIR", "").strip()
_INITIAL_ENV_TEMP_TTL = os.getenv("TEMP_RECEIPT_TTL_SECONDS", "").strip()
_INITIAL_ENV_FALLBACK_MODEL: str | None = (
    os.getenv("GEMINI_FALLBACK_MODEL", "").strip() or None
)


class ConfigurationError(RuntimeError):
    """Error ketika konfigurasi wajib di sisi server belum tersedia atau tidak valid."""


GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = (
    os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
)
GEMINI_FALLBACK_MODEL: str | None = _INITIAL_ENV_FALLBACK_MODEL
DATABASE_PATH: str = _INITIAL_ENV_DATABASE_PATH or DEFAULT_DATABASE_PATH
UPLOADS_DIR: Path = (
    Path(_INITIAL_ENV_UPLOADS_DIR) if _INITIAL_ENV_UPLOADS_DIR else DEFAULT_UPLOADS_DIR
)
RECEIPTS_DIR: Path = (
    Path(_INITIAL_ENV_RECEIPTS_DIR)
    if _INITIAL_ENV_RECEIPTS_DIR
    else UPLOADS_DIR / "receipts"
)
TEMP_RECEIPTS_DIR: Path = (
    Path(_INITIAL_ENV_TEMP_RECEIPTS_DIR)
    if _INITIAL_ENV_TEMP_RECEIPTS_DIR
    else UPLOADS_DIR / "temp"
)
TEMP_RECEIPT_TTL_SECONDS: int = (
    int(_INITIAL_ENV_TEMP_TTL)
    if _INITIAL_ENV_TEMP_TTL.isdigit()
    else DEFAULT_TEMP_RECEIPT_TTL_SECONDS
)


def get_gemini_fallback_model() -> str | None:
    """Kembalikan nama model fallback Gemini jika dikonfigurasi (default None)."""
    if GEMINI_FALLBACK_MODEL != _INITIAL_ENV_FALLBACK_MODEL:
        normalized = (GEMINI_FALLBACK_MODEL or "").strip()
        return normalized or None
    env_fallback = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()
    return env_fallback or None


def get_database_path() -> str:
    """Kembalikan path file SQLite aktif (mendukung override via env DATABASE_PATH atau DB_PATH)."""
    default_or_initial = _INITIAL_ENV_DATABASE_PATH or DEFAULT_DATABASE_PATH
    if DATABASE_PATH != default_or_initial:
        return DATABASE_PATH
    env_db_path = (
        os.getenv("DATABASE_PATH", "").strip() or os.getenv("DB_PATH", "").strip()
    )
    return env_db_path or DATABASE_PATH


def get_uploads_dir() -> Path:
    """Kembalikan direktori root uploads aktif (mendukung override env UPLOADS_DIR)."""
    default_or_initial = (
        Path(_INITIAL_ENV_UPLOADS_DIR)
        if _INITIAL_ENV_UPLOADS_DIR
        else DEFAULT_UPLOADS_DIR
    )
    if UPLOADS_DIR != default_or_initial:
        return Path(UPLOADS_DIR)
    env_uploads = os.getenv("UPLOADS_DIR", "").strip()
    return Path(env_uploads) if env_uploads else default_or_initial


def get_receipts_dir() -> Path:
    """Kembalikan direktori arsip permanen struk (default <uploads>/receipts)."""
    base_uploads = (
        Path(_INITIAL_ENV_UPLOADS_DIR)
        if _INITIAL_ENV_UPLOADS_DIR
        else DEFAULT_UPLOADS_DIR
    )
    default_or_initial = (
        Path(_INITIAL_ENV_RECEIPTS_DIR)
        if _INITIAL_ENV_RECEIPTS_DIR
        else base_uploads / "receipts"
    )
    if RECEIPTS_DIR != default_or_initial:
        return Path(RECEIPTS_DIR)
    env_receipts = os.getenv("RECEIPTS_DIR", "").strip()
    if env_receipts:
        return Path(env_receipts)
    return get_uploads_dir() / "receipts"


def get_temp_receipts_dir() -> Path:
    """Kembalikan direktori sementara hasil scan struk (default <uploads>/temp)."""
    base_uploads = (
        Path(_INITIAL_ENV_UPLOADS_DIR)
        if _INITIAL_ENV_UPLOADS_DIR
        else DEFAULT_UPLOADS_DIR
    )
    default_or_initial = (
        Path(_INITIAL_ENV_TEMP_RECEIPTS_DIR)
        if _INITIAL_ENV_TEMP_RECEIPTS_DIR
        else base_uploads / "temp"
    )
    if TEMP_RECEIPTS_DIR != default_or_initial:
        return Path(TEMP_RECEIPTS_DIR)
    env_temp = os.getenv("TEMP_RECEIPTS_DIR", "").strip()
    if env_temp:
        return Path(env_temp)
    return get_uploads_dir() / "temp"


def get_temp_receipt_ttl_seconds() -> int:
    """Kembalikan batas usia TTL file sementara hasil scan dalam detik."""
    default_or_initial = (
        int(_INITIAL_ENV_TEMP_TTL)
        if _INITIAL_ENV_TEMP_TTL.isdigit()
        else DEFAULT_TEMP_RECEIPT_TTL_SECONDS
    )
    if TEMP_RECEIPT_TTL_SECONDS != default_or_initial:
        return max(1, int(TEMP_RECEIPT_TTL_SECONDS))
    env_ttl = os.getenv("TEMP_RECEIPT_TTL_SECONDS", "").strip()
    if env_ttl.isdigit():
        return max(1, int(env_ttl))
    return default_or_initial


def get_gemini_api_key() -> str:
    """Validasi dan kembalikan GEMINI_API_KEY saat dibutuhkan oleh layanan AI."""
    api_key = (GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")).strip()
    if not api_key or api_key in _PLACEHOLDER_API_KEYS:
        message = (
            "GEMINI_API_KEY kosong atau belum dikonfigurasi di file .env. "
            "Salin .env.example menjadi .env dan isi GEMINI_API_KEY yang valid."
        )
        logger.error(message)
        raise ConfigurationError(message)
    return api_key
