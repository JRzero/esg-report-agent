from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import Conflict, DomainError, Forbidden, NotFound
from app.core.security import create_token, decode_token
from app.integrations.export import render_docx
from app.integrations.storage import storage
from app.modules.models import (
    AITask,
    AuditLog,
    Citation,
    Claim,
    Disclosure,
    DisclosureRequirement,
    Document,
    DocumentAnchor,
    DocumentVersion,
    Fact,
    FactConflictGroup,
    FactConflictMember,
    FactEvidence,
    MissingItem,
    ProjectDisclosure,
    ProjectMember,
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
    Standard,
    StandardVersion,
    Tenant,
    TenantMembership,
    User,
)
from app.modules.schemas import (
    BlockCreate,
    BlockUpdate,
    ClaimVerifyResponse,
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
    FactCreate,
    FactRejectRequest,
    FactUpdate,
    LoginRequest,
    MembershipRead,
    MissingItemUpdate,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectMemberUpdate,
    ProjectRead,
    ProjectUpdate,
    RefreshRequest,
    ReportCreate,
    ReportTemplateCreate,
    ReportTemplateVersionCreate,
    SectionCreate,
    SectionUpdate,
    TaskRead,
    TemplateSectionCreate,
    TokenResponse,
    TransferOwnerRequest,
    UserCreate,
    UserRead,
)
from app.modules.services import (
    CompanyService,
    FactService,
    IdentityService,
    ProjectAccess,
    ProjectService,
    ReportService,
    StandardService,
    TaskService,
    TemplateService,
    TenantService,
)
from app.workers.tasks import process_document, run_ai_task

router = APIRouter(prefix="/api/v1")


async def _document_for_version(db: AsyncSession, version_id: UUID) -> tuple[DocumentVersion, Document]:
    version = await db.get(DocumentVersion, version_id)
    document = await db.get(Document, version.document_id) if version else None
    if not version or not document or document.deleted_at is not None:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    return version, document


async def _report(db: AsyncSession, report_id: UUID) -> Report:
    report = await db.get(Report, report_id)
    if not report:
        raise NotFound("REPORT_NOT_FOUND", "Report not found")
    return report


async def _section(db: AsyncSession, section_id: UUID) -> ReportSection:
    section = await db.get(ReportSection, section_id)
    if not section:
        raise NotFound("SECTION_NOT_FOUND", "Section not found")
    return section


async def _block(db: AsyncSession, block_id: UUID) -> ReportBlock:
    block = await db.get(ReportBlock, block_id)
    if not block or block.deleted_at is not None:
        raise NotFound("BLOCK_NOT_FOUND", "Block not found")
    return block


@router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user, membership = await IdentityService(db).authenticate(body.email, body.password)
    access = create_token(str(user.id), str(membership.tenant_id), str(membership.id), "access")
    refresh_token = create_token(str(user.id), str(membership.tenant_id), str(membership.id), "refresh")
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        expires_in=get_settings().jwt_access_token_minutes * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except Exception as exc:
        raise DomainError("AUTH_INVALID_TOKEN", "Invalid refresh token", 401) from exc
    if payload.get("type") != "refresh":
        raise DomainError("AUTH_INVALID_TOKEN", "Refresh token required", 401)
    user_id = UUID(payload["sub"])
    tenant_id = UUID(payload["tenant_id"])
    membership_id = UUID(payload["membership_id"])
    membership = await db.scalar(
        select(TenantMembership).where(
            TenantMembership.id == membership_id,
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "ACTIVE",
        )
    )
    if not membership:
        raise DomainError("AUTH_INVALID_MEMBERSHIP", "Membership is not active", 401)
    access = create_token(str(user_id), str(tenant_id), str(membership_id), "access")
    refresh_token = create_token(str(user_id), str(tenant_id), str(membership_id), "refresh")
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        expires_in=get_settings().jwt_access_token_minutes * 60,
    )


@router.get("/auth/me", tags=["Auth"])
async def me(ctx: RequestContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, ctx.user_id)
    membership = await db.get(TenantMembership, ctx.membership_id)
    tenant = await db.get(Tenant, ctx.tenant_id)
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "tenant": {"id": tenant.id, "name": tenant.name, "code": tenant.code},
        "membership": {
            "id": membership.id,
            "tenant_role": membership.tenant_role,
            "member_type": membership.member_type,
            "company_id": membership.company_id,
        },
    }


@router.get("/tenant/members", tags=["Tenants"])
async def tenant_members(ctx: RequestContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    rows = await TenantService(db).list_members(ctx.tenant_id)
    return [
        {
            "membership": MembershipRead.model_validate(membership).model_dump(),
            "user": UserRead.model_validate(user).model_dump(),
        }
        for membership, user in rows
    ]


@router.post("/tenant/members", status_code=201, tags=["Tenants"])
async def create_tenant_member(
    body: UserCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    if body.company_id:
        await CompanyService(db).get(ctx.tenant_id, body.company_id)
    user, membership = await TenantService(db).create_member(ctx.tenant_id, ctx.user_id, body)
    await db.commit()
    return {
        "user": UserRead.model_validate(user),
        "membership": MembershipRead.model_validate(membership),
    }


@router.get("/companies", response_model=list[CompanyRead], tags=["Companies"])
async def companies(ctx: RequestContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    return await CompanyService(db).list(ctx.tenant_id)


@router.post("/companies", response_model=CompanyRead, status_code=201, tags=["Companies"])
async def create_company(
    body: CompanyCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    obj = await CompanyService(db).create(ctx.tenant_id, ctx.user_id, body)
    await db.commit()
    return obj


@router.get("/companies/{company_id}", response_model=CompanyRead, tags=["Companies"])
async def get_company(
    company_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await CompanyService(db).get(ctx.tenant_id, company_id)


@router.patch("/companies/{company_id}", response_model=CompanyRead, tags=["Companies"])
async def update_company(
    company_id: UUID,
    body: CompanyUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    obj = await CompanyService(db).update(ctx.tenant_id, ctx.user_id, company_id, body)
    await db.commit()
    return obj


@router.delete("/companies/{company_id}", status_code=204, tags=["Companies"])
async def delete_company(
    company_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    await CompanyService(db).delete(ctx.tenant_id, ctx.user_id, company_id)
    await db.commit()


@router.get("/projects", response_model=list[ProjectRead], tags=["Projects"])
async def projects(ctx: RequestContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    return await ProjectService(db).list(ctx.tenant_id, ctx.membership_id)


@router.post("/projects", response_model=ProjectRead, status_code=201, tags=["Projects"])
async def create_project(
    body: ProjectCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await ProjectService(db).create(ctx.tenant_id, ctx.user_id, ctx.membership_id, body)
    await db.commit()
    return obj


@router.get("/projects/{project_id}", response_model=ProjectRead, tags=["Projects"])
async def project(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await ProjectService(db).get(ctx.tenant_id, project_id, ctx.membership_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead, tags=["Projects"])
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await ProjectService(db).update(
        ctx.tenant_id, ctx.user_id, ctx.membership_id, project_id, body
    )
    await db.commit()
    return obj


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberRead], tags=["Project Members"])
async def project_members(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await ProjectService(db).list_members(project_id, ctx.membership_id)


@router.post(
    "/projects/{project_id}/members",
    response_model=ProjectMemberRead,
    status_code=201,
    tags=["Project Members"],
)
async def add_member(
    project_id: UUID,
    body: ProjectMemberCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await ProjectService(db).add_member(
        ctx.tenant_id,
        ctx.user_id,
        ctx.membership_id,
        project_id,
        body.membership_id,
        body.project_role,
    )
    await db.commit()
    return obj


@router.patch(
    "/projects/{project_id}/members/{project_member_id}",
    response_model=ProjectMemberRead,
    tags=["Project Members"],
)
async def update_project_member(
    project_id: UUID,
    project_member_id: UUID,
    body: ProjectMemberUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await ProjectService(db).update_member_role(
        ctx.tenant_id,
        ctx.user_id,
        ctx.membership_id,
        project_id,
        project_member_id,
        body.project_role,
    )
    await db.commit()
    return obj


@router.delete("/projects/{project_id}/members/{project_member_id}", status_code=204, tags=["Project Members"])
async def remove_project_member(
    project_id: UUID,
    project_member_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectService(db).remove_member(
        ctx.tenant_id,
        ctx.user_id,
        ctx.membership_id,
        project_id,
        project_member_id,
    )
    await db.commit()


@router.post("/projects/{project_id}/transfer-owner", response_model=ProjectMemberRead, tags=["Project Members"])
async def transfer_owner(
    project_id: UUID,
    body: TransferOwnerRequest,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await ProjectService(db).transfer_owner(
        ctx.tenant_id,
        ctx.user_id,
        ctx.membership_id,
        project_id,
        body.membership_id,
    )
    await db.commit()
    return obj


async def _read_upload_limited(file: UploadFile) -> tuple[bytes, str]:
    limit = get_settings().max_upload_bytes
    payload = bytearray()
    digest = sha256()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        payload.extend(chunk)
        if len(payload) > limit:
            raise DomainError(
                "FILE_TOO_LARGE",
                "Uploaded file exceeds configured size limit",
                413,
            )
        digest.update(chunk)
    if not payload:
        raise DomainError("EMPTY_FILE", "Uploaded file is empty", 422)
    return bytes(payload), digest.hexdigest()


async def _create_document_version(
    db: AsyncSession,
    document: Document,
    file: UploadFile,
    user_id: UUID,
) -> DocumentVersion:
    data, digest = await _read_upload_limited(file)
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".txt", ".md", ".csv"}:
        raise DomainError("UNSUPPORTED_FILE_TYPE", f"Unsupported file type: {extension}", 422)
    next_version = (
        await db.scalar(
            select(func.max(DocumentVersion.version_no)).where(
                DocumentVersion.document_id == document.id
            )
        )
        or 0
    ) + 1
    version = DocumentVersion(
        document_id=document.id,
        version_no=next_version,
        original_filename=file.filename or document.name,
        mime_type=file.content_type,
        file_extension=extension,
        file_size=len(data),
        object_key=(
            f"tenants/{document.tenant_id}/projects/{document.project_id}/documents/"
            f"{document.id}/versions/v{next_version}/original{extension}"
        ),
        sha256=digest,
        uploaded_by=user_id,
    )
    db.add(version)
    await db.flush()
    await storage().put(version.object_key, data, file.content_type)
    return version


@router.get("/projects/{project_id}/documents", tags=["Documents"])
async def documents(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    docs = list(
        (
            await db.scalars(
                select(Document)
                .where(Document.project_id == project_id, Document.deleted_at.is_(None))
                .order_by(Document.created_at.desc())
            )
        ).all()
    )
    return docs


@router.post("/projects/{project_id}/documents", status_code=201, tags=["Documents"])
async def upload_document(
    project_id: UUID,
    file: UploadFile = File(...),
    source_type: str = Form("EVIDENCE"),
    category_code: str | None = Form(None),
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    if source_type not in {"EVIDENCE", "REFERENCE", "STANDARD", "HISTORICAL"}:
        raise DomainError("INVALID_DOCUMENT_SOURCE_TYPE", "Invalid source_type", 422)
    document = Document(
        tenant_id=ctx.tenant_id,
        project_id=project_id,
        name=file.filename or "document",
        source_type=source_type,
        category_code=category_code,
        created_by=ctx.user_id,
    )
    db.add(document)
    await db.flush()
    version = await _create_document_version(db, document, file, ctx.user_id)
    await db.commit()
    process_document.delay(str(version.id))
    return {"document_id": document.id, "version_id": version.id, "status": "UPLOADED"}


@router.get("/documents/{document_id}", tags=["Documents"])
async def document_detail(
    document_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if not document or document.deleted_at is not None:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    versions = list(
        (
            await db.scalars(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version_no.desc())
            )
        ).all()
    )
    return {"document": document, "versions": versions}


@router.post("/documents/{document_id}/versions", status_code=201, tags=["Documents"])
async def upload_document_version(
    document_id: UUID,
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if not document or document.deleted_at is not None:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    version = await _create_document_version(db, document, file, ctx.user_id)
    await db.commit()
    process_document.delay(str(version.id))
    return {"document_id": document.id, "version_id": version.id, "status": "UPLOADED"}


@router.get("/document-versions/{version_id}", tags=["Documents"])
async def document_version_detail(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version, document = await _document_for_version(db, version_id)
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    return version


@router.get("/document-versions/{version_id}/anchors", tags=["Documents"])
async def anchors(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    _, document = await _document_for_version(db, version_id)
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(DocumentAnchor).where(DocumentAnchor.document_version_id == version_id)
            )
        ).all()
    )


@router.post("/document-versions/{version_id}/reprocess", status_code=202, tags=["Documents"])
async def reprocess_document(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version, document = await _document_for_version(db, version_id)
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    version.evidence_parse_status = "PENDING"
    version.context_status = "PENDING"
    version.parse_error = None
    await db.commit()
    process_document.delay(str(version.id))
    return {"version_id": version.id, "status": "PENDING"}


@router.get("/document-versions/{version_id}/download", tags=["Documents"])
async def download_document_version(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version, document = await _document_for_version(db, version_id)
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    return {"download_url": await storage().signed_download_url(version.object_key)}


@router.get("/projects/{project_id}/facts", tags=["Facts"])
async def facts(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_FACT")
    return await FactService(db).list(project_id)


@router.post("/projects/{project_id}/facts", status_code=201, tags=["Facts"])
async def create_fact(
    project_id: UUID,
    body: FactCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "CONFIRM_FACT")
    obj = await FactService(db).create_candidate(
        ctx.tenant_id, project_id, ctx.user_id, body, status="PENDING"
    )
    await db.commit()
    return obj


@router.patch("/facts/{fact_id}", tags=["Facts"])
async def update_fact(
    fact_id: UUID,
    body: FactUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await db.get(Fact, fact_id)
    if not fact:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, "CONFIRM_FACT")
    obj = await FactService(db).update(fact.project_id, fact_id, ctx.user_id, body)
    await db.commit()
    return obj


@router.post("/facts/{fact_id}/confirm", tags=["Facts"])
async def confirm_fact(
    fact_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await db.get(Fact, fact_id)
    if not fact:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, "CONFIRM_FACT")
    obj = await FactService(db).confirm(fact.project_id, fact.id, ctx.user_id)
    await db.commit()
    return obj


@router.post("/facts/{fact_id}/reject", tags=["Facts"])
async def reject_fact(
    fact_id: UUID,
    body: FactRejectRequest,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await db.get(Fact, fact_id)
    if not fact:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, "CONFIRM_FACT")
    obj = await FactService(db).reject(fact.project_id, fact.id, ctx.user_id, body.reason)
    await db.commit()
    return obj


@router.get("/facts/{fact_id}/evidence", tags=["Facts"])
async def fact_evidence(
    fact_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    fact = await db.get(Fact, fact_id)
    if not fact:
        raise NotFound("FACT_NOT_FOUND", "Fact not found")
    await ProjectAccess(db).require(fact.project_id, ctx.membership_id, "VIEW_FACT")
    query = (
        select(FactEvidence, DocumentAnchor, DocumentVersion, Document)
        .join(DocumentAnchor, FactEvidence.document_anchor_id == DocumentAnchor.id)
        .join(DocumentVersion, DocumentAnchor.document_version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(FactEvidence.fact_id == fact_id)
    )
    rows = (await db.execute(query)).all()
    return [
        {
            "fact_evidence_id": evidence.id,
            "anchor": {
                "id": anchor.id,
                "type": anchor.anchor_type,
                "page": anchor.page_start,
                "sheet": anchor.sheet_name,
                "cell": anchor.cell_range,
                "raw_text": anchor.raw_text,
            },
            "document": {
                "id": document.id,
                "name": document.name,
                "source_type": document.source_type,
                "version_id": version.id,
            },
        }
        for evidence, anchor, version, document in rows
    ]


@router.get("/projects/{project_id}/fact-conflicts", tags=["Facts"])
async def fact_conflicts(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_FACT")
    return list(
        (
            await db.scalars(
                select(FactConflictGroup)
                .where(FactConflictGroup.project_id == project_id)
                .order_by(FactConflictGroup.created_at.desc())
            )
        ).all()
    )


@router.post("/fact-conflicts/{group_id}/resolve", tags=["Facts"])
async def resolve_fact_conflict(
    group_id: UUID,
    fact_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    group = await db.get(FactConflictGroup, group_id)
    if not group:
        raise NotFound("FACT_CONFLICT_NOT_FOUND", "Fact conflict not found")
    await ProjectAccess(db).require(group.project_id, ctx.membership_id, "CONFIRM_FACT")
    fact = await db.get(Fact, fact_id)
    is_member = await db.scalar(
        select(FactConflictMember).where(
            FactConflictMember.conflict_group_id == group.id,
            FactConflictMember.fact_id == fact_id,
        )
    )
    if not fact or fact.project_id != group.project_id or not is_member:
        raise NotFound("FACT_NOT_FOUND", "Fact not found in conflict group")
    group.status = "RESOLVED"
    group.resolved_fact_id = fact_id
    group.resolved_by = ctx.user_id
    group.resolved_at = datetime.now(timezone.utc)
    members = list(
        (
            await db.scalars(
                select(Fact)
                .join(FactConflictMember, FactConflictMember.fact_id == Fact.id)
                .where(FactConflictMember.conflict_group_id == group.id)
            )
        ).all()
    )
    for item in members:
        item.status = "CONFIRMED" if item.id == fact_id else "REJECTED"
    await db.commit()
    return {"status": "RESOLVED", "resolved_fact_id": fact_id}


@router.get("/standards", tags=["Standards"])
async def standards(ctx: RequestContext = Depends(current_context), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Standard).order_by(Standard.code))).all())


@router.get("/standards/{standard_id}/versions", tags=["Standards"])
async def standard_versions(
    standard_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return list(
        (
            await db.scalars(
                select(StandardVersion)
                .where(StandardVersion.standard_id == standard_id)
                .order_by(StandardVersion.created_at.desc())
            )
        ).all()
    )


@router.get("/standard-versions/{version_id}/disclosures", tags=["Standards"])
async def disclosures(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return list(
        (
            await db.scalars(
                select(Disclosure)
                .where(Disclosure.standard_version_id == version_id)
                .order_by(Disclosure.sort_order)
            )
        ).all()
    )


@router.get("/disclosures/{disclosure_id}/requirements", tags=["Standards"])
async def disclosure_requirements(
    disclosure_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return list(
        (
            await db.scalars(
                select(DisclosureRequirement)
                .where(DisclosureRequirement.disclosure_id == disclosure_id)
                .order_by(DisclosureRequirement.sort_order)
            )
        ).all()
    )


@router.post("/projects/{project_id}/standards/{version_id}", status_code=201, tags=["Standards"])
async def attach_standard(
    project_id: UUID,
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_PROJECT")
    obj = await StandardService(db).attach_to_project(project_id, version_id)
    await db.commit()
    return obj


@router.post("/projects/{project_id}/ai/disclosure-mapping", tags=["AI"])
async def disclosure_mapping(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_PROJECT")
    count = await StandardService(db).map_confirmed_facts(project_id)
    await db.commit()
    return {"status": "SUCCESS", "mappings_created": count}


@router.get("/projects/{project_id}/disclosures", tags=["Standards"])
async def project_disclosures(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    query = (
        select(ProjectDisclosure, Disclosure)
        .join(Disclosure, ProjectDisclosure.disclosure_id == Disclosure.id)
        .where(ProjectDisclosure.project_id == project_id)
    )
    rows = (await db.execute(query)).all()
    return [
        {
            "id": pd.id,
            "code": disclosure.code,
            "title": disclosure.title,
            "applicability": pd.applicability,
            "coverage_status": pd.coverage_status,
        }
        for pd, disclosure in rows
    ]


@router.get("/projects/{project_id}/requirements", tags=["Standards"])
async def project_requirements(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    query = (
        select(ProjectRequirementStatus, DisclosureRequirement)
        .join(
            DisclosureRequirement,
            ProjectRequirementStatus.requirement_id == DisclosureRequirement.id,
        )
        .where(ProjectRequirementStatus.project_id == project_id)
    )
    rows = (await db.execute(query)).all()
    return [
        {
            "id": status.id,
            "requirement_id": requirement.id,
            "code": requirement.requirement_code,
            "content": requirement.content,
            "status": status.status,
            "reason": status.reason,
        }
        for status, requirement in rows
    ]


@router.post("/projects/{project_id}/ai/missing-data-analysis", tags=["AI"])
async def missing_analysis(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_PROJECT")
    items = await StandardService(db).generate_missing_items(ctx.tenant_id, project_id)
    await db.commit()
    return {"status": "SUCCESS", "missing_items_created": len(items)}


@router.get("/projects/{project_id}/missing-items", tags=["Standards"])
async def missing_items(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(MissingItem)
                .where(MissingItem.project_id == project_id)
                .order_by(MissingItem.created_at.desc())
            )
        ).all()
    )


@router.patch("/missing-items/{item_id}", tags=["Standards"])
async def update_missing_item(
    item_id: UUID,
    body: MissingItemUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(MissingItem, item_id)
    if not item:
        raise NotFound("MISSING_ITEM_NOT_FOUND", "Missing item not found")
    await ProjectAccess(db).require(item.project_id, ctx.membership_id, "EDIT_PROJECT")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await db.commit()
    return item


@router.get("/report-templates", tags=["Templates"])
async def report_templates(
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    return await TemplateService(db).list(ctx.tenant_id)


@router.post("/report-templates", status_code=201, tags=["Templates"])
async def create_report_template(
    body: ReportTemplateCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    template = await TemplateService(db).create(ctx.tenant_id, ctx.user_id, body)
    await db.commit()
    return template


@router.post("/report-templates/{template_id}/versions", status_code=201, tags=["Templates"])
async def create_template_version(
    template_id: UUID,
    body: ReportTemplateVersionCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(ReportTemplate, template_id)
    if not template or template.status != "ACTIVE" or template.tenant_id not in {None, ctx.tenant_id}:
        raise NotFound("REPORT_TEMPLATE_NOT_FOUND", "Report template not found")
    if template.tenant_id is None:
        raise Conflict("SYSTEM_TEMPLATE_IMMUTABLE", "System template cannot be modified")
    version = await TemplateService(db).create_version(template, ctx.user_id, body)
    await db.commit()
    return version


@router.post("/report-template-versions/{version_id}/sections", status_code=201, tags=["Templates"])
async def create_template_section(
    version_id: UUID,
    body: TemplateSectionCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(ReportTemplateVersion, version_id)
    template = await db.get(ReportTemplate, version.template_id) if version else None
    if not version or not template or template.tenant_id != ctx.tenant_id:
        raise NotFound("REPORT_TEMPLATE_VERSION_NOT_FOUND", "Report template version not found")
    if body.parent_id:
        parent = await db.get(ReportTemplateSection, body.parent_id)
        if not parent or parent.template_version_id != version_id:
            raise DomainError("INVALID_TEMPLATE_PARENT", "Parent section must belong to same version", 422)
    section = ReportTemplateSection(template_version_id=version_id, **body.model_dump())
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


@router.get("/report-template-versions/{version_id}/sections", tags=["Templates"])
async def template_sections(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(ReportTemplateVersion, version_id)
    template = await db.get(ReportTemplate, version.template_id) if version else None
    if not version or not template or template.tenant_id not in {None, ctx.tenant_id}:
        raise NotFound("REPORT_TEMPLATE_VERSION_NOT_FOUND", "Report template version not found")
    return list(
        (
            await db.scalars(
                select(ReportTemplateSection)
                .where(ReportTemplateSection.template_version_id == version_id)
                .order_by(ReportTemplateSection.level, ReportTemplateSection.sort_order)
            )
        ).all()
    )


@router.get("/projects/{project_id}/reports", tags=["Reports"])
async def reports(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(Report)
                .where(Report.project_id == project_id)
                .order_by(Report.created_at.desc())
            )
        ).all()
    )


@router.post("/projects/{project_id}/reports", status_code=201, tags=["Reports"])
async def create_report(
    project_id: UUID,
    body: ReportCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_REPORT")
    if body.template_version_id:
        version = await db.get(ReportTemplateVersion, body.template_version_id)
        template = await db.get(ReportTemplate, version.template_id) if version else None
        if not version or not template or template.tenant_id not in {None, ctx.tenant_id}:
            raise NotFound("REPORT_TEMPLATE_VERSION_NOT_FOUND", "Report template version not found")
    report = await ReportService(db).create_report(
        ctx.tenant_id,
        project_id,
        ctx.user_id,
        body.title,
        body.language,
        body.template_version_id,
    )
    await db.commit()
    return report


@router.get("/reports/{report_id}", tags=["Reports"])
async def report_detail(
    report_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    report = await _report(db, report_id)
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "VIEW_PROJECT")
    return report


@router.post("/reports/{report_id}/sections", status_code=201, tags=["Reports"])
async def create_section(
    report_id: UUID,
    body: SectionCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    report = await _report(db, report_id)
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "EDIT_REPORT")
    if body.parent_id:
        parent = await db.get(ReportSection, body.parent_id)
        if not parent or parent.report_id != report_id:
            raise DomainError("INVALID_SECTION_PARENT", "Parent section must belong to same report", 422)
    section = ReportSection(
        tenant_id=ctx.tenant_id,
        project_id=report.project_id,
        report_id=report_id,
        **body.model_dump(),
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


@router.get("/reports/{report_id}/sections", tags=["Reports"])
async def sections(
    report_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    report = await _report(db, report_id)
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(ReportSection)
                .where(ReportSection.report_id == report_id)
                .order_by(ReportSection.sort_order)
            )
        ).all()
    )


@router.patch("/sections/{section_id}", tags=["Reports"])
async def update_section(
    section_id: UUID,
    body: SectionUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await _section(db, section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    values = body.model_dump(exclude_unset=True)
    if "parent_id" in values and values["parent_id"]:
        parent = await db.get(ReportSection, values["parent_id"])
        if not parent or parent.report_id != section.report_id or parent.id == section.id:
            raise DomainError("INVALID_SECTION_PARENT", "Invalid parent section", 422)
    for key, value in values.items():
        setattr(section, key, value)
    await db.commit()
    return section


@router.post("/sections/{section_id}/disclosures/{disclosure_id}", status_code=201, tags=["Reports"])
async def map_section_disclosure(
    section_id: UUID,
    disclosure_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await _section(db, section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    disclosure = await db.get(Disclosure, disclosure_id)
    if not disclosure:
        raise NotFound("DISCLOSURE_NOT_FOUND", "Disclosure not found")
    existing = await db.scalar(
        select(SectionDisclosureMap).where(
            SectionDisclosureMap.section_id == section_id,
            SectionDisclosureMap.disclosure_id == disclosure_id,
        )
    )
    if existing:
        return existing
    mapping = SectionDisclosureMap(section_id=section_id, disclosure_id=disclosure_id)
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return mapping


@router.get("/sections/{section_id}/blocks", tags=["Reports"])
async def report_blocks(
    section_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await _section(db, section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "VIEW_PROJECT")
    return await ReportService(db).blocks(section_id)


@router.post("/sections/{section_id}/blocks", status_code=201, tags=["Reports"])
async def create_block(
    section_id: UUID,
    body: BlockCreate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await _section(db, section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "EDIT_REPORT")
    block = await ReportService(db).create_block(
        ctx.tenant_id, section.project_id, section.id, ctx.user_id, body
    )
    await db.commit()
    return block


@router.patch("/blocks/{block_id}", tags=["Reports"])
async def update_block(
    block_id: UUID,
    body: BlockUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    block = await _block(db, block_id)
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    block = await ReportService(db).update_block(block, ctx.user_id, body)
    await db.commit()
    return block


@router.delete("/blocks/{block_id}", status_code=204, tags=["Reports"])
async def delete_block(
    block_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    block = await _block(db, block_id)
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    block.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/blocks/{block_id}/revisions", tags=["Reports"])
async def block_revisions(
    block_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    block = await _block(db, block_id)
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(ReportBlockRevision)
                .where(ReportBlockRevision.block_id == block_id)
                .order_by(ReportBlockRevision.revision_no.desc())
            )
        ).all()
    )


@router.post("/blocks/{block_id}/restore/{revision_id}", tags=["Reports"])
async def restore_block(
    block_id: UUID,
    revision_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    block = await _block(db, block_id)
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "EDIT_REPORT")
    revision = await db.get(ReportBlockRevision, revision_id)
    if not revision or revision.block_id != block_id:
        raise NotFound("REVISION_NOT_FOUND", "Revision not found")
    block = await ReportService(db).restore_block(block, revision, ctx.user_id)
    await db.commit()
    return block


@router.get("/block-revisions/{revision_id}/claims", tags=["Reports"])
async def revision_claims(
    revision_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    revision = await db.get(ReportBlockRevision, revision_id)
    block = await db.get(ReportBlock, revision.block_id) if revision else None
    if not block:
        raise NotFound("REVISION_NOT_FOUND", "Revision not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "VIEW_PROJECT")
    return list((await db.scalars(select(Claim).where(Claim.block_revision_id == revision_id))).all())


@router.get("/claims/{claim_id}/citations", tags=["Reports"])
async def claim_citations(
    claim_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    claim = await db.get(Claim, claim_id)
    revision = await db.get(ReportBlockRevision, claim.block_revision_id) if claim else None
    block = await db.get(ReportBlock, revision.block_id) if revision else None
    if not block:
        raise NotFound("CLAIM_NOT_FOUND", "Claim not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "VIEW_PROJECT")
    return list((await db.scalars(select(Citation).where(Citation.claim_id == claim_id))).all())


@router.post("/claims/{claim_id}/verify", response_model=ClaimVerifyResponse, tags=["Reports"])
async def verify_claim(
    claim_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    claim = await db.get(Claim, claim_id)
    revision = await db.get(ReportBlockRevision, claim.block_revision_id) if claim else None
    block = await db.get(ReportBlock, revision.block_id) if revision else None
    if not block or not claim:
        raise NotFound("CLAIM_NOT_FOUND", "Claim not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "VIEW_PROJECT")
    status, reasons = await ReportService(db).verify_claim(claim)
    await db.commit()
    return ClaimVerifyResponse(claim_id=claim.id, status=status, reasons=reasons)


@router.get("/citations/{citation_id}/trace", tags=["Reports"])
async def citation_trace(
    citation_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    citation = await db.get(Citation, citation_id)
    if not citation:
        raise NotFound("CITATION_NOT_FOUND", "Citation not found")
    claim = await db.get(Claim, citation.claim_id)
    revision = await db.get(ReportBlockRevision, claim.block_revision_id) if claim else None
    block = await db.get(ReportBlock, revision.block_id) if revision else None
    if not block:
        raise NotFound("CITATION_NOT_FOUND", "Citation not found")
    await ProjectAccess(db).require(block.project_id, ctx.membership_id, "VIEW_PROJECT")
    fact = await db.get(Fact, citation.fact_id) if citation.fact_id else None
    anchor = await db.get(DocumentAnchor, citation.document_anchor_id) if citation.document_anchor_id else None
    document = None
    version = None
    if anchor:
        version = await db.get(DocumentVersion, anchor.document_version_id)
        document = await db.get(Document, version.document_id) if version else None
    return {
        "claim": {
            "id": claim.id,
            "text": claim.claim_text,
            "verification_status": claim.verification_status,
        },
        "fact": (
            {"id": fact.id, "name": fact.name, "status": fact.status, "unit": fact.unit}
            if fact
            else None
        ),
        "anchor": (
            {
                "id": anchor.id,
                "type": anchor.anchor_type,
                "page": anchor.page_start,
                "sheet": anchor.sheet_name,
                "cell": anchor.cell_range,
                "raw_text": anchor.raw_text,
            }
            if anchor
            else None
        ),
        "document": (
            {
                "id": document.id,
                "name": document.name,
                "source_type": document.source_type,
                "version_id": version.id,
            }
            if document
            else None
        ),
    }


async def queue_ai(
    db: AsyncSession,
    ctx: RequestContext,
    project_id: UUID,
    task_type: str,
    target_type: str,
    target_id: UUID,
    idempotency_key: str | None = None,
):
    task = await TaskService(db).create(
        ctx.tenant_id,
        project_id,
        ctx.user_id,
        task_type,
        target_type,
        target_id,
        idempotency_key=idempotency_key,
    )
    await db.commit()
    if task.status == "PENDING":
        run_ai_task.delay(str(task.id))
    return {"task_id": task.id, "status": task.status}


@router.post("/document-versions/{version_id}/extract-facts", status_code=202, tags=["AI"])
async def extract_facts(
    version_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    _, document = await _document_for_version(db, version_id)
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "CONFIRM_FACT")
    return await queue_ai(
        db,
        ctx,
        document.project_id,
        "FACT_EXTRACTION",
        "DOCUMENT_VERSION",
        version_id,
        idempotency_key,
    )


@router.post("/sections/{section_id}/ai/writing-plan", status_code=202, tags=["AI"])
async def plan(
    section_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await _section(db, section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "GENERATE_REPORT")
    return await queue_ai(
        db,
        ctx,
        section.project_id,
        "SECTION_PLANNING",
        "SECTION",
        section_id,
        idempotency_key,
    )


@router.post("/sections/{section_id}/ai/generate", status_code=202, tags=["AI"])
async def generate(
    section_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    section = await _section(db, section_id)
    await ProjectAccess(db).require(section.project_id, ctx.membership_id, "GENERATE_REPORT")
    return await queue_ai(
        db,
        ctx,
        section.project_id,
        "SECTION_WRITING",
        "SECTION",
        section_id,
        idempotency_key,
    )


@router.post("/reports/{report_id}/ai/consistency-check", tags=["AI"])
async def consistency_check(
    report_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    report = await _report(db, report_id)
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "VIEW_PROJECT")
    return {"status": "SUCCESS", "issues": await ReportService(db).consistency(report_id)}


@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead], tags=["Tasks"])
async def project_tasks(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return await TaskService(db).list(ctx.tenant_id, project_id)


@router.get("/tasks/{task_id}", response_model=TaskRead, tags=["Tasks"])
async def task(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await db.get(AITask, task_id)
    if not obj or obj.tenant_id != ctx.tenant_id:
        raise NotFound("TASK_NOT_FOUND", "Task not found")
    if obj.project_id:
        await ProjectAccess(db).require(obj.project_id, ctx.membership_id, "VIEW_PROJECT")
    return obj


@router.post("/tasks/{task_id}/retry", response_model=TaskRead, tags=["Tasks"])
async def retry_task(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await db.get(AITask, task_id)
    if not obj or obj.tenant_id != ctx.tenant_id:
        raise NotFound("TASK_NOT_FOUND", "Task not found")
    if obj.project_id:
        await ProjectAccess(db).require(obj.project_id, ctx.membership_id, "GENERATE_REPORT")
    obj = await TaskService(db).retry(obj)
    await db.commit()
    run_ai_task.delay(str(obj.id))
    return obj


@router.post("/tasks/{task_id}/cancel", response_model=TaskRead, tags=["Tasks"])
async def cancel_task(
    task_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await db.get(AITask, task_id)
    if not obj or obj.tenant_id != ctx.tenant_id:
        raise NotFound("TASK_NOT_FOUND", "Task not found")
    if obj.project_id:
        await ProjectAccess(db).require(obj.project_id, ctx.membership_id, "GENERATE_REPORT")
    obj = await TaskService(db).cancel(obj)
    await db.commit()
    return obj


@router.post("/reports/{report_id}/exports", status_code=201, tags=["Reports"])
async def export_report(
    report_id: UUID,
    format: str = "DOCX",
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    report = await _report(db, report_id)
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "VIEW_PROJECT")
    if format.upper() != "DOCX":
        raise DomainError("EXPORT_FORMAT_UNSUPPORTED", "Only DOCX is supported in MVP", 422)
    data = await render_docx(db, report_id)
    key = (
        f"tenants/{ctx.tenant_id}/projects/{report.project_id}/reports/{report_id}/exports/"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.docx"
    )
    await storage().put(
        key,
        data,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    export = ReportExport(
        report_id=report_id,
        format="DOCX",
        status="SUCCESS",
        object_key=key,
        created_by=ctx.user_id,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)
    return {
        "id": export.id,
        "status": export.status,
        "download_url": await storage().signed_download_url(key),
    }


@router.get("/report-exports/{export_id}", tags=["Reports"])
async def report_export(
    export_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    export = await db.get(ReportExport, export_id)
    report = await db.get(Report, export.report_id) if export else None
    if not export or not report:
        raise NotFound("REPORT_EXPORT_NOT_FOUND", "Report export not found")
    await ProjectAccess(db).require(report.project_id, ctx.membership_id, "VIEW_PROJECT")
    return {
        "id": export.id,
        "status": export.status,
        "format": export.format,
        "download_url": (
            await storage().signed_download_url(export.object_key) if export.object_key else None
        ),
    }


@router.get("/projects/{project_id}/audit-logs", tags=["Audit"])
async def audit_logs(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return list(
        (
            await db.scalars(
                select(AuditLog)
                .where(AuditLog.project_id == project_id, AuditLog.tenant_id == ctx.tenant_id)
                .order_by(AuditLog.created_at.desc())
                .limit(500)
            )
        ).all()
    )
