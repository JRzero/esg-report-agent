from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import DomainError, NotFound
from app.integrations.parsers import SUPPORTED_EXTENSIONS
from app.integrations.storage import storage
from app.modules.evidence_ext import DocumentLifecycle
from app.modules.models import ContextBinding, Document, DocumentVersion
from app.modules.services import ProjectAccess, TaskService
from app.workers.tasks import run_ai_task

router = APIRouter()


async def _queue(
    db: AsyncSession,
    ctx: RequestContext,
    project_id: UUID,
    task_type: str,
    target_type: str,
    target_id: UUID,
):
    task = await TaskService(db).create(
        ctx.tenant_id,
        project_id,
        ctx.user_id,
        task_type,
        target_type,
        target_id,
    )
    await db.commit()
    run_ai_task.delay(str(task.id), str(ctx.tenant_id))
    return {"task_id": task.id, "status": task.status}


def _validate_filename(filename: str) -> None:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DomainError(
            "DOCUMENT_TYPE_UNSUPPORTED",
            f"Unsupported file extension: {extension or '(none)'}",
            422,
            {"supported": sorted(SUPPORTED_EXTENSIONS)},
        )


@router.get("/projects/{project_id}/documents", tags=["Documents"])
async def list_documents(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return await DocumentLifecycle(db).list(project_id)


@router.get("/documents/{document_id}", tags=["Documents"])
async def document_detail(
    document_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == ctx.tenant_id,
            Document.deleted_at.is_(None),
        )
    )
    if not document:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    versions = await DocumentLifecycle(db).versions(document.id)
    bindings = list(
        (
            await db.scalars(
                select(ContextBinding)
                .where(
                    ContextBinding.resource_type == "DOCUMENT_VERSION",
                    ContextBinding.resource_id.in_([v.id for v in versions] or [UUID(int=0)]),
                )
                .order_by(ContextBinding.created_at.desc())
            )
        ).all()
    )
    return {"document": document, "versions": versions, "context_bindings": bindings}


@router.delete("/documents/{document_id}", status_code=204, tags=["Documents"])
async def delete_document(
    document_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == ctx.tenant_id,
            Document.deleted_at.is_(None),
        )
    )
    if not document:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    await DocumentLifecycle(db).delete(document, ctx.user_id)
    await db.commit()
    return Response(status_code=204)


@router.get("/documents/{document_id}/versions", tags=["Documents"])
async def document_versions(
    document_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == ctx.tenant_id,
            Document.deleted_at.is_(None),
        )
    )
    if not document:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    return await DocumentLifecycle(db).versions(document_id)


@router.post("/documents/{document_id}/versions", status_code=201, tags=["Documents"])
async def upload_document_version(
    document_id: UUID,
    file: UploadFile = File(...),
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == ctx.tenant_id,
            Document.deleted_at.is_(None),
        )
    )
    if not document:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    filename = file.filename or "document"
    _validate_filename(filename)
    data = await file.read()
    if not data:
        raise DomainError("DOCUMENT_EMPTY", "Uploaded document is empty", 422)

    version = await DocumentLifecycle(db).create_version(
        document, ctx.user_id, filename, file.content_type, data
    )
    await db.commit()

    try:
        await storage().put(version.object_key, data, file.content_type)
    except Exception as exc:
        version.validation_status = "FAILED"
        version.parse_error = str(exc)
        await db.commit()
        raise DomainError("STORAGE_WRITE_FAILED", "Failed to persist document", 503) from exc

    task = await _queue(
        db,
        ctx,
        document.project_id,
        "DOCUMENT_PROCESS",
        "DOCUMENT_VERSION",
        version.id,
    )
    return {"version": version, "processing_task": task}


@router.get("/document-versions/{version_id}", tags=["Documents"])
async def version_detail(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(DocumentVersion, version_id)
    document = await db.get(Document, version.document_id) if version else None
    if not document or document.tenant_id != ctx.tenant_id or document.deleted_at is not None:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    binding = await db.scalar(
        select(ContextBinding)
        .where(
            ContextBinding.resource_type == "DOCUMENT_VERSION",
            ContextBinding.resource_id == version.id,
        )
        .order_by(ContextBinding.created_at.desc())
    )
    return {"version": version, "context_binding": binding}


@router.get("/document-versions/{version_id}/download", tags=["Documents"])
async def download_document_version(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(DocumentVersion, version_id)
    document = await db.get(Document, version.document_id) if version else None
    if not document or document.tenant_id != ctx.tenant_id:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "VIEW_PROJECT")
    if not await storage().exists(version.object_key):
        raise NotFound("DOCUMENT_OBJECT_NOT_FOUND", "Stored document object not found")
    return {"download_url": await storage().signed_download_url(version.object_key)}


@router.post("/document-versions/{version_id}/parse", status_code=202, tags=["Documents"])
async def reprocess_document(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(DocumentVersion, version_id)
    document = await db.get(Document, version.document_id) if version else None
    if not document or document.tenant_id != ctx.tenant_id:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    return await _queue(
        db, ctx, document.project_id, "DOCUMENT_PROCESS", "DOCUMENT_VERSION", version.id
    )


@router.post(
    "/document-versions/{version_id}/reindex-context",
    status_code=202,
    tags=["Documents"],
)
async def reindex_document_context(
    version_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(DocumentVersion, version_id)
    document = await db.get(Document, version.document_id) if version else None
    if not document or document.tenant_id != ctx.tenant_id:
        raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
    await ProjectAccess(db).require(document.project_id, ctx.membership_id, "UPLOAD_DOCUMENT")
    return await _queue(
        db, ctx, document.project_id, "CONTEXT_REINDEX", "DOCUMENT_VERSION", version.id
    )
