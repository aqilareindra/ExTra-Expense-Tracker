"""Layanan autentikasi pengguna: hashing bcrypt, token JWT, dan dependensi FastAPI (M3.2)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import warnings

import bcrypt
from fastapi import HTTPException, Request, status
import jwt
from jwt import exceptions as jwt_exceptions
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend import config as app_config
from backend.database import User, session_scope
from backend.schemas.auth import LoginRequest, RegisterRequest, UserPublic

ACCESS_TOKEN_COOKIE_NAME = "access_token"
JWT_ALGORITHM = "HS256"

_DUMMY_PASSWORD_HASH: str = bcrypt.hashpw(
    b"dummy-timing-guard-password",
    bcrypt.gensalt(),
).decode("utf-8")


class AuthServiceError(Exception):
    """Base domain exception untuk operasi autentikasi."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class EmailAlreadyExistsError(AuthServiceError):
    """Error ketika email registrasi sudah terdaftar (HTTP 409)."""

    def __init__(
        self,
        message: str = "Email sudah terdaftar. Silakan masuk atau gunakan email lain.",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="EMAIL_ALREADY_EXISTS",
            message=message,
        )


class InvalidCredentialsError(AuthServiceError):
    """Error ketika email atau password login tidak valid (HTTP 401)."""

    def __init__(self, message: str = "Email atau password salah.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_CREDENTIALS",
            message=message,
        )


class UnauthorizedError(AuthServiceError):
    """Error ketika sesi/token tidak tersedia, tidak valid, atau kedaluwarsa (HTTP 401)."""

    def __init__(
        self,
        message: str = "Sesi login tidak ditemukan atau telah berakhir. Silakan masuk terlebih dahulu.",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message=message,
        )


def _user_to_public(user: User) -> UserPublic:
    """Konversi model ORM User ke UserPublic tanpa menyertakan password_hash."""
    return UserPublic(
        id=int(user.id),
        email=str(user.email),
        created_at=str(user.created_at),
    )


def hash_password(plain_password: str) -> str:
    """Hash password menggunakan bcrypt dengan salt acak."""
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password maksimal 72 byte.")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifikasi password plain terhadap hash bcrypt secara aman."""
    if not plain_password or not password_hash:
        return False
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        return False
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    user_id: int,
    expires_delta: timedelta | None = None,
) -> str:
    """Buat token JWT HS256 dengan klaim sub (string), iat, dan exp."""
    now = datetime.now(timezone.utc)
    delta = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=app_config.get_jwt_expire_minutes())
    )
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    secret = app_config.get_jwt_secret()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Validasi dan decode token JWT, lalu kembalikan user_id bertipe int."""
    if not token or not isinstance(token, str):
        raise UnauthorizedError()

    secret = app_config.get_jwt_secret()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            claims = jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["sub", "exp", "iat"]},
            )
    except jwt_exceptions.ExpiredSignatureError as exc:
        raise UnauthorizedError(
            "Sesi login Anda telah berakhir. Silakan masuk kembali."
        ) from exc
    except jwt_exceptions.InvalidTokenError as exc:
        raise UnauthorizedError("Token autentikasi tidak valid.") from exc

    raw_sub = claims.get("sub")
    if not isinstance(raw_sub, str) or not raw_sub.isdigit():
        raise UnauthorizedError("Token autentikasi tidak valid.")

    user_id = int(raw_sub)
    if user_id < 1:
        raise UnauthorizedError("Token autentikasi tidak valid.")
    return user_id


def register_user(
    payload: RegisterRequest,
    db_path: str | Path | None = None,
) -> UserPublic:
    """Daftarkan pengguna baru dengan email unik dan password ter-hash bcrypt."""
    hashed = hash_password(payload.password)
    try:
        with session_scope(db_path) as session:
            existing = session.scalar(
                select(User).where(User.email == payload.email)
            )
            if existing is not None:
                raise EmailAlreadyExistsError()

            new_user = User(email=payload.email, password_hash=hashed)
            session.add(new_user)
            session.flush()
            session.refresh(new_user)
            return _user_to_public(new_user)
    except IntegrityError as exc:
        raise EmailAlreadyExistsError() from exc


def authenticate_user(
    payload: LoginRequest,
    db_path: str | Path | None = None,
) -> UserPublic:
    """Verifikasi kredensial pengguna tanpa membocorkan eksistensi email."""
    with session_scope(db_path) as session:
        user = session.scalar(select(User).where(User.email == payload.email))
        if user is None:
            verify_password(payload.password, _DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError()

        if not verify_password(payload.password, user.password_hash):
            raise InvalidCredentialsError()

        return _user_to_public(user)


def get_user_by_id(
    user_id: int,
    db_path: str | Path | None = None,
) -> UserPublic | None:
    """Ambil data publik pengguna berdasarkan ID, atau None jika tidak ditemukan."""
    with session_scope(db_path) as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        return _user_to_public(user)


def _extract_token_from_request(request: Request) -> str | None:
    """Ambil JWT dari cookie HttpOnly terlebih dahulu, lalu fallback Authorization Bearer."""
    cookie_token = (request.cookies.get(ACCESS_TOKEN_COOKIE_NAME) or "").strip()
    if cookie_token:
        return cookie_token

    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header:
        return None
    scheme, _, credentials = auth_header.partition(" ")
    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()
    return None


def get_current_user(request: Request) -> UserPublic:
    """FastAPI dependency yang memastikan request berasal dari pengguna terautentikasi."""
    token = _extract_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Sesi login tidak ditemukan atau telah berakhir. Silakan masuk terlebih dahulu.",
            },
        )

    try:
        user_id = decode_access_token(token)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "status": "error",
                "error_code": exc.error_code,
                "message": exc.message,
            },
        ) from exc

    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Akun pengguna tidak ditemukan atau sesi tidak lagi berlaku.",
            },
        )
    return user
