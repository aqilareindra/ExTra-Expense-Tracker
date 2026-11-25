"""Entry point aplikasi FastAPI ExTra."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import config
from backend.database import init_db
from backend.routers.receipts import router as receipts_router
from backend.routers.summary import router as summary_router
from backend.routers.transactions import router as transactions_router

FRONTEND_DIR = config.BASE_DIR / "frontend"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Inisialisasi tabel SQLite saat aplikasi dijalankan."""
    init_db()
    yield


app = FastAPI(title="ExTra API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Format seluruh error validasi Pydantic menjadi JSON konsisten."""
    details: list[dict[str, str]] = []
    for err in exc.errors():
        loc_parts = [str(part) for part in err.get("loc", ()) if part != "body"]
        field_name = ".".join(loc_parts) if loc_parts else "body"
        details.append(
            {
                "field": field_name,
                "message": str(err.get("msg", "Data input tidak valid.")),
            }
        )

    summary_msg = (
        details[0]["message"] if details else "Data request tidak lolos validasi."
    )
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": summary_msg,
            "details": details,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Pastikan HTTPException dikembalikan dengan struktur error standar ExTra."""
    if isinstance(exc.detail, dict) and exc.detail.get("status") == "error":
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    code_map = {
        400: "BAD_REQUEST",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "FILE_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "AI_SERVICE_UNAVAILABLE",
        500: "INTERNAL_SERVER_ERROR",
        502: "AI_PARSE_ERROR",
        503: "AI_SERVICE_UNAVAILABLE",
    }
    error_code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error_code": error_code,
            "message": str(exc.detail),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Cegah kebocoran stack trace internal ke client pada error tak terduga."""
    logger.error("Unhandled server error (%s).", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Terjadi kesalahan internal pada server. Silakan coba lagi.",
        },
    )


app.include_router(receipts_router)
app.include_router(transactions_router)
app.include_router(summary_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Endpoint pemeriksaan status layanan."""
    return {"status": "ok", "service": "ExTra API"}


if (FRONTEND_DIR / "css").is_dir():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")

if (FRONTEND_DIR / "js").is_dir():
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")


@app.get("/", include_in_schema=False)
def serve_frontend_index() -> FileResponse:
    """Layani halaman utama antarmuka web ExTra."""
    return FileResponse(FRONTEND_DIR / "index.html", media_type="text/html")
