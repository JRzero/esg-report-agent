from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import Conflict, DomainError, Forbidden, NotFound
from app.integrations.storage import storage
from app.modules.models import (
    AuditLog,
    Company,
    Document,
    DocumentVersion,
    Fact,
    FactRevision,
    MissingItem,
    Project,
    ProjectMember,
    TenantMembership,
)
from app.modules.services import CompanyService, ProjectAccess, audit
from app.workers.tasks import process_document

router = APIRouter(prefix="/api/v1", tags=["Lifecycle"])


def _dump(obj):
    return jsonable_encoder({c.name: getattr(obj, c.name) for c in obj.__table__.columns})


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: UUID,
    body: dict,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    company = await CompanyService(db).get(ctx.tenant_id, company_id)
    before = _dump(company)
    allowed = {"name", "short_name", "registration_no", "industry_code", "country", "region", "description"}
    for key, value in body.items():
        if key in allowed:
            setattr(company, key, value)
    await audit(db, ctx.tenant_id, ctx.user_id, "COMPANY_UPDATE", "company", company.id, before=before, after=_dump(company))
    await db.commit()
    return company


@router.delete("/companies/{company_id}", status_code=204)
async def delete_company(
    company_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    company = await CompanyService(db).get(ctx.tenant_id, company_id)
    active = await db.scalar(
        select(func.count()).select_from(Project).where(
            Project.company_id == company.id,
            Project.deleted_at.is_(None),
            Project.status == "ACTIVE",
        )
    )
    if active:
        raise Conflict("COMPANY_HAS_ACTIVE_PROJECTS", "Company has active projects")
    company.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: UUID,
    body: dict,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_PROJECT")
    project = await db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == ctx.tenant_id,
            Project.deleted_at.is_(None),
        )
    )
    if not project:
        raise NotFound("PROJECT_NOT_FOUND", "Project not found")
    before = _dump(project)
    allowed = {"name", "report_year", "period_start", "period_end", "status", "settings"}
    for key, value in body.items():
        if key in allowed:
            setattr(project, key, value)
    if project.period_start > project.period_end:
        raise DomainError("INVALID_PERIOD", "period_start must not exceed period_end", 422)
    await audit(db, ctx.tenant_id, ctx.user_id, "PROJECT_UPDATE", "project", project.id, project.id, before, _dump(project))
    await db.commit()
    return project


@router.get("/projects/{project_id}/members")
async def list_project_members(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    rows = (
        await db.execute(
            select(ProjectMember, TenantMembership)
            .join(TenantMembership, ProjectMember.membership_id == TenantMembership.id)
            .where(ProjectMember.project_id == project_id, ProjectMember.status == "ACTIVE")
        )
    ).all()
    return [{"project_member": _dump(pm), "membership": _dump(tm)} for pm, tm in rows]


@router.patch("/projects/{project_id}/members/{project_member_id}")
async def update_project_member(
    project_id: UUID,
    project_member_id: UUID,
    body: dict,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "MANAGE_MEMBERS")
    pm = await db.scalar(
        select(ProjectMember).where(ProjectMember.id == project_member_id, ProjectMember.project_id == project_id)
    )
    if not pm:
        raise NotFound("PROJECT_MEMBER_NOT_FOUND", "Project member not found")
    if pm.project_role == "OWNER":
        raise Conflict("OWNER_TRANSFER_REQUIRED", "Use transfer-owner for the project owner")
    role = body.get("project_role")
    if role not in {"EDITOR", "REVIEWER", "CLIENT_MEMBER"}:
        raise DomainError("INVALID_PROJECT_ROLE", "Invalid project role", 422)
    pm.project_role = role
    await db.commit()
    return pm


@router.delete("/projects/{project_id}/members/{project_member_id}", status_code=204)
async def remove_project_member(
    project_id: UUID,
    project_member_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "MANAGE_MEMBERS")
    pm = await db.scalar(
        select(ProjectMember).where(ProjectMember.id == project_member_id, ProjectMember.project_id == project_id)
    )
    if not pm:
        raise NotFound("PROJECT_MEMBER_NOT_FOUND", "Project member not found")
    if pm.project_role == "OWNER":
        raise Conflict("LAST_PROJECT_OWNER", "Transfer project ownership before removal")
    pm.status = "REMOVED"
    await db.commit()


@router.post("/projects/{project_id}/transfer-owner")
async def transfer_owner(
    project_id: UUID,
    body: dict,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    current = await ProjectAccess(db).require(project_id, ctx.membership_id, "MANAGE_MEMBERS")
    if current.project_role != "OWNER":
        raise Forbidden("PROJECT_OWNER_REQUIRED", "Project owner required")
    membership_id = UUID(str(body.get("membership_id")))
    target = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.membership_id == membership_id,
            ProjectMember.status == "ACTIVE",
        )
    )
    if not target:
        raise NotFound("PROJECT_MEMBER_NOT_FOUND", "Target must be an active project member")
    current.project_role = "EDITOR"
    target.project_role = "OWNER"
    project = await db.get(Project, project_id)
    project.owner_membership_id = membership_id
    await db.commit()
    return {"owner_membership_id": membership_id}


@router.get("/projects/{project_id}/documents")
async def list_documents(project_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return list((await db.scalars(select(Document).where(Document.project_id == project_id, Document.deleted_at.is_(None)).order_by(Document.created_at.desc()))).all())


@router.get("/documents/{document_id}")
async def get_document(document_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    document = await db.get(Document, document_id)
    if not document or document.tenant_id != ctx.tenant_id or document.deleted_at is not None:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    versions = list((await db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == document_id).order_by(DocumentVersion.version_no.desc()))).all())
    return {"document": _dump(document), "versions": [_dump(v) for v in versions]}


@router.post("/documents/{document_id}/versions", status_code=201)
async def upload_document_version(
    document_id: UUID,
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if not document or document.tenant_id != ctx.tenant_id:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    data = await file.read()
    max_version = await db.scalar(select(func.max(DocumentVersion.version_no)).where(DocumentVersion.document_id == document_id)) or 0
    version_no = max_version + 1
    ext = Path(file.filename or "").suffix.lower()
    version = DocumentVersion(
        document_id=document.id,
        version_no=version_no,
        original_filename=file.filename or document.name,
        mime_type=file.content_type,
        file_extension=ext,
        file_size=len(data),
        object_key=f"tenants/{ctx.tenant_id}/projects/{document.project_id}/documents/{document.id}/versions/v{version_no}/original{ext}",
        sha256=sha256(data).hexdigest(),
        uploaded_by=ctx.user_id,
    )
    db.add(version)
    await db.flush()
    await storage().put(version.object_key, data, file.content_type)
    await db.commit()
    process_document.delay(str(version.id))
    return {"document_id": document.id, "version_id": version.id, "version_no": version_no, "status": "UPLOADED"}


@router.post("/document-versions/{version_id}/reprocess", status_code=202)
async def reprocess_document(version_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    version = await db.get(DocumentVersion, version_id)
    document = await db.get(Document, version.document_id) if version else None
    if not document:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    version.evidence_parse_status = "PENDING"
    version.context_status = "PENDING"
    version.parse_error = None
    await db.commit()
    process_document.delay(str(version.id))
    return {"version_id": version.id, "status": "PENDING"}


@router.get("/document-versions/{version_id}/download")
async def download_document(version_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    version = await db.get(DocumentVersion, version_id)
    document = await db.get(Document, version.document_id) if version else None
    if not document:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    return {"download_url": await storage().signed_download_url(version.object_key)}


@router.patch("/facts/{fact_id}")
async def update_fact(fact_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    fact = await db.get(Fact, fact_id)
    if not fact or fact.tenant_id != ctx.tenant_id:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, "CONFIRM_FACT")
    allowed = {"name", "number_value", "text_value", "boolean_value", "date_value", "json_value", "raw_value", "unit", "period_start", "period_end", "entity_scope", "dimensions"}
    for key, value in body.items():
        if key in allowed:
            setattr(fact, key, value)
    revision_no = (await db.scalar(select(func.max(FactRevision.revision_no)).where(FactRevision.fact_id == fact.id)) or 0) + 1
    db.add(FactRevision(fact_id=fact.id, revision_no=revision_no, snapshot=_dump(fact), change_type="HUMAN_EDIT", changed_by=ctx.user_id))
    await db.commit()
    return fact


@router.post("/facts/{fact_id}/reject")
async def reject_fact(fact_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    fact = await db.get(Fact, fact_id)
    if not fact or fact.tenant_id != ctx.tenant_id:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, "CONFIRM_FACT")
    fact.status = "REJECTED"
    revision_no = (await db.scalar(select(func.max(FactRevision.revision_no)).where(FactRevision.fact_id == fact.id)) or 0) + 1
    db.add(FactRevision(fact_id=fact.id, revision_no=revision_no, snapshot={"status": "REJECTED", "reason": body.get("reason")}, change_type="REJECTED", changed_by=ctx.user_id))
    await db.commit()
    return fact


@router.get("/facts/{fact_id}/revisions")
async def fact_revisions(fact_id: UUID, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    fact = await db.get(Fact, fact_id)
    if not fact or fact.tenant_id != ctx.tenant_id:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, "VIEW_FACT")
    return list((await db.scalars(select(FactRevision).where(FactRevision.fact_id == fact_id).order_by(FactRevision.revision_no.desc()))).all())


@router.patch("/missing-items/{item_id}")
async def update_missing_item(item_id: UUID, body: dict, ctx: RequestContext = Depends(current_context), db=Depends(get_db)):
    item = await db.get(MissingItem, item_id)
    if not item or item.tenant_id != ctx.tenant_id:
        raise NotFound("MISSING_ITEM_NOT_FOUND", "Missing item not found")
    await ProjectAccess(db).require(item.project_id, ctx.membership_id, "EDIT_PROJECT")
    for key in {"status", "priority", "suggested_material"}:
        if key in body:
            setattr(item, key, body[key])
    await db.commit()
    return item


@router.get("/audit-logs")
async def audit_logs(
    project_id: UUID | None = None,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    query = select(AuditLog).where(AuditLog.tenant_id == ctx.tenant_id)
    if project_id:
        query = query.where(AuditLog.project_id == project_id)
    return list((await db.scalars(query.order_by(AuditLog.created_at.desc()).limit(500))).all())
