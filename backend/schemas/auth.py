"""Skema Pydantic v2 untuk autentikasi pengguna (M3.2)."""

from typing import Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, field_validator


def normalize_and_validate_email(value: object) -> str:
    """Validasi format email dan normalisasi ke huruf kecil tanpa spasi tepi."""
    if not isinstance(value, str):
        raise ValueError("Format alamat email tidak valid.")
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Alamat email wajib diisi.")
    try:
        info = validate_email(trimmed, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError("Format alamat email tidak valid.") from exc
    return info.normalized.lower()


def validate_register_password(value: object) -> str:
    """Validasi password registrasi minimal 8 karakter (dan batas aman 72 byte bcrypt)."""
    if not isinstance(value, str):
        raise ValueError("Password harus berupa string.")
    if len(value) < 8:
        raise ValueError("Password minimal terdiri dari 8 karakter.")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password maksimal 72 byte.")
    return value


def validate_login_password(value: object) -> str:
    """Validasi password login tidak kosong."""
    if not isinstance(value, str) or not value:
        raise ValueError("Password wajib diisi.")
    return value


class RegisterRequest(BaseModel):
    """Skema payload registrasi akun baru."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def _check_email(cls, value: object) -> str:
        return normalize_and_validate_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def _check_password(cls, value: object) -> str:
        return validate_register_password(value)


class LoginRequest(BaseModel):
    """Skema payload login akun."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def _check_email(cls, value: object) -> str:
        return normalize_and_validate_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def _check_password(cls, value: object) -> str:
        return validate_login_password(value)


class UserPublic(BaseModel):
    """Representasi aman data pengguna (tanpa password_hash)."""

    id: int
    email: str
    created_at: str


class AuthSuccessResponse(BaseModel):
    """Respons sukses untuk POST /api/auth/register dan POST /api/auth/login."""

    status: Literal["success"] = "success"
    message: str
    data: UserPublic


class CurrentUserResponse(BaseModel):
    """Respons sukses untuk GET /api/auth/me."""

    status: Literal["success"] = "success"
    data: UserPublic


class LogoutResponse(BaseModel):
    """Respons sukses untuk POST /api/auth/logout."""

    status: Literal["success"] = "success"
    message: str = "Berhasil keluar dari sesi."
