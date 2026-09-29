import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select

from app.ai.openviking import OpenVikingAdapter
from app.ai.workflows import (
    FactExtractionWorkflow,
    SectionPlanningWorkflow,
    SectionWritingWorkflow,
)
from app.core.config import get_settings
from app.core.database import SessionLocal, set_tenant_context
from app.integrations.export import render_docx
from app.integrations.parsers import parse_document
from app.integrations.storage import storage
from app.modules.models import (
    AITask,
    AITrace,
    ContextBinding,
    Document,
    DocumentAnchor,
    DocumentVersion,
    ProjectDisclosure,
    ProjectRequirementStatus,
    Report,
    ReportExport,
)
from app.modules.services import ReportService, StandardService
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_document")
def process_document(version_id: str, tenant_id: str):
    return asyncio.run(_process_document(UUID(version_id), UUID(tenant_id)))


async def _process_document(version_id: UUID, tenant_id: UUID) -> int:
    async with SessionLocal() as session:
        await set_tenant_context(session, str(tenant_id))
        version = await session.get(DocumentVersion, version_id)
        document = await session.get(Document, version.document_id) if version else None
        if not version or not document:
            raise RuntimeError("Document version not found")
        version.validation_status = "READY"
        version.evidence_parse_status = "PROCESSING"
        version.parse_error = None
        await session.commit()
        data = await storage().get(version.object_key)

        try:
            anchors = parse_document(version.original_filename, data)
        except Exception as exc:
            version.evidence_parse_status = "FAILED"
            version.parse_error = str(exc)[:4000]
            await session.commit()
            raise

        for anchor in anchors:
            existing = await session.scalar(
                select(DocumentAnchor).where(
                    DocumentAnchor.document_version_id == version.id,
                    DocumentAnchor.content_hash == anchor.content_hash,
                )
            )
            if existing:
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
        await session.commit()

    # Context indexing is independent from evidence parsing and may fail/retry
    # without invalidating immutable anchors.
    try:
        await _reindex_context(version_id, tenant_id)
    except Exception:
        pass
    return len(anchors)


async def _reindex_context(version_id: UUID, tenant_id: UUID) -> dict:
    async with SessionLocal() as session:
        await set_tenant_context(session, str(tenant_id))
        version = await session.get(DocumentVersion, version_id)
        document = await session.get(Document, version.document_id) if version else None
        if not version or not document:
            raise RuntimeError("Document version not found")
        binding = await session.scalar(
            select(ContextBinding)
            .where(
                ContextBinding.resource_type == "DOCUMENT_VERSION",
                ContextBinding.resource_id == version.id,
            )
            .order_by(ContextBinding.created_at.desc())
        )
        if not binding:
            binding = ContextBinding(
                tenant_id=document.tenant_id,
                project_id=document.project_id,
                resource_type="DOCUMENT_VERSION",
                resource_id=version.id,
            )
            session.add(binding)
            await session.flush()
        binding.processing_status = "PROCESSING"
        binding.last_error = None
        version.context_status = "PROCESSING"
        await session.commit()

        data = await storage().get(version.object_key)
        category = (document.category_code or "incoming").replace(".", "/")
        namespace = (
            "reference"
            if document.source_type == "REFERENCE"
            else "standards"
            if document.source_type == "STANDARD"
            else "history"
            if document.source_type == "HISTORICAL"
            else "evidence"
        )
        target = (
            f"viking://resources/projects/{document.project_id}/{namespace}/"
            f"{category}/{version.id}-{version.original_filename}"
        )
        try:
            result = await OpenVikingAdapter().add_bytes(
                version.original_filename,
                data,
                target,
            )
            binding.uri = result.get("root_uri", target)
            binding.external_task_id = result.get("task_id")
            binding.processing_status = (
                "PROCESSING" if binding.external_task_id else "READY"
            )
            binding.retry_count = 0
            version.context_status = binding.processing_status
            await session.commit()
            return {
                "uri": binding.uri,
                "external_task_id": binding.external_task_id,
                "status": binding.processing_status,
            }
        except Exception as exc:
            binding.processing_status = "FAILED"
            binding.retry_count = (binding.retry_count or 0) + 1
            binding.last_error = str(exc)[:4000]
            version.context_status = "FAILED"
            await session.commit()
            raise


async def _run_export(session, task: AITask) -> dict:
    export = await session.get(ReportExport, task.target_id)
    if not export:
        raise RuntimeError("Report export not found")
    report = await session.get(Report, export.report_id)
    if not report:
        raise RuntimeError("Report not found")
    data = await render_docx(session, report.id)
    # Close the read transaction before object-storage I/O.
    await session.commit()
    key = (
        f"tenants/{report.tenant_id}/projects/{report.project_id}/reports/{report.id}/"
        f"exports/{export.id}.docx"
    )
    await storage().put(
        key,
        data,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    export = await session.get(ReportExport, export.id)
    export.object_key = key
    export.status = "SUCCESS"
    export.completed_at = datetime.now(timezone.utc)
    await session.commit()
    return {"export_id": str(export.id), "object_key": key}


@celery_app.task(name="app.workers.tasks.run_ai_task")
def run_ai_task(task_id: str, tenant_id: str):
    return asyncio.run(_run_ai_task(UUID(task_id), UUID(tenant_id)))


async def _run_ai_task(task_id: UUID, tenant_id: UUID):
    async with SessionLocal() as session:
        await set_tenant_context(session, str(tenant_id))
        task = await session.get(AITask, task_id)
        if not task:
            raise RuntimeError("Task not found")
        if task.status == "CANCELLED":
            return {"status": "CANCELLED"}

        task.status = "RUNNING"
        task.stage = "running"
        task.started_at = datetime.now(timezone.utc)
        task.error_code = None
        task.error_message = None
        await session.commit()

        skill_name = task.task_type.lower()
        try:
            result: object
            if task.task_type == "DOCUMENT_PROCESS":
                result = {"anchors": await _process_document(task.target_id, tenant_id)}
            elif task.task_type == "CONTEXT_REINDEX":
                result = await _reindex_context(task.target_id, tenant_id)
            elif task.task_type == "FACT_EXTRACTION":
                version = await session.get(DocumentVersion, task.target_id)
                if version:
                    version.fact_extraction_status = "PROCESSING"
                    await session.commit()
                facts = await FactExtractionWorkflow(session).run(
                    task.tenant_id,
                    task.project_id,
                    task.created_by,
                    task.target_id,
                )
                if version:
                    version = await session.get(DocumentVersion, task.target_id)
                    version.fact_extraction_status = "READY"
                result = {"count": len(facts), "fact_ids": [str(f.id) for f in facts]}
            elif task.task_type == "DISCLOSURE_MAPPING":
                count = await StandardService(session).map_confirmed_facts(task.project_id)
                result = {"mappings_created": count}
            elif task.task_type == "MISSING_DATA_ANALYSIS":
                items = await StandardService(session).generate_missing_items(
                    task.tenant_id,
                    task.project_id,
                )
                result = {"missing_items_created": len(items)}
            elif task.task_type == "GRI_CHECK":
                mappings = await StandardService(session).map_confirmed_facts(task.project_id)
                rows = (
                    await session.execute(
                        select(ProjectRequirementStatus.status, func.count())
                        .where(ProjectRequirementStatus.project_id == task.project_id)
                        .group_by(ProjectRequirementStatus.status)
                    )
                ).all()
                disclosures = (
                    await session.execute(
                        select(ProjectDisclosure.coverage_status, func.count())
                        .where(ProjectDisclosure.project_id == task.project_id)
                        .group_by(ProjectDisclosure.coverage_status)
                    )
                ).all()
                result = {
                    "mappings_created": mappings,
                    "requirements": {status: count for status, count in rows},
                    "disclosures": {status: count for status, count in disclosures},
                }
            elif task.task_type == "SECTION_PLANNING":
                plan = await SectionPlanningWorkflow(session).run(
                    task.project_id,
                    task.target_id,
                )
                result = {"writing_plan": plan}
            elif task.task_type == "SECTION_WRITING":
                blocks = await SectionWritingWorkflow(session).run(
                    task.tenant_id,
                    task.project_id,
                    task.created_by,
                    task.target_id,
                )
                result = {"count": len(blocks), "block_ids": [str(b.id) for b in blocks]}
            elif task.task_type == "CONSISTENCY_CHECK":
                issues = await ReportService(session).consistency(task.target_id)
                result = {"issues": issues}
            elif task.task_type == "DOCX_EXPORT":
                result = await _run_export(session, task)
            else:
                raise RuntimeError(f"Unsupported task type: {task.task_type}")

            task = await session.get(AITask, task_id)
            task.status = "SUCCESS"
            task.progress = 1
            task.stage = "completed"
            task.result_json = result if isinstance(result, dict) else {"result": result}
            task.completed_at = datetime.now(timezone.utc)
            settings = get_settings()
            session.add(
                AITrace(
                    ai_task_id=task.id,
                    skill_name=skill_name,
                    skill_version="1.0",
                    prompt_version="1.0",
                    model_provider="openai-compatible" if settings.llm_base_url else None,
                    model_name=settings.llm_model if settings.llm_base_url else None,
                    result_status="SUCCESS",
                )
            )
            await session.commit()
            return task.result_json
        except Exception as exc:
            await session.rollback()
            task = await session.get(AITask, task_id)
            if task:
                task.status = "FAILED"
                task.stage = "failed"
                task.error_code = "TASK_FAILED"
                task.error_message = str(exc)[:4000]
                task.completed_at = datetime.now(timezone.utc)
                session.add(
                    AITrace(
                        ai_task_id=task.id,
                        skill_name=skill_name,
                        skill_version="1.0",
                        prompt_version="1.0",
                        result_status="FAILED",
                    )
                )
                if task.task_type == "FACT_EXTRACTION":
                    version = await session.get(DocumentVersion, task.target_id)
                    if version:
                        version.fact_extraction_status = "FAILED"
                if task.task_type == "DOCX_EXPORT":
                    export = await session.get(ReportExport, task.target_id)
                    if export:
                        export.status = "FAILED"
                await session.commit()
            raise
