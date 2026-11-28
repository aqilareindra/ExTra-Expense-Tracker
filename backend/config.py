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
DEFAULT_DEV_JWT_SECRET = "extra-local-dev-only-jwt-secret-do-not-use-in-prod-2026"
DEFAULT_JWT_EXPIRE_MINUTES = 1440
DEFAULT_COOKIE_SECURE = False
_PLACEHOLDER_API_KEYS = {"your_gemini_api_key_here"}
_PLACEHOLDER_JWT_SECRETS = {
    "change_this_to_a_strong_random_secret",
    "change_this_to_a_strong_random_secret_at_least_32_chars",
    "your_jwt_secret_here",
}
_INITIAL_ENV_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_INITIAL_ENV_DATABASE_PATH = (
    os.getenv("DATABASE_PATH", "").strip() or os.getenv("DB_PATH", "").strip()
)
_INITIAL_ENV_UPLOADS_DIR = os.getenv("UPLOADS_DIR", "").strip()
_INITIAL_ENV_RECEIPTS_DIR = os.getenv("RECEIPTS_DIR", "").strip()
_INITIAL_ENV_TEMP_RECEIPTS_DIR = os.getenv("TEMP_RECEIPTS_DIR", "").strip()
_INITIAL_ENV_TEMP_TTL = os.getenv("TEMP_RECEIPT_TTL_SECONDS", "").strip()
_INITIAL_ENV_JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
_INITIAL_ENV_JWT_EXPIRE_MINUTES = os.getenv("JWT_EXPIRE_MINUTES", "").strip()
_INITIAL_ENV_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "").strip()
_INITIAL_ENV_FALLBACK_MODEL: str | None = (
    os.getenv("GEMINI_FALLBACK_MODEL", "").strip() or None
)
_JWT_FALLBACK_WARNED = False


class ConfigurationError(RuntimeError):
    """Error ketika konfigurasi wajib di sisi server belum tersedia atau tidak valid."""


GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = (
    os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
)
GEMINI_FALLBACK_MODEL: str | None = _INITIAL_ENV_FALLBACK_MODEL
DATABASE_URL: str = _INITIAL_ENV_DATABASE_URL
DATABASE_PATH: str = _INITIAL_ENV_DATABASE_PATH or DEFAULT_DATABASE_PATH
JWT_SECRET: str = _INITIAL_ENV_JWT_SECRET
JWT_EXPIRE_MINUTES: int = (
    int(_INITIAL_ENV_JWT_EXPIRE_MINUTES)
    if _INITIAL_ENV_JWT_EXPIRE_MINUTES.isdigit()
    and int(_INITIAL_ENV_JWT_EXPIRE_MINUTES) > 0
    else DEFAULT_JWT_EXPIRE_MINUTES
)
COOKIE_SECURE: bool = _INITIAL_ENV_COOKIE_SECURE.lower() in {
    "1",
    "true",
    "yes",
    "on",
}
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


def _normalize_database_url(raw_url: str) -> str:
    """Normalisasi URL PostgreSQL agar menggunakan driver psycopg v3 secara konsisten."""
    trimmed = raw_url.strip()
    if not trimmed:
        return ""
    if trimmed.startswith("postgres://"):
        return "postgresql+psycopg://" + trimmed[len("postgres://") :]
    if trimmed.startswith("postgresql://"):
        return "postgresql+psycopg://" + trimmed[len("postgresql://") :]
    return trimmed


def get_database_url() -> str:
    """Kembalikan DATABASE_URL aktif yang ternormalisasi (kosong jika fallback ke SQLite)."""
    if DATABASE_URL != _INITIAL_ENV_DATABASE_URL:
        return _normalize_database_url(DATABASE_URL)
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        return _normalize_database_url(env_url)
    return _normalize_database_url(DATABASE_URL)


def get_database_path() -> str:
    """Kembalikan path file SQLite aktif (mendukung override via env DATABASE_PATH atau DB_PATH)."""
    default_or_initial = _INITIAL_ENV_DATABASE_PATH or DEFAULT_DATABASE_PATH
    if DATABASE_PATH != default_or_initial:
        return DATABASE_PATH
    env_db_path = (
        os.getenv("DATABASE_PATH", "").strip() or os.getenv("DB_PATH", "").strip()
    )
    return env_db_path or DATABASE_PATH


def get_jwt_secret() -> str:
    """Kembalikan secret key JWT dari env/config dengan fallback dev-only yang aman."""
    global _JWT_FALLBACK_WARNED
    raw_secret = (
        JWT_SECRET
        if JWT_SECRET != _INITIAL_ENV_JWT_SECRET
        else os.getenv("JWT_SECRET", "").strip() or JWT_SECRET
    ).strip()
    if not raw_secret or raw_secret in _PLACEHOLDER_JWT_SECRETS:
        if not _JWT_FALLBACK_WARNED:
            logger.warning(
                "JWT_SECRET belum disetel atau masih placeholder; "
                "menggunakan fallback secret khusus pengembangan lokal."
            )
            _JWT_FALLBACK_WARNED = True
        return DEFAULT_DEV_JWT_SECRET
    return raw_secret


def get_jwt_expire_minutes() -> int:
    """Kembalikan masa berlaku token JWT dalam menit (minimal 1 menit)."""
    initial_val = (
        int(_INITIAL_ENV_JWT_EXPIRE_MINUTES)
        if _INITIAL_ENV_JWT_EXPIRE_MINUTES.isdigit()
        and int(_INITIAL_ENV_JWT_EXPIRE_MINUTES) > 0
        else DEFAULT_JWT_EXPIRE_MINUTES
    )
    if JWT_EXPIRE_MINUTES != initial_val:
        return max(1, int(JWT_EXPIRE_MINUTES))
    env_val = os.getenv("JWT_EXPIRE_MINUTES", "").strip()
    if env_val.isdigit() and int(env_val) > 0:
        return max(1, int(env_val))
    return initial_val


def get_cookie_secure() -> bool:
    """Kembalikan flag Secure cookie sesi (false untuk localhost HTTP, true untuk HTTPS)."""
    initial_bool = _INITIAL_ENV_COOKIE_SECURE.lower() in {"1", "true", "yes", "on"}
    if COOKIE_SECURE != initial_bool:
        return bool(COOKIE_SECURE)
    env_val = os.getenv("COOKIE_SECURE", "").strip().lower()
    if env_val:
        return env_val in {"1", "true", "yes", "on"}
    return initial_bool


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
