from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import Forbidden, NotFound
from app.modules.models import ReportTemplateSection, ReportTemplateVersion
from app.modules.reporting_ext import TemplateLifecycle
from app.modules.schemas import (
    ReportTemplateCreate,
    ReportTemplateVersionCreate,
    TemplateSectionCreate,
)

router = APIRouter()


@router.get("/report-templates", tags=["Templates"])
async def report_templates(
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await TemplateLifecycle(db).list(ctx.tenant_id)


@router.post("/report-templates", status_code=201, tags=["Templates"])
async def create_report_template(
    body: ReportTemplateCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    item = await TemplateLifecycle(db).create(ctx.tenant_id, ctx.user_id, body)
    await db.commit()
    return item


@router.get("/report-templates/{template_id}", tags=["Templates"])
async def report_template_detail(
    template_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await TemplateLifecycle(db).get(ctx.tenant_id, template_id)


@router.get("/report-templates/{template_id}/versions", tags=["Templates"])
async def report_template_versions(
    template_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await TemplateLifecycle(db).get(ctx.tenant_id, template_id)
    return list(
        (
            await db.scalars(
                select(ReportTemplateVersion)
                .where(ReportTemplateVersion.template_id == template_id)
                .order_by(ReportTemplateVersion.version_no.desc())
            )
        ).all()
    )


@router.post("/report-templates/{template_id}/versions", status_code=201, tags=["Templates"])
async def create_report_template_version(
    template_id: UUID,
    body: ReportTemplateVersionCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    template = await TemplateLifecycle(db).get(ctx.tenant_id, template_id)
    if template.tenant_id is None or ctx.tenant_role != "ADMIN":
        raise Forbidden("TEMPLATE_WRITE_DENIED", "Template is read-only")
    item = await TemplateLifecycle(db).add_version(template, ctx.user_id, body)
    await db.commit()
    return item


@router.get("/report-template-versions/{version_id}/sections", tags=["Templates"])
async def template_sections(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(ReportTemplateVersion, version_id)
    if not version:
        raise NotFound("TEMPLATE_VERSION_NOT_FOUND", "Template version not found")
    await TemplateLifecycle(db).get(ctx.tenant_id, version.template_id)
    return list(
        (
            await db.scalars(
                select(ReportTemplateSection)
                .where(ReportTemplateSection.template_version_id == version_id)
                .order_by(ReportTemplateSection.level, ReportTemplateSection.sort_order)
            )
        ).all()
    )


@router.post(
    "/report-template-versions/{version_id}/sections",
    status_code=201,
    tags=["Templates"],
)
async def create_template_section(
    version_id: UUID,
    body: TemplateSectionCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    item = await TemplateLifecycle(db).add_section(ctx.tenant_id, version_id, body)
    await db.commit()
    return item
