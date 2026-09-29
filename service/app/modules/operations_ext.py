from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.modules.models import AITask, AITrace, AITraceContext


RETRYABLE_STATUSES = {"FAILED", "CANCELLED"}
CANCELLABLE_STATUSES = {"PENDING"}


class TaskLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def list(self, project_id: UUID, limit: int = 100):
        query = (
            select(AITask)
            .where(AITask.project_id == project_id)
            .order_by(AITask.created_at.desc())
            .limit(min(max(limit, 1), 200))
        )
        return list((await self.s.scalars(query)).all())

    async def get(self, tenant_id: UUID, task_id: UUID) -> AITask:
        item = await self.s.scalar(
            select(AITask).where(AITask.id == task_id, AITask.tenant_id == tenant_id)
        )
        if not item:
            raise NotFound("TASK_NOT_FOUND", "Task not found")
        return item

    async def cancel(self, task: AITask):
        if task.status not in CANCELLABLE_STATUSES:
            raise Conflict(
                "TASK_NOT_CANCELLABLE",
                "Only pending tasks can be cancelled safely",
            )
        task.status = "CANCELLED"
        task.stage = "cancelled"
        task.completed_at = datetime.now(timezone.utc)
        return task

    async def retry(self, task: AITask, user_id: UUID) -> AITask:
        if task.status not in RETRYABLE_STATUSES:
            raise Conflict("TASK_NOT_RETRYABLE", "Only failed or cancelled tasks can be retried")
        clone = AITask(
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            task_type=task.task_type,
            target_type=task.target_type,
            target_id=task.target_id,
            status="PENDING",
            progress=0,
            stage="queued",
            input_json={**(task.input_json or {}), "retry_of": str(task.id)},
            created_by=user_id,
        )
        self.s.add(clone)
        await self.s.flush()
        return clone


async def trace_for_task(session: AsyncSession, task_id: UUID):
    traces = list(
        (
            await session.scalars(
                select(AITrace).where(AITrace.ai_task_id == task_id).order_by(AITrace.created_at)
            )
        ).all()
    )
    result = []
    for trace in traces:
        contexts = list(
            (
                await session.scalars(
                    select(AITraceContext)
                    .where(AITraceContext.trace_id == trace.id)
                    .order_by(AITraceContext.rank)
                )
            ).all()
        )
        result.append({"trace": trace, "contexts": contexts})
    return result
