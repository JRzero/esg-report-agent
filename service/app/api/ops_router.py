from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import Conflict, NotFound
from app.modules.models import AITask
from app.modules.services import ProjectAccess
from app.workers.tasks import run_ai_task

router = APIRouter(prefix="/api/v1", tags=["Operations"])


@router.get("/projects/{project_id}/tasks")
async def list_tasks(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(AITask)
                .where(AITask.project_id == project_id)
                .order_by(AITask.created_at.desc())
                .limit(200)
            )
        ).all()
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(AITask, task_id)
    if not task or task.tenant_id != ctx.tenant_id:
        raise NotFound("TASK_NOT_FOUND", "Task not found")
    if task.project_id:
        await ProjectAccess(db).require(task.project_id, ctx.membership_id, "GENERATE_REPORT")
    if task.status in {"SUCCESS", "FAILED", "CANCELLED"}:
        raise Conflict("TASK_NOT_CANCELLABLE", f"Task is already {task.status}")
    task.status = "CANCELLED"
    task.stage = "cancelled"
    await db.commit()
    return task


@router.post("/tasks/{task_id}/retry", status_code=202)
async def retry_task(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(AITask, task_id)
    if not task or task.tenant_id != ctx.tenant_id:
        raise NotFound("TASK_NOT_FOUND", "Task not found")
    if task.project_id:
        await ProjectAccess(db).require(task.project_id, ctx.membership_id, "GENERATE_REPORT")
    if task.status not in {"FAILED", "CANCELLED"}:
        raise Conflict("TASK_NOT_RETRYABLE", "Only failed or cancelled tasks can be retried")
    task.status = "PENDING"
    task.progress = 0
    task.stage = "queued"
    task.error_code = None
    task.error_message = None
    task.started_at = None
    task.completed_at = None
    await db.commit()
    run_ai_task.delay(str(task.id))
    return {"task_id": task.id, "status": task.status}


async def dependency_status(db: AsyncSession):
    settings = get_settings()
    result = {
        "postgres": "unknown",
        "redis": "unknown",
        "storage": "configured",
        "openviking": "not_configured",
        "llm": "not_configured",
    }
    try:
        await db.execute(text("select 1"))
        result["postgres"] = "ok"
    except Exception:
        result["postgres"] = "down"

    try:
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        await redis.aclose()
        result["redis"] = "ok"
    except Exception:
        result["redis"] = "down"

    if settings.openviking_base_url:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(
                    settings.openviking_base_url.rstrip("/") + "/health",
                    headers={"X-API-Key": settings.openviking_api_key}
                    if settings.openviking_api_key
                    else {},
                )
                result["openviking"] = "ok" if response.is_success else "down"
        except Exception:
            result["openviking"] = "down"

    if settings.llm_base_url:
        result["llm"] = "configured"
    return result


@router.get("/internal/dependencies")
async def dependencies(
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await dependency_status(db)
