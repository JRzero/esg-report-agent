from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import NotFound
from app.integrations.storage import storage
from app.modules.models import (
    Citation,
    Claim,
    Comment,
    Report,
    ReportBlock,
    ReportBlockRevision,
    ReportExport,
    ReportSection,
    SectionDisclosureMap,
)
from app.modules.reporting_ext import (
    CommentLifecycle,
    ReportLifecycle,
    get_export,
    verify_claim,
)
from app.modules.schemas import (
    BlockCreate,
    BlockUpdate,
    CommentCreate,
    ReportUpdate,
    SectionDisclosureCreate,
    SectionReorderRequest,
    SectionUpdate,
)
from app.modules.services import ProjectAccess

router = APIRouter()


async def _report(
    db: AsyncSession,
    ctx: RequestContext,
    report_id: UUID,
    action: str = "VIEW_PROJECT",
) -> Report:
    report = await db.get(Report, report_id)
    if not report or report.tenant_id != ctx.tenant_id:
        raise NotFound("REPORT_NOT_FOUND", "Report not found")
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, action)
    return report


@router.get("/projects/{project_id}/reports", tags=["Reports"])
async def project_reports(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return await ReportLifecycle(db).list(project_id)


@router.get("/reports/{report_id}", tags=["Reports"])
async def report_detail(
    report_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await _report(db, ctx, report_id)


@router.patch("/reports/{report_id}", tags=["Reports"])
async def update_report(
    report_id: UUID,
    body: ReportUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    report = await _report(db, ctx, report_id, "EDIT_REPORT")
    item = await ReportLifecycle(db).update(report, body)
    await db.commit()
    return item


@router.patch("/sections/{section_id}", tags=["Reports"])
async def update_section(
    section_id: UUID,
    body: SectionUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await ReportLifecycle(db).section(section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    item = await ReportLifecycle(db).update_section(section, body)
    await db.commit()
    return item


@router.delete("/sections/{section_id}", status_code=204, tags=["Reports"])
async def delete_section(
    section_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await ReportLifecycle(db).section(section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    await ReportLifecycle(db).delete_section(section)
    await db.commit()
    return Response(status_code=204)


@router.post("/reports/{report_id}/sections/reorder", tags=["Reports"])
async def reorder_sections(
    report_id: UUID,
    body: SectionReorderRequest,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    report = await _report(db, ctx, report_id, "EDIT_REPORT")
    await ReportLifecycle(db).reorder(report.id, body.items)
    await db.commit()
    return {"status": "SUCCESS"}


@router.get("/sections/{section_id}/disclosures", tags=["Reports"])
async def section_disclosures(
    section_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await ReportLifecycle(db).section(section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(SectionDisclosureMap).where(SectionDisclosureMap.section_id == section.id)
            )
        ).all()
    )


@router.post("/sections/{section_id}/disclosures", status_code=201, tags=["Reports"])
async def add_section_disclosure(
    section_id: UUID,
    body: SectionDisclosureCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await ReportLifecycle(db).section(section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    item = await ReportLifecycle(db).add_disclosure(
        section, body.disclosure_id, body.mapping_type
    )
    await db.commit()
    return item


@router.delete(
    "/sections/{section_id}/disclosures/{disclosure_id}",
    status_code=204,
    tags=["Reports"],
)
async def remove_section_disclosure(
    section_id: UUID,
    disclosure_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await ReportLifecycle(db).section(section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    item = await db.scalar(
        select(SectionDisclosureMap).where(
            SectionDisclosureMap.section_id == section_id,
            SectionDisclosureMap.disclosure_id == disclosure_id,
        )
    )
    if item:
        await db.delete(item)
        await db.commit()
    return Response(status_code=204)


@router.post("/sections/{section_id}/blocks", status_code=201, tags=["Reports"])
async def create_block(
    section_id: UUID,
    body: BlockCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await ReportLifecycle(db).section(section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    item = await ReportLifecycle(db).create_block(section, ctx.user_id, body)
    await db.commit()
    return item


@router.patch("/blocks/{block_id}", tags=["Reports"])
async def update_block(
    block_id: UUID,
    body: BlockUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    block = await ReportLifecycle(db).block(block_id)
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    item = await ReportLifecycle(db).update_block(block, ctx.user_id, body)
    await db.commit()
    return item


@router.delete("/blocks/{block_id}", status_code=204, tags=["Reports"])
async def delete_block(
    block_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    block = await ReportLifecycle(db).block(block_id)
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    await ReportLifecycle(db).delete_block(block)
    await db.commit()
    return Response(status_code=204)


@router.post("/blocks/{block_id}/restore/{revision_no}", tags=["Reports"])
async def restore_block(
    block_id: UUID,
    revision_no: int,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    block = await ReportLifecycle(db).block(block_id)
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    item = await ReportLifecycle(db).restore_block(block, revision_no, ctx.user_id)
    await db.commit()
    return item


@router.post("/claims/{claim_id}/verify", tags=["Reports"])
async def verify_report_claim(
    claim_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise NotFound("CLAIM_NOT_FOUND", "Claim not found")
    revision = await db.get(ReportBlockRevision, claim.block_revision_id)
    block = await db.get(ReportBlock, revision.block_id) if revision else None
    if not block:
        raise NotFound("CLAIM_NOT_FOUND", "Claim not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "VIEW_FACT")
    item = await verify_claim(db, claim_id)
    await db.commit()
    return item


@router.get("/projects/{project_id}/comments", tags=["Comments"])
async def list_comments(
    project_id: UUID,
    section_id: UUID | None = None,
    block_id: UUID | None = None,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "COMMENT")
    query = select(Comment).where(Comment.project_id == project_id)
    if section_id:
        query = query.where(Comment.section_id == section_id)
    if block_id:
        query = query.where(Comment.block_id == block_id)
    return list((await db.scalars(query.order_by(Comment.created_at))).all())


@router.post("/projects/{project_id}/comments", status_code=201, tags=["Comments"])
async def create_comment(
    project_id: UUID,
    body: CommentCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "COMMENT")
    item = await CommentLifecycle(db).create(
        ctx.tenant_id, project_id, ctx.user_id, body
    )
    await db.commit()
    return item


@router.post("/comments/{comment_id}/resolve", tags=["Comments"])
async def resolve_comment(
    comment_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    comment = await db.get(Comment, comment_id)
    if not comment or comment.tenant_id != ctx.tenant_id:
        raise NotFound("COMMENT_NOT_FOUND", "Comment not found")
    await ProjectAccess(db).require(comment.project_id, ctx.membership_id, "COMMENT")
    item = await CommentLifecycle(db).resolve(comment.id, ctx.user_id)
    await db.commit()
    return item


@router.get("/report-exports/{export_id}", tags=["Reports"])
async def report_export_detail(
    export_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    export = await get_export(db, export_id)
    report = await _report(db, ctx, export.report_id)
    result = {"id": export.id, "report_id": report.id, "status": export.status, "format": export.format}
    if export.status == "SUCCESS" and export.object_key:
        result["download_url"] = await storage().signed_download_url(export.object_key)
    return result
