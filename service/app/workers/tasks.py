import asyncio, hashlib
from pathlib import Path
from sqlalchemy import select
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.integrations.storage import storage
from app.integrations.parsers import parse_document
from app.modules.models import DocumentVersion, Document, DocumentAnchor, ContextBinding, AITask, Report, ReportSection, ReportBlock
from app.ai.workflows import FactExtractionWorkflow, SectionPlanningWorkflow, SectionWritingWorkflow
from app.ai.openviking import OpenVikingAdapter

@celery_app.task(name='app.workers.tasks.process_document')
def process_document(version_id:str): return asyncio.run(_process_document(version_id))
async def _process_document(version_id):
    async with SessionLocal() as s:
        v=await s.get(DocumentVersion,version_id); d=await s.get(Document,v.document_id); data=await storage().get(v.object_key)
        v.validation_status='READY'; v.evidence_parse_status='PROCESSING'; await s.commit()
        anchors=parse_document(v.original_filename,data)
        async with s.begin():
            for a in anchors:
                exists=await s.scalar(select(DocumentAnchor).where(DocumentAnchor.document_version_id==v.id,DocumentAnchor.content_hash==a.content_hash))
                if not exists: s.add(DocumentAnchor(tenant_id=d.tenant_id,project_id=d.project_id,document_version_id=v.id,anchor_type=a.anchor_type,page_start=a.page_start,page_end=a.page_end,sheet_name=a.sheet_name,cell_range=a.cell_range,heading_path=a.heading_path,paragraph_start=a.paragraph_start,slide_number=a.slide_number,bbox=a.bbox,raw_text=a.raw_text,normalized_text=a.raw_text.strip(),content_hash=a.content_hash,metadata_json=a.metadata))
            v.evidence_parse_status='READY'
        # Context ingestion is independent from evidence parsing. A failure here does not
        # invalidate anchors/facts and is retryable.
        binding=ContextBinding(tenant_id=d.tenant_id,project_id=d.project_id,resource_type='DOCUMENT_VERSION',resource_id=v.id,processing_status='PROCESSING')
        s.add(binding); await s.commit(); await s.refresh(binding)
        try:
            category=(d.category_code or 'incoming').replace('.', '/')
            target=f'viking://resources/projects/{d.project_id}/' + ('reference/' if d.source_type=='REFERENCE' else 'history/' if d.source_type=='HISTORICAL' else 'evidence/') + category + f'/{v.id}-{v.original_filename}'
            result=await OpenVikingAdapter().add_bytes(v.original_filename,data,target)
            binding.uri=result.get('root_uri',target); binding.external_task_id=result.get('task_id'); binding.processing_status='PROCESSING' if binding.external_task_id else 'READY'; v.context_status=binding.processing_status
        except Exception as e:
            binding.processing_status='FAILED'; binding.last_error=str(e); v.context_status='FAILED'
        await s.commit()

@celery_app.task(name='app.workers.tasks.run_ai_task')
def run_ai_task(task_id:str): return asyncio.run(_run_ai_task(task_id))
async def _run_ai_task(task_id):
    async with SessionLocal() as s:
        t=await s.get(AITask,task_id); t.status='RUNNING'; t.stage='running'; await s.commit()
        try:
            async with s.begin():
                if t.task_type=='FACT_EXTRACTION': result=await FactExtractionWorkflow(s).run(t.tenant_id,t.project_id,t.created_by,t.target_id)
                elif t.task_type=='SECTION_PLANNING': result=await SectionPlanningWorkflow(s).run(t.project_id,t.target_id)
                elif t.task_type=='SECTION_WRITING': result=await SectionWritingWorkflow(s).run(t.tenant_id,t.project_id,t.created_by,t.target_id)
                else: result=[]
                t.status='SUCCESS'; t.progress=1; t.stage='completed'; t.result_json={'count':len(result) if isinstance(result,list) else 1}
        except Exception as e:
            async with s.begin(): t.status='FAILED'; t.error_code='TASK_FAILED'; t.error_message=str(e)
            raise
