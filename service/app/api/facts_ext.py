from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import NotFound
from app.modules.evidence_ext import FactLifecycle
from app.modules.models import (
    Fact,
    FactConflictGroup,
    FactConflictMember,
    FactEvidence,
    FactRevision,
)
from app.modules.schemas import FactEvidenceCreate, FactRejectRequest, FactUpdate
from app.modules.services import ProjectAccess

router = APIRouter()


async def _fact(
    db: AsyncSession,
    ctx: RequestContext,
    fact_id: UUID,
    action: str,
) -> Fact:
    fact = await db.get(Fact, fact_id)
    if not fact or fact.tenant_id != ctx.tenant_id or fact.deleted_at is not None:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, action)
    return fact


@router.get("/facts/{fact_id}", tags=["Facts"])
async def fact_detail(
    fact_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await _fact(db, ctx, fact_id, "VIEW_FACT")


@router.patch("/facts/{fact_id}", tags=["Facts"])
async def update_fact(
    fact_id: UUID,
    body: FactUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await _fact(db, ctx, fact_id, "CONFIRM_FACT")
    item = await FactLifecycle(db).update(fact, ctx.user_id, body)
    await db.commit()
    return item


@router.post("/facts/{fact_id}/reject", tags=["Facts"])
async def reject_fact(
    fact_id: UUID,
    body: FactRejectRequest,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await _fact(db, ctx, fact_id, "CONFIRM_FACT")
    item = await FactLifecycle(db).reject(fact, ctx.user_id, body.reason)
    await db.commit()
    return item


@router.get("/facts/{fact_id}/revisions", tags=["Facts"])
async def fact_revisions(
    fact_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await _fact(db, ctx, fact_id, "VIEW_FACT")
    return list(
        (
            await db.scalars(
                select(FactRevision)
                .where(FactRevision.fact_id == fact.id)
                .order_by(FactRevision.revision_no.desc())
            )
        ).all()
    )


@router.post("/facts/{fact_id}/evidence", status_code=201, tags=["Facts"])
async def add_fact_evidence(
    fact_id: UUID,
    body: FactEvidenceCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await _fact(db, ctx, fact_id, "CONFIRM_FACT")
    item = await FactLifecycle(db).add_evidence(
        fact, ctx.user_id, body.anchor_id, body.evidence_role
    )
    await db.commit()
    return item


@router.delete(
    "/facts/{fact_id}/evidence/{anchor_id}",
    status_code=204,
    tags=["Facts"],
)
async def remove_fact_evidence(
    fact_id: UUID,
    anchor_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await _fact(db, ctx, fact_id, "CONFIRM_FACT")
    await FactLifecycle(db).remove_evidence(fact, ctx.user_id, anchor_id)
    await db.commit()
    return Response(status_code=204)


@router.get("/fact-conflicts/{group_id}", tags=["Facts"])
async def conflict_detail(
    group_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    group = await db.get(FactConflictGroup, group_id)
    if not group or group.tenant_id != ctx.tenant_id:
        raise NotFound("FACT_CONFLICT_NOT_FOUND", "Fact conflict not found")
    await ProjectAccess(db).require(group.project_id, ctx.membership_id, "VIEW_FACT")
    query = (
        select(Fact)
        .join(FactConflictMember, FactConflictMember.fact_id == Fact.id)
        .where(FactConflictMember.conflict_group_id == group.id)
    )
    facts = list((await db.scalars(query)).all())
    return {"conflict": group, "facts": facts}


@router.get("/facts/{fact_id}/evidence-links", tags=["Facts"])
async def fact_evidence_links(
    fact_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await _fact(db, ctx, fact_id, "VIEW_FACT")
    return list(
        (
            await db.scalars(
                select(FactEvidence).where(FactEvidence.fact_id == fact.id)
            )
        ).all()
    )
