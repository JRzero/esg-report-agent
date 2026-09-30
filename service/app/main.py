from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.router import router
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import DomainError
from app.integrations.storage import storage

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.include_router(router)


@app.middleware("http")
async def security_and_request_id_middleware(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_request_id if 0 < len(supplied_request_id) <= 128 else str(uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/v1/auth/"):
        response.headers["Cache-Control"] = "no-store"
    if settings.security_hsts_enabled:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            }
        },
    )


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
async def ready():
    dependencies: dict[str, str] = {}

    try:
        async with get_session_factory()() as session:
            await session.execute(text("select 1"))
        dependencies["postgres"] = "ok"
    except Exception:
        dependencies["postgres"] = "error"

    try:
        redis = Redis.from_url(settings.redis_url)
        try:
            await redis.ping()
            dependencies["redis"] = "ok"
        finally:
            await redis.aclose()
    except Exception:
        dependencies["redis"] = "error"

    try:
        dependencies["storage"] = "ok" if await storage().health() else "error"
    except Exception:
        dependencies["storage"] = "error"

    ready_state = all(value == "ok" for value in dependencies.values())
    return JSONResponse(
        status_code=200 if ready_state else 503,
        content={"status": "ready" if ready_state else "not_ready", "dependencies": dependencies},
    )
