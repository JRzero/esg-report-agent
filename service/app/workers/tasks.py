import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.ai.openviking import OpenVikingAdapter
from app.ai.workflows import FactExtractionWorkflow, SectionPlanningWorkflow, SectionWritingWorkflow
from app.core.database import SessionLocal
from app.integrations.parsers import parse_document
from app.integrations.storage import storage
from app.modules.models import AITask, ContextBinding, Document, DocumentAnchor, DocumentVersion
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_document")
def process_document(version_id: str):
    return asyncio.run(_process_document(version_id))


async def _process_document(version_id: str):
    async with SessionLocal() as session:
        version = await session.get(DocumentVersion, version_id)
        if not version:
            return
        document = await session.get(Document, version.document_id)
        if not document or document.deleted_at is not None:
            return
        try:
            data = await storage().get(version.object_key)
            version.validation_status = "READY"
            version.evidence_parse_status = "PROCESSING"
            version.parse_error = None
            await session.commit()

            anchors = parse_document(version.original_filename, data)
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
            await session.commit()
        except Exception as exc:
            await session.rollback()
            version = await session.get(DocumentVersion, version_id)
            if version:
                version.validation_status = "FAILED"
                version.evidence_parse_status = "FAILED"
                version.parse_error = str(exc)
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
                f"viking://resources/projects/{document.project_id}/"
                f"{source_segment}/{category}/{version.id}-{version.original_filename}"
            )
            result = await OpenVikingAdapter().add_bytes(version.original_filename, data, target)
            binding.uri = result.get("root_uri", target)
            binding.external_task_id = result.get("task_id")
            binding.processing_status = "PROCESSING" if binding.external_task_id else "READY"
            version.context_status = binding.processing_status
        except Exception as exc:
            binding.processing_status = "FAILED"
            binding.retry_count += 1
            binding.last_error = str(exc)
            version.context_status = "FAILED"
        await session.commit()


@celery_app.task(name="app.workers.tasks.run_ai_task")
def run_ai_task(task_id: str):
    return asyncio.run(_run_ai_task(task_id))


async def _run_ai_task(task_id: str):
    async with SessionLocal() as session:
        task = await session.get(AITask, task_id)
        if not task or task.status == "CANCELLED":
            return
        task.status = "RUNNING"
        task.stage = "running"
        task.started_at = datetime.now(timezone.utc)
        task.error_code = None
        task.error_message = None
        await session.commit()

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

            fresh = await session.get(AITask, task.id)
            if fresh.status == "CANCELLED":
                await session.rollback()
                return
            fresh.status = "SUCCESS"
            fresh.progress = 1
            fresh.stage = "completed"
            fresh.result_json = {"count": len(result) if isinstance(result, list) else 1}
            fresh.completed_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            failed = await session.get(AITask, task_id)
            if failed and failed.status != "CANCELLED":
                failed.status = "FAILED"
                failed.stage = "failed"
                failed.error_code = "TASK_FAILED"
                failed.error_message = str(exc)[:8000]
                failed.completed_at = datetime.now(timezone.utc)
                await session.commit()
            raise
