from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter

settings = get_settings()

_DEFAULT_SECRET = "change-me-secret"
_DEFAULT_ENC_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app = FastAPI(
    title=settings.project_name,
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
async def startup_checks() -> None:
    if settings.environment == "production":
        if settings.secret_key == _DEFAULT_SECRET:
            raise RuntimeError("SECRET_KEY must be changed from the default value before running in production.")
        if settings.encryption_key == _DEFAULT_ENC_KEY:
            raise RuntimeError("ENCRYPTION_KEY must be changed from the default value before running in production.")


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": settings.project_name}


media_root = Path(settings.generated_media_dir)
media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_root), name="media")

app.include_router(api_router, prefix=settings.api_prefix)
