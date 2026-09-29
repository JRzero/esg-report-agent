from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.modules.operations_ext import TaskLifecycle, trace_for_task
from app.modules.services import ProjectAccess
from app.workers.tasks import run_ai_task

router = APIRouter()


@router.get("/projects/{project_id}/tasks", tags=["Tasks"])
async def project_tasks(
    project_id: UUID,
    limit: int = 100,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return await TaskLifecycle(db).list(project_id, limit)


@router.post("/tasks/{task_id}/cancel", tags=["Tasks"])
async def cancel_task(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    lifecycle = TaskLifecycle(db)
    task = await lifecycle.get(ctx.tenant_id, task_id)
    if task.project_id:
        await ProjectAccess(db).require(task.project_id, ctx.membership_id, "EDIT_PROJECT")
    item = await lifecycle.cancel(task)
    await db.commit()
    return item


@router.post("/tasks/{task_id}/retry", status_code=202, tags=["Tasks"])
async def retry_task(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    lifecycle = TaskLifecycle(db)
    task = await lifecycle.get(ctx.tenant_id, task_id)
    if task.project_id:
        await ProjectAccess(db).require(task.project_id, ctx.membership_id, "EDIT_PROJECT")
    clone = await lifecycle.retry(task, ctx.user_id)
    await db.commit()
    run_ai_task.delay(str(clone.id), str(ctx.tenant_id))
    return {"task_id": clone.id, "status": clone.status}


@router.get("/tasks/{task_id}/traces", tags=["AI Trace"])
async def task_traces(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    task = await TaskLifecycle(db).get(ctx.tenant_id, task_id)
    if task.project_id:
        await ProjectAccess(db).require(task.project_id, ctx.membership_id, "VIEW_PROJECT")
    return await trace_for_task(db, task.id)
