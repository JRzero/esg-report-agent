from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import Conflict, DomainError, NotFound
from app.integrations.storage import storage
from app.modules.collaboration import Comment
from app.modules.models import (
    Citation,
    Claim,
    Disclosure,
    Fact,
    FactEvidence,
    ProjectDisclosure,
    ProjectRequirementStatus,
    Report,
    ReportBlock,
    ReportBlockRevision,
    ReportExport,
    ReportSection,
    ReportTemplate,
    ReportTemplateSection,
    ReportTemplateVersion,
    SectionDisclosureMap,
)
from app.modules.services import ProjectAccess, ReportService
from app.workers.tasks import export_report

router = APIRouter(prefix="/api/v1", tags=["Report Operations"])


def _dump(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


@router.get("/report-templates")
async def list_templates(ctx: RequestContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    return list(
        (
            await db.scalars(
                select(ReportTemplate)
                .where(
                    (ReportTemplate.tenant_id == ctx.tenant_id)
                    | (ReportTemplate.tenant_id.is_(None)),
                    ReportTemplate.status == "ACTIVE",
                )
                .order_by(ReportTemplate.created_at.desc())
            )
        ).all()
    )


@router.post("/report-templates", status_code=201)
async def create_template(
    body: dict,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    template = ReportTemplate(
        tenant_id=ctx.tenant_id,
        name=body["name"],
        description=body.get("description"),
        template_type="TENANT",
        created_by=ctx.user_id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/report-templates/{template_id}")
async def get_template(template_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    template = await db.get(ReportTemplate, template_id)
    if not template or (template.tenant_id not in {None, ctx.tenant_id}):
        raise NotFound("REPORT_TEMPLATE_NOT_FOUND", "Report template not found")
    versions = list(
        (
            await db.scalars(
                select(ReportTemplateVersion)
                .where(ReportTemplateVersion.template_id == template_id)
                .order_by(ReportTemplateVersion.version_no.desc())
            )
        ).all()
    )
    return {"template": _dump(template), "versions": [_dump(v) for v in versions]}


@router.post("/report-templates/{template_id}/versions", status_code=201)
async def create_template_version(
    template_id: UUID,
    body: dict,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(ReportTemplate, template_id)
    if not template or template.tenant_id != ctx.tenant_id:
        raise NotFound("REPORT_TEMPLATE_NOT_FOUND", "Report template not found")
    next_no = (
        await db.scalar(
            select(func.max(ReportTemplateVersion.version_no)).where(
                ReportTemplateVersion.template_id == template_id
            )
        )
        or 0
    ) + 1
    version = ReportTemplateVersion(
        template_id=template_id,
        version_no=next_no,
        source_type=body.get("source_type", "MANUAL"),
        created_by=ctx.user_id,
    )
    db.add(version)
    await db.flush()
    mapping = {}
    for index, item in enumerate(body.get("sections", [])):
        client_key = item.get("key", str(index))
        parent_key = item.get("parent_key")
        section = ReportTemplateSection(
            template_version_id=version.id,
            parent_id=mapping.get(parent_key),
            title=item["title"],
            description=item.get("description"),
            level=item.get("level", 1),
            sort_order=item.get("sort_order", index),
            writing_guidance=item.get("writing_guidance"),
        )
        db.add(section)
        await db.flush()
        mapping[client_key] = section.id
    await db.commit()
    return {"version": _dump(version), "sections_created": len(mapping)}


@router.get("/report-template-versions/{version_id}/sections")
async def template_sections(version_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    version = await db.get(ReportTemplateVersion, version_id)
    template = await db.get(ReportTemplate, version.template_id) if version else None
    if not template or template.tenant_id not in {None, ctx.tenant_id}:
        raise NotFound("REPORT_TEMPLATE_NOT_FOUND", "Report template not found")
    return list(
        (
            await db.scalars(
                select(ReportTemplateSection)
                .where(ReportTemplateSection.template_version_id == version_id)
                .order_by(ReportTemplateSection.sort_order)
            )
        ).all()
    )


@router.post("/projects/{project_id}/reports/from-template", status_code=201)
async def create_report_from_template(
    project_id: UUID,
    body: dict,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_REPORT")
    report = await ReportService(db).create_report(
        ctx.tenant_id,
        project_id,
        ctx.user_id,
        body["title"],
        body.get("language", "zh-CN"),
        UUID(body["template_version_id"]) if body.get("template_version_id") else None,
    )
    await db.commit()
    return report


@router.patch("/sections/{section_id}")
async def update_section(section_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    section = await db.get(ReportSection, section_id)
    if not section:
        raise NotFound("SECTION_NOT_FOUND", "Section not found")
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    for key in {"title", "description", "parent_id", "level", "sort_order", "status"}:
        if key in body:
            setattr(section, key, body[key])
    await db.commit()
    return section


@router.delete("/sections/{section_id}", status_code=204)
async def delete_section(section_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    section = await db.get(ReportSection, section_id)
    if not section:
        raise NotFound("SECTION_NOT_FOUND", "Section not found")
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    has_children = await db.scalar(
        select(func.count()).select_from(ReportSection).where(ReportSection.parent_id == section_id)
    )
    if has_children:
        raise Conflict("SECTION_HAS_CHILDREN", "Move or delete child sections first")
    await db.delete(section)
    await db.commit()


@router.post("/sections/{section_id}/disclosures", status_code=201)
async def map_section_disclosure(section_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    section = await db.get(ReportSection, section_id)
    if not section:
        raise NotFound("SECTION_NOT_FOUND", "Section not found")
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    disclosure_id = UUID(str(body["disclosure_id"]))
    exists = await db.scalar(
        select(SectionDisclosureMap).where(
            SectionDisclosureMap.section_id == section_id,
            SectionDisclosureMap.disclosure_id == disclosure_id,
        )
    )
    if exists:
        return exists
    mapping = SectionDisclosureMap(
        section_id=section_id,
        disclosure_id=disclosure_id,
        mapping_type=body.get("mapping_type", "DIRECT"),
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return mapping


@router.post("/sections/{section_id}/blocks", status_code=201)
async def create_block(section_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    section = await db.get(ReportSection, section_id)
    if not section:
        raise NotFound("SECTION_NOT_FOUND", "Section not found")
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    block = ReportBlock(
        tenant_id=ctx.tenant_id,
        project_id=section.project_id,
        section_id=section.id,
        block_type=body.get("block_type", "PARAGRAPH"),
        sort_order=body.get("sort_order", 0),
        current_content=body.get("content", ""),
        current_content_json=body.get("content_json", {}),
        current_revision_no=1,
        source_type="HUMAN",
        created_by=ctx.user_id,
        updated_by=ctx.user_id,
    )
    db.add(block)
    await db.flush()
    db.add(
        ReportBlockRevision(
            block_id=block.id,
            revision_no=1,
            content=block.current_content,
            content_json=block.current_content_json,
            source_type="HUMAN",
            created_by=ctx.user_id,
        )
    )
    await db.commit()
    return block


@router.patch("/blocks/{block_id}")
async def update_block(block_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    block = await db.get(ReportBlock, block_id)
    if not block or block.deleted_at is not None:
        raise NotFound("BLOCK_NOT_FOUND", "Block not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    next_no = block.current_revision_no + 1
    content = body.get("content", block.current_content)
    content_json = body.get("content_json", block.current_content_json)
    block.current_content = content
    block.current_content_json = content_json
    block.current_revision_no = next_no
    block.updated_by = ctx.user_id
    if "sort_order" in body:
        block.sort_order = body["sort_order"]
    db.add(
        ReportBlockRevision(
            block_id=block.id,
            revision_no=next_no,
            content=content,
            content_json=content_json,
            source_type="HUMAN",
            change_reason=body.get("change_reason"),
            created_by=ctx.user_id,
        )
    )
    await db.commit()
    return block


@router.delete("/blocks/{block_id}", status_code=204)
async def delete_block(block_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    block = await db.get(ReportBlock, block_id)
    if not block:
        raise NotFound("BLOCK_NOT_FOUND", "Block not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    block.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/blocks/{block_id}/restore/{revision_id}")
async def restore_block(block_id: UUID, revision_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    block = await db.get(ReportBlock, block_id)
    revision = await db.get(ReportBlockRevision, revision_id)
    if not block or not revision or revision.block_id != block.id:
        raise NotFound("REVISION_NOT_FOUND", "Revision not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    next_no = block.current_revision_no + 1
    block.current_content = revision.content
    block.current_content_json = revision.content_json
    block.current_revision_no = next_no
    block.updated_by = ctx.user_id
    db.add(
        ReportBlockRevision(
            block_id=block.id,
            revision_no=next_no,
            content=revision.content,
            content_json=revision.content_json,
            source_type="RESTORE",
            change_reason=f"Restored revision {revision.revision_no}",
            created_by=ctx.user_id,
        )
    )
    await db.commit()
    return block


async def _resolve_target(db: AsyncSession, target_type: str, target_id: UUID):
    if target_type == "SECTION":
        target = await db.get(ReportSection, target_id)
        return target.project_id if target else None
    if target_type == "BLOCK":
        target = await db.get(ReportBlock, target_id)
        return target.project_id if target else None
    return None


@router.get("/comments")
async def list_comments(target_type: str, target_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    project_id = await _resolve_target(db, target_type, target_id)
    if not project_id:
        raise NotFound("COMMENT_TARGET_NOT_FOUND", "Comment target not found")
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(Comment)
                .where(Comment.target_type == target_type, Comment.target_id == target_id)
                .order_by(Comment.created_at)
            )
        ).all()
    )


@router.post("/comments", status_code=201)
async def create_comment(body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    target_type = body["target_type"]
    target_id = UUID(str(body["target_id"]))
    project_id = await _resolve_target(db, target_type, target_id)
    if not project_id:
        raise NotFound("COMMENT_TARGET_NOT_FOUND", "Comment target not found")
    await ProjectAccess(db).require(project_id, ctx.membership_id, "COMMENT")
    comment = Comment(
        tenant_id=ctx.tenant_id,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        parent_id=UUID(str(body["parent_id"])) if body.get("parent_id") else None,
        body=body["body"],
        created_by=ctx.user_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.post("/comments/{comment_id}/resolve")
async def resolve_comment(comment_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    comment = await db.get(Comment, comment_id)
    if not comment or comment.tenant_id != ctx.tenant_id:
        raise NotFound("COMMENT_NOT_FOUND", "Comment not found")
    await ProjectAccess(db).require(comment.project_id, ctx.membership_id, "COMMENT")
    comment.status = "RESOLVED"
    comment.resolved_by = ctx.user_id
    comment.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return comment


@router.post("/claims/{claim_id}/verify")
async def verify_claim(claim_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    claim = await db.get(Claim, claim_id)
    revision = await db.get(ReportBlockRevision, claim.block_revision_id) if claim else None
    block = await db.get(ReportBlock, revision.block_id) if revision else None
    if not block:
        raise NotFound("CLAIM_NOT_FOUND", "Claim not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "VIEW_PROJECT")
    citations = list((await db.scalars(select(Citation).where(Citation.claim_id == claim_id, Citation.status == "ACTIVE"))).all())
    supported = False
    for citation in citations:
        if not citation.fact_id:
            continue
        fact = await db.get(Fact, citation.fact_id)
        evidence = await db.get(FactEvidence, citation.fact_evidence_id) if citation.fact_evidence_id else None
        if fact and fact.status == "CONFIRMED" and (evidence or fact.source_type == "HUMAN"):
            supported = True
            break
    claim.verification_status = "VERIFIED" if supported else "UNVERIFIED"
    await db.commit()
    return {"claim_id": claim.id, "verification_status": claim.verification_status}


@router.post("/projects/{project_id}/ai/gri-check", status_code=202)
async def gri_check(project_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    disclosures = list((await db.scalars(select(ProjectDisclosure).where(ProjectDisclosure.project_id == project_id))).all())
    requirements = list((await db.scalars(select(ProjectRequirementStatus).where(ProjectRequirementStatus.project_id == project_id))).all())
    summary = {
        "covered": sum(1 for x in requirements if x.status == "COVERED"),
        "partial": sum(1 for x in requirements if x.status == "PARTIAL"),
        "missing": sum(1 for x in requirements if x.status == "MISSING"),
        "not_applicable": sum(1 for x in requirements if x.status == "NOT_APPLICABLE"),
    }
    return {
        "status": "SUCCESS",
        "disclosures": [{"id": x.disclosure_id, "coverage_status": x.coverage_status} for x in disclosures],
        "requirements": summary,
    }


@router.post("/reports/{report_id}/exports/async", status_code=202)
async def create_async_export(report_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    report = await db.get(Report, report_id)
    if not report:
        raise NotFound("REPORT_NOT_FOUND", "Report not found")
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "VIEW_PROJECT")
    format_name = body.get("format", "DOCX").upper()
    if format_name != "DOCX":
        raise DomainError("EXPORT_FORMAT_UNSUPPORTED", "Only DOCX is supported", 422)
    export = ReportExport(report_id=report.id, format="DOCX", status="PENDING", created_by=ctx.user_id)
    db.add(export)
    await db.commit()
    await db.refresh(export)
    export_report.delay(str(export.id))
    return {"export_id": export.id, "status": export.status}


@router.get("/report-exports/{export_id}")
async def get_export(export_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    export = await db.get(ReportExport, export_id)
    report = await db.get(Report, export.report_id) if export else None
    if not report:
        raise NotFound("REPORT_EXPORT_NOT_FOUND", "Report export not found")
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "VIEW_PROJECT")
    download_url = None
    if export.status == "SUCCESS" and export.object_key:
        download_url = await storage().signed_download_url(export.object_key)
    return {"id": export.id, "status": export.status, "format": export.format, "download_url": download_url}
