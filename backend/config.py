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
_PLACEHOLDER_API_KEYS = {"your_gemini_api_key_here"}


class ConfigurationError(RuntimeError):
    """Error ketika konfigurasi wajib di sisi server belum tersedia atau tidak valid."""


GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = (
    os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
)


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
