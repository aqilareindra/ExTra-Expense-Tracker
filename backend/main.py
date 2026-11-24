"""Entry point aplikasi FastAPI ExTra."""

from fastapi import FastAPI

from backend import config  # noqa: F401

app = FastAPI(title="ExTra API")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Endpoint pemeriksaan status layanan."""
    return {"status": "ok", "service": "ExTra API"}
