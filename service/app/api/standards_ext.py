from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import NotFound
from app.modules.models import (
    Disclosure,
    DisclosureRequirement,
    MissingItem,
    ProjectStandard,
    Standard,
    StandardVersion,
)
from app.modules.schemas import MissingItemUpdate
from app.modules.services import ProjectAccess, TaskService
from app.workers.tasks import run_ai_task

router = APIRouter()


async def _queue(
    db: AsyncSession,
    ctx: RequestContext,
    project_id: UUID,
    task_type: str,
):
    task = await TaskService(db).create(
        ctx.tenant_id,
        project_id,
        ctx.user_id,
        task_type,
        "PROJECT",
        project_id,
    )
    await db.commit()
    run_ai_task.delay(str(task.id), str(ctx.tenant_id))
    return {"task_id": task.id, "status": task.status}


@router.get("/standards/{standard_id}/versions", tags=["Standards"])
async def standard_versions(
    standard_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    standard = await db.get(Standard, standard_id)
    if not standard:
        raise NotFound("STANDARD_NOT_FOUND", "Standard not found")
    return list(
        (
            await db.scalars(
                select(StandardVersion)
                .where(StandardVersion.standard_id == standard_id)
                .order_by(StandardVersion.effective_date.desc().nullslast())
            )
        ).all()
    )


@router.get("/disclosures/{disclosure_id}", tags=["Standards"])
async def disclosure_detail(
    disclosure_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(Disclosure, disclosure_id)
    if not item:
        raise NotFound("DISCLOSURE_NOT_FOUND", "Disclosure not found")
    return item


@router.get("/disclosures/{disclosure_id}/requirements", tags=["Standards"])
async def disclosure_requirements(
    disclosure_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    disclosure = await db.get(Disclosure, disclosure_id)
    if not disclosure:
        raise NotFound("DISCLOSURE_NOT_FOUND", "Disclosure not found")
    return list(
        (
            await db.scalars(
                select(DisclosureRequirement)
                .where(DisclosureRequirement.disclosure_id == disclosure_id)
                .order_by(DisclosureRequirement.sort_order)
            )
        ).all()
    )


@router.get("/projects/{project_id}/standards", tags=["Standards"])
async def project_standards(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    query = (
        select(ProjectStandard, StandardVersion, Standard)
        .join(StandardVersion, ProjectStandard.standard_version_id == StandardVersion.id)
        .join(Standard, StandardVersion.standard_id == Standard.id)
        .where(ProjectStandard.project_id == project_id)
    )
    rows = (await db.execute(query)).all()
    return [
        {"project_standard": ps, "version": version, "standard": standard}
        for ps, version, standard in rows
    ]


@router.patch("/missing-items/{item_id}", tags=["Standards"])
async def update_missing_item(
    item_id: UUID,
    body: MissingItemUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(MissingItem, item_id)
    if not item or item.tenant_id != ctx.tenant_id:
        raise NotFound("MISSING_ITEM_NOT_FOUND", "Missing item not found")
    await ProjectAccess(db).require(item.project_id, ctx.membership_id, "EDIT_PROJECT")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await db.commit()
    return item


@router.post("/projects/{project_id}/ai/gri-check", status_code=202, tags=["AI"])
async def gri_check(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_PROJECT")
    return await _queue(db, ctx, project_id, "GRI_CHECK")
