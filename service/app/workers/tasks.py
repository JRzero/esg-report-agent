import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.ai.openviking import OpenVikingAdapter
from app.ai.workflows import FactExtractionWorkflow, SectionPlanningWorkflow, SectionWritingWorkflow
from app.core.database import SessionLocal
from app.integrations.export import render_docx
from app.integrations.parsers import parse_document
from app.integrations.storage import storage
from app.modules.models import (
    AITask,
    ContextBinding,
    Document,
    DocumentAnchor,
    DocumentVersion,
    Report,
    ReportExport,
)
from app.workers.celery_app import celery_app


def utcnow():
    return datetime.now(timezone.utc)


@celery_app.task(name="app.workers.tasks.process_document")
def process_document(version_id: str):
    return asyncio.run(_process_document(UUID(version_id)))


async def _process_document(version_id: UUID):
    async with SessionLocal() as session:
        version = await session.get(DocumentVersion, version_id)
        if not version:
            return
        document = await session.get(Document, version.document_id)
        data = await storage().get(version.object_key)

        version.validation_status = "READY"
        version.evidence_parse_status = "PROCESSING"
        await session.commit()

        try:
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
            version.parse_error = None
            await session.commit()
        except Exception as exc:
            version.evidence_parse_status = "FAILED"
            version.parse_error = str(exc)
            await session.commit()
            raise

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
                processing_status="PROCESSING",
            )
            session.add(binding)
        else:
            binding.processing_status = "PROCESSING"
            binding.last_error = None
            binding.retry_count += 1
        await session.commit()
        await session.refresh(binding)

        try:
            category = (document.category_code or "incoming").replace(".", "/")
            lane = (
                "reference/"
                if document.source_type == "REFERENCE"
                else "history/"
                if document.source_type == "HISTORICAL"
                else "evidence/"
            )
            target = (
                f"viking://resources/projects/{document.project_id}/"
                f"{lane}{category}/{version.id}-{version.original_filename}"
            )
            result = await OpenVikingAdapter().add_bytes(
                version.original_filename,
                data,
                target,
            )
            binding.uri = result.get("root_uri", target)
            binding.external_task_id = result.get("task_id")
            binding.processing_status = "PROCESSING" if binding.external_task_id else "READY"
            version.context_status = binding.processing_status
        except Exception as exc:
            binding.processing_status = "FAILED"
            binding.last_error = str(exc)
            version.context_status = "FAILED"
        await session.commit()


@celery_app.task(name="app.workers.tasks.run_ai_task")
def run_ai_task(task_id: str):
    return asyncio.run(_run_ai_task(UUID(task_id)))


async def _run_ai_task(task_id: UUID):
    async with SessionLocal() as session:
        task = await session.get(AITask, task_id)
        if not task or task.status == "CANCELLED":
            return

        task.status = "RUNNING"
        task.stage = "running"
        task.started_at = utcnow()
        task.error_code = None
        task.error_message = None
        await session.commit()

        try:
            if task.status == "CANCELLED":
                return
            if task.task_type == "FACT_EXTRACTION":
                result = await FactExtractionWorkflow(session).run(
                    task.tenant_id,
                    task.project_id,
                    task.created_by,
                    task.target_id,
                )
            elif task.task_type == "SECTION_PLANNING":
                result = await SectionPlanningWorkflow(session).run(
                    task.project_id,
                    task.target_id,
                )
            elif task.task_type == "SECTION_WRITING":
                result = await SectionWritingWorkflow(session).run(
                    task.tenant_id,
                    task.project_id,
                    task.created_by,
                    task.target_id,
                )
            else:
                raise ValueError(f"Unsupported AI task type: {task.task_type}")

            task.status = "SUCCESS"
            task.progress = 1
            task.stage = "completed"
            task.completed_at = utcnow()
            task.result_json = {
                "count": len(result) if isinstance(result, list) else 1,
            }
            await session.commit()
        except Exception as exc:
            await session.rollback()
            task = await session.get(AITask, task_id)
            if task:
                task.status = "FAILED"
                task.stage = "failed"
                task.error_code = "TASK_FAILED"
                task.error_message = str(exc)
                task.completed_at = utcnow()
                await session.commit()
            raise


@celery_app.task(name="app.workers.tasks.export_report")
def export_report(export_id: str):
    return asyncio.run(_export_report(UUID(export_id)))


async def _export_report(export_id: UUID):
    async with SessionLocal() as session:
        export = await session.get(ReportExport, export_id)
        if not export:
            return
        report = await session.get(Report, export.report_id)
        if not report:
            export.status = "FAILED"
            await session.commit()
            return

        export.status = "PROCESSING"
        await session.commit()
        try:
            data = await render_docx(session, report.id)
            key = (
                f"tenants/{report.tenant_id}/projects/{report.project_id}/reports/"
                f"{report.id}/exports/{export.id}.docx"
            )
            await storage().put(
                key,
                data,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            export.object_key = key
            export.status = "SUCCESS"
            export.completed_at = utcnow()
            await session.commit()
        except Exception:
            await session.rollback()
            export = await session.get(ReportExport, export_id)
            if export:
                export.status = "FAILED"
                export.completed_at = utcnow()
                await session.commit()
            raise
