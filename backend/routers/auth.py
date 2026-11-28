"""Router REST API untuk registrasi, login, logout, dan profil pengguna aktif (M3.2)."""

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from backend import config as app_config
from backend.schemas.auth import (
    AuthSuccessResponse,
    CurrentUserResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    UserPublic,
)
from backend.schemas.transaction import ErrorResponse
from backend.services import auth_service
from backend.services.auth_service import (
    ACCESS_TOKEN_COOKIE_NAME,
    AuthServiceError,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _auth_error_response(exc: AuthServiceError) -> JSONResponse:
    """Bangun respons JSON error konsisten untuk kegagalan autentikasi."""
    payload = ErrorResponse(error_code=exc.error_code, message=exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(exclude_none=True),
    )


def _set_access_token_cookie(response: Response, token: str) -> None:
    """Set cookie HttpOnly berisi JWT sesi pengguna."""
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=app_config.get_cookie_secure(),
        max_age=app_config.get_jwt_expire_minutes() * 60,
        path="/",
    )


@router.post(
    "/register",
    response_model=AuthSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def register_endpoint(
    payload: RegisterRequest,
    response: Response,
) -> AuthSuccessResponse | JSONResponse:
    """Daftarkan akun baru dan langsung aktifkan sesi login via HttpOnly cookie."""
    try:
        user = auth_service.register_user(payload)
    except AuthServiceError as exc:
        return _auth_error_response(exc)

    token = auth_service.create_access_token(user.id)
    _set_access_token_cookie(response, token)
    return AuthSuccessResponse(
        message="Akun berhasil dibuat.",
        data=user,
    )


@router.post(
    "/login",
    response_model=AuthSuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def login_endpoint(
    payload: LoginRequest,
    response: Response,
) -> AuthSuccessResponse | JSONResponse:
    """Verifikasi email & password lalu set HttpOnly cookie sesi."""
    try:
        user = auth_service.authenticate_user(payload)
    except AuthServiceError as exc:
        return _auth_error_response(exc)

    token = auth_service.create_access_token(user.id)
    _set_access_token_cookie(response, token)
    return AuthSuccessResponse(
        message="Berhasil masuk.",
        data=user,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
)
def logout_endpoint(response: Response) -> LogoutResponse:
    """Hapus cookie sesi login pengguna."""
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=app_config.get_cookie_secure(),
    )
    return LogoutResponse()


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}},
)
def get_me_endpoint(
    current_user: UserPublic = Depends(get_current_user),
) -> CurrentUserResponse:
    """Kembalikan profil pengguna yang sedang aktif berdasarkan sesi/token."""
    return CurrentUserResponse(data=current_user)
