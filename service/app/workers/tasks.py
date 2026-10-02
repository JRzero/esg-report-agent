import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.ai.openviking import OpenVikingAdapter
from app.ai.workflows import FactExtractionWorkflow, SectionPlanningWorkflow, SectionWritingWorkflow
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.integrations.parsers import parse_document
from app.integrations.storage import storage
from app.modules.models import AITask, ContextBinding, Document, DocumentAnchor, DocumentVersion
from app.modules.services import TaskService
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_document")
def process_document(version_id: str):
    return asyncio.run(_process_document(version_id))


async def _process_document(version_id: str):
    settings = get_settings()
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        claimed = await session.execute(
            update(DocumentVersion)
            .where(
                DocumentVersion.id == version_id,
                DocumentVersion.evidence_parse_status == "PENDING",
            )
            .values(
                validation_status="READY",
                evidence_parse_status="PROCESSING",
                processing_started_at=now,
                parse_error=None,
            )
        )
        if claimed.rowcount != 1:
            await session.rollback()
            return
        await session.commit()

        version = await session.get(DocumentVersion, version_id)
        document = await session.get(Document, version.document_id) if version else None
        if not version or not document or document.deleted_at is not None:
            return

        try:
            data = await storage().get(version.object_key)
            anchors = parse_document(
                version.original_filename,
                data,
                max_anchors=settings.max_document_anchors,
                max_text_chars=settings.max_document_text_chars,
            )
            for anchor in anchors:
                exists = await session.scalar(
                    select(DocumentAnchor).where(
                        DocumentAnchor.document_version_id == version.id,
                        DocumentAnchor.content_hash == anchor.content_hash,
                    )
                )
                if exists:
                    continue
                session.add(
                    DocumentAnchor(
                        tenant_id=document.tenant_id,
                        project_id=document.project_id,
                        document_version_id=version.id,
                        anchor_type=anchor.anchor_type,
                        page_start=anchor.page_start,
                        page_end=anchor.page_end,
                        sheet_name=anchor.sheet_name,
                        cell_range=anchor.cell_range,
                        heading_path=anchor.heading_path,
                        paragraph_start=anchor.paragraph_start,
                        slide_number=anchor.slide_number,
                        bbox=anchor.bbox,
                        raw_text=anchor.raw_text,
                        normalized_text=anchor.raw_text.strip(),
                        content_hash=anchor.content_hash,
                        metadata_json=anchor.metadata,
                    )
                )
            version.evidence_parse_status = "READY"
            version.processing_started_at = None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            failed = await session.get(DocumentVersion, version_id)
            if failed:
                failed.validation_status = "FAILED"
                failed.evidence_parse_status = "FAILED"
                failed.processing_started_at = None
                failed.parse_error = str(exc)[:8000]
                await session.commit()
            return

        binding = await session.scalar(
            select(ContextBinding).where(
                ContextBinding.resource_type == "DOCUMENT_VERSION",
                ContextBinding.resource_id == version.id,
            )
        )
        if not binding:
            binding = ContextBinding(
                tenant_id=document.tenant_id,
                project_id=document.project_id,
                resource_type="DOCUMENT_VERSION",
                resource_id=version.id,
                processing_status="PENDING",
            )
            session.add(binding)
            await session.flush()

        adapter = OpenVikingAdapter()
        if not adapter.enabled:
            binding.processing_status = "DISABLED"
            binding.last_error = None
            version.context_status = "DISABLED"
            await session.commit()
            return

        if binding.processing_status == "READY":
            version.context_status = "READY"
            await session.commit()
            return

        if binding.processing_status == "PROCESSING" and binding.external_task_id:
            version.context_status = "PROCESSING"
            await session.commit()
            return

        binding.processing_status = "PROCESSING"
        binding.last_error = None
        await session.commit()

        try:
            category = (document.category_code or "incoming").replace(".", "/")
            source_segment = {
                "REFERENCE": "reference",
                "STANDARD": "standard",
                "HISTORICAL": "history",
            }.get(document.source_type, "evidence")
            target = (
                f"viking://resources/tenants/{document.tenant_id}/projects/{document.project_id}/"
                f"{source_segment}/{category}/{version.id}-{version.original_filename}"
            )
            result = await adapter.add_bytes(version.original_filename, data, target)
            binding.uri = result.get("root_uri", target)
            binding.external_task_id = result.get("task_id")
            if binding.external_task_id:
                binding.processing_status = "PROCESSING"
                version.context_status = "PROCESSING"
            else:
                status = str(result.get("status", "")).lower()
                if status in {"success", "completed"}:
                    binding.processing_status = "READY"
                    version.context_status = "READY"
                else:
                    binding.processing_status = "FAILED"
                    binding.last_error = f"Unexpected OpenViking add-resource status: {status or 'unknown'}"
                    version.context_status = "FAILED"
        except Exception as exc:
            binding.processing_status = "FAILED"
            binding.retry_count += 1
            binding.last_error = str(exc)[:8000]
            version.context_status = "FAILED"
        await session.commit()


@celery_app.task(name="app.workers.tasks.run_ai_task")
def run_ai_task(task_id: str):
    return asyncio.run(_run_ai_task(task_id))


async def _run_ai_task(task_id: str):
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        claimed = await session.execute(
            update(AITask)
            .where(AITask.id == task_id, AITask.status == "PENDING")
            .values(
                status="RUNNING",
                stage="running",
                started_at=now,
                completed_at=None,
                error_code=None,
                error_message=None,
            )
        )
        if claimed.rowcount != 1:
            await session.rollback()
            return
        await session.commit()

        task = await session.get(AITask, task_id)
        if not task:
            return

        try:
            if task.task_type == "FACT_EXTRACTION":
                result = await FactExtractionWorkflow(session).run(
                    task.tenant_id,
                    task.project_id,
                    task.created_by,
                    task.target_id,
                )
            elif task.task_type == "SECTION_PLANNING":
                result = await SectionPlanningWorkflow(session).run(task.project_id, task.target_id)
            elif task.task_type == "SECTION_WRITING":
                result = await SectionWritingWorkflow(session).run(
                    task.tenant_id,
                    task.project_id,
                    task.created_by,
                    task.target_id,
                )
            else:
                raise ValueError(f"Unsupported task type: {task.task_type}")

            completed = await session.execute(
                update(AITask)
                .where(AITask.id == task.id, AITask.status == "RUNNING")
                .values(
                    status="SUCCESS",
                    progress=1,
                    stage="completed",
                    result_json={"count": len(result) if isinstance(result, list) else 1},
                    completed_at=datetime.now(timezone.utc),
                )
            )
            if completed.rowcount != 1:
                await session.rollback()
                return
            await session.commit()
        except Exception as exc:
            await session.rollback()
            async with session.begin():
                failed_task = await session.get(AITask, task_id)
                if (
                    failed_task
                    and failed_task.task_type == "SECTION_PLANNING"
                    and failed_task.target_id
                ):
                    section = await session.get(ReportSection, failed_task.target_id)
                    if section and section.project_id == failed_task.project_id:
                        section.status = "DRAFT" if section.writing_plan else "NOT_STARTED"
                await session.execute(
                    update(AITask)
                    .where(AITask.id == task_id, AITask.status == "RUNNING")
                    .values(
                        status="FAILED",
                        stage="failed",
                        error_code="TASK_FAILED",
                        error_message=str(exc)[:8000],
                        completed_at=datetime.now(timezone.utc),
                    )
                )
            raise


@celery_app.task(name="app.workers.tasks.reconcile_context_bindings")
def reconcile_context_bindings():
    return asyncio.run(_reconcile_context_bindings())


async def _reconcile_context_bindings():
    settings = get_settings()
    adapter = OpenVikingAdapter()
    if not adapter.enabled:
        return {"checked": 0, "updated": 0}

    checked = 0
    updated_count = 0
    async with SessionLocal() as session:
        bindings = list(
            (
                await session.scalars(
                    select(ContextBinding)
                    .where(
                        ContextBinding.provider == "OPENVIKING",
                        ContextBinding.processing_status == "PROCESSING",
                        ContextBinding.external_task_id.is_not(None),
                    )
                    .order_by(ContextBinding.updated_at)
                    .limit(100)
                )
            ).all()
        )

        for binding in bindings:
            checked += 1
            try:
                external = await adapter.get_task(binding.external_task_id)
                status = str(external.get("status", "")).lower()
                version = (
                    await session.get(DocumentVersion, binding.resource_id)
                    if binding.resource_type == "DOCUMENT_VERSION"
                    else None
                )
                if status == "completed":
                    binding.processing_status = "READY"
                    binding.last_error = None
                    binding.metadata_json = {
                        **(binding.metadata_json or {}),
                        "external_result": external.get("result"),
                    }
                    if version:
                        version.context_status = "READY"
                    updated_count += 1
                elif status in {"failed", "cancelled"}:
                    binding.processing_status = "FAILED"
                    binding.last_error = str(external.get("error") or status)[:8000]
                    if version:
                        version.context_status = "FAILED"
                    updated_count += 1
                elif status in {"pending", "running", "cancelling"}:
                    continue
                else:
                    binding.retry_count += 1
                    binding.last_error = f"Unknown OpenViking task status: {status or 'missing'}"
                    if binding.retry_count >= settings.openviking_reconcile_max_retries:
                        binding.processing_status = "FAILED"
                        if version:
                            version.context_status = "FAILED"
                        updated_count += 1
            except Exception as exc:
                binding.retry_count += 1
                binding.last_error = str(exc)[:8000]
                if binding.retry_count >= settings.openviking_reconcile_max_retries:
                    binding.processing_status = "FAILED"
                    version = (
                        await session.get(DocumentVersion, binding.resource_id)
                        if binding.resource_type == "DOCUMENT_VERSION"
                        else None
                    )
                    if version:
                        version.context_status = "FAILED"
                    updated_count += 1

        await session.commit()
    return {"checked": checked, "updated": updated_count}


@celery_app.task(name="app.workers.tasks.recover_stale_work")
def recover_stale_work():
    return asyncio.run(_recover_stale_work())


async def _recover_stale_work():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    task_cutoff = now - timedelta(seconds=settings.task_stale_after_seconds)
    document_cutoff = now - timedelta(seconds=settings.document_stale_after_seconds)

    async with SessionLocal() as session:
        task_count = await TaskService(session).recover_stale(task_cutoff)

        stale_versions = list(
            (
                await session.scalars(
                    select(DocumentVersion).where(
                        DocumentVersion.evidence_parse_status == "PROCESSING",
                        DocumentVersion.processing_started_at.is_not(None),
                        DocumentVersion.processing_started_at < document_cutoff,
                    )
                )
            ).all()
        )
        for version in stale_versions:
            version.evidence_parse_status = "FAILED"
            version.validation_status = "FAILED"
            version.processing_started_at = None
            version.parse_error = "Document processing exceeded stale-work threshold"

        await session.commit()
        return {"tasks": task_count, "documents": len(stale_versions)}
