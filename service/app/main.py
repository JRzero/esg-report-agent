from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from redis.asyncio import Redis

from app.api.lifecycle_router import router as lifecycle_router
from app.api.ops_router import router as ops_router
from app.api.report_ops_router import router as report_ops_router
from app.api.router import router
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import DomainError

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.2.0")
app.include_router(router)
app.include_router(lifecycle_router)
app.include_router(report_ops_router)
app.include_router(ops_router)


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
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
        headers={"X-Request-ID": request_id},
    )


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
async def ready():
    dependencies = {"postgres": "down", "redis": "down"}
    try:
        async with get_session_factory()() as session:
            await session.execute(text("select 1"))
        dependencies["postgres"] = "ok"
    except Exception:
        pass
    try:
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        await redis.aclose()
        dependencies["redis"] = "ok"
    except Exception:
        pass
    ready_state = all(value == "ok" for value in dependencies.values())
    return {
        "status": "ready" if ready_state else "not_ready",
        "dependencies": dependencies,
    }
