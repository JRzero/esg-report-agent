from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import current_context
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import DomainError, Forbidden, NotFound
from app.core.security import create_token, decode_token
from app.core.permissions import allows
from app.integrations.storage import storage
from app.integrations.parsers import SUPPORTED_EXTENSIONS
from app.modules.models import *
from app.modules.schemas import *
from app.modules.services import IdentityService,TenantService,CompanyService,ProjectService,ProjectAccess,FactService,TaskService,StandardService,ReportService
from app.workers.tasks import run_ai_task

router=APIRouter(prefix='/api/v1')

@router.post('/auth/login',response_model=TokenResponse,tags=['Auth'])
async def login(body:LoginRequest,db:AsyncSession=Depends(get_db)):
    u,m=await IdentityService(db).authenticate(body.email,body.password)
    a=create_token(str(u.id),str(m.tenant_id),str(m.id),'access'); r=create_token(str(u.id),str(m.tenant_id),str(m.id),'refresh')
    return TokenResponse(access_token=a,refresh_token=r,expires_in=get_settings().jwt_access_token_minutes*60)


@router.post('/auth/refresh',response_model=TokenResponse,tags=['Auth'])
async def refresh(body:RefreshRequest,db:AsyncSession=Depends(get_db)):
    try: payload=decode_token(body.refresh_token)
    except Exception: raise DomainError('AUTH_INVALID_TOKEN','Invalid refresh token',401)
    if payload.get('type')!='refresh': raise DomainError('AUTH_INVALID_TOKEN','Refresh token required',401)
    user_id=UUID(payload['sub']); tenant_id=UUID(payload['tenant_id']); membership_id=UUID(payload['membership_id'])
    membership=await db.scalar(select(TenantMembership).where(TenantMembership.id==membership_id,TenantMembership.user_id==user_id,TenantMembership.tenant_id==tenant_id,TenantMembership.status=='ACTIVE'))
    if not membership: raise DomainError('AUTH_INVALID_MEMBERSHIP','Membership is not active',401)
    a=create_token(str(user_id),str(tenant_id),str(membership_id),'access'); r=create_token(str(user_id),str(tenant_id),str(membership_id),'refresh')
    return TokenResponse(access_token=a,refresh_token=r,expires_in=get_settings().jwt_access_token_minutes*60)

@router.get('/auth/me',tags=['Auth'])
async def me(ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    user=await db.get(User,ctx.user_id); membership=await db.get(TenantMembership,ctx.membership_id); tenant=await db.get(Tenant,ctx.tenant_id)
    return {'user':{'id':user.id,'email':user.email,'name':user.name},'tenant':{'id':tenant.id,'name':tenant.name,'code':tenant.code},'membership':{'id':membership.id,'tenant_role':membership.tenant_role,'member_type':membership.member_type,'company_id':membership.company_id}}

@router.get('/tenant/members',tags=['Tenants'])
async def tenant_members(ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    if ctx.tenant_role!='ADMIN': raise Forbidden('TENANT_ADMIN_REQUIRED','Tenant admin required')
    rows=await TenantService(db).list_members(ctx.tenant_id)
    return [{'membership':MembershipRead.model_validate(m).model_dump(),'user':UserRead.model_validate(u).model_dump()} for m,u in rows]

@router.post('/tenant/members',status_code=201,tags=['Tenants'])
async def create_tenant_member(body:UserCreate,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    if ctx.tenant_role!='ADMIN': raise Forbidden('TENANT_ADMIN_REQUIRED','Tenant admin required')
    if body.company_id: await CompanyService(db).get(ctx.tenant_id,body.company_id)
    user,membership=await TenantService(db).create_member(ctx.tenant_id,ctx.user_id,body); await db.commit()
    return {'user':UserRead.model_validate(user),'membership':MembershipRead.model_validate(membership)}

@router.get('/companies',response_model=list[CompanyRead],tags=['Companies'])
async def companies(ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    if ctx.member_type=='CLIENT':
        if not ctx.company_id: return []
        try: return [await CompanyService(db).get(ctx.tenant_id,ctx.company_id)]
        except NotFound: return []
    return await CompanyService(db).list(ctx.tenant_id)
@router.post('/companies',response_model=CompanyRead,status_code=201,tags=['Companies'])
async def create_company(body:CompanyCreate,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    if ctx.tenant_role!='ADMIN': raise Forbidden('TENANT_ADMIN_REQUIRED','Tenant admin required')
    obj=await CompanyService(db).create(ctx.tenant_id,ctx.user_id,body); await db.commit(); return obj

@router.get('/projects',response_model=list[ProjectRead],tags=['Projects'])
async def projects(ctx:RequestContext=Depends(current_context),db=Depends(get_db)): return await ProjectService(db).list(ctx.tenant_id,ctx.membership_id)
@router.post('/projects',response_model=ProjectRead,status_code=201,tags=['Projects'])
async def create_project(body:ProjectCreate,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    if ctx.member_type!='INTERNAL': raise Forbidden('PROJECT_CREATE_DENIED','Client members cannot create projects')
    obj=await ProjectService(db).create(ctx.tenant_id,ctx.user_id,ctx.membership_id,body); await db.commit(); return obj
@router.get('/projects/{project_id}',response_model=ProjectRead,tags=['Projects'])
async def project(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)): return await ProjectService(db).get(ctx.tenant_id,project_id,ctx.membership_id)
@router.post('/projects/{project_id}/members',response_model=ProjectMemberRead,status_code=201,tags=['Project Members'])
async def add_member(project_id:UUID,body:ProjectMemberCreate,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    obj=await ProjectService(db).add_member(ctx.tenant_id,ctx.user_id,ctx.membership_id,project_id,body.membership_id,body.project_role); await db.commit(); return obj

@router.post('/projects/{project_id}/documents',status_code=201,tags=['Documents'])
async def upload_document(project_id:UUID,file:UploadFile=File(...),source_type:str=Form('EVIDENCE'),category_code:str|None=Form(None),ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'UPLOAD_DOCUMENT')
    source_type=source_type.upper()
    if source_type not in {'EVIDENCE','REFERENCE','STANDARD','HISTORICAL'}:
        raise DomainError('INVALID_DOCUMENT_SOURCE_TYPE','Invalid document source type',422)
    filename=file.filename or 'document'
    extension=Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DomainError('DOCUMENT_TYPE_UNSUPPORTED',f'Unsupported file extension: {extension or "(none)"}',422,{'supported':sorted(SUPPORTED_EXTENSIONS)})
    data=await file.read()
    if not data: raise DomainError('DOCUMENT_EMPTY','Uploaded document is empty',422)
    digest=sha256(data).hexdigest()
    d=Document(tenant_id=ctx.tenant_id,project_id=project_id,name=filename,source_type=source_type,category_code=category_code,created_by=ctx.user_id); db.add(d); await db.flush()
    v=DocumentVersion(document_id=d.id,version_no=1,original_filename=filename,mime_type=file.content_type,file_extension=extension,file_size=len(data),object_key=f'tenants/{ctx.tenant_id}/projects/{project_id}/documents/{d.id}/versions/v1/original{extension}',sha256=digest,uploaded_by=ctx.user_id); db.add(v); await db.flush()
    await db.commit()
    try:
        await storage().put(v.object_key,data,file.content_type)
    except Exception as exc:
        v.validation_status='FAILED'; v.parse_error=str(exc)[:4000]; await db.commit()
        raise DomainError('STORAGE_WRITE_FAILED','Failed to persist document',503) from exc
    task=await TaskService(db).create(ctx.tenant_id,project_id,ctx.user_id,'DOCUMENT_PROCESS','DOCUMENT_VERSION',v.id)
    await db.commit(); run_ai_task.delay(str(task.id), str(ctx.tenant_id))
    return {'document_id':d.id,'version_id':v.id,'status':'UPLOADED','processing_task_id':task.id}

@router.get('/document-versions/{version_id}/anchors',tags=['Documents'])
async def anchors(version_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    v=await db.get(DocumentVersion,version_id); d=await db.get(Document,v.document_id) if v else None
    if not d: raise NotFound('DOCUMENT_NOT_FOUND','Document not found')
    await ProjectAccess(db).require(d.project_id,ctx.membership_id,'VIEW_PROJECT')
    return list((await db.scalars(select(DocumentAnchor).where(DocumentAnchor.document_version_id==version_id))).all())

@router.get('/projects/{project_id}/facts',tags=['Facts'])
async def facts(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'VIEW_FACT'); return await FactService(db).list(project_id)
@router.post('/projects/{project_id}/facts',status_code=201,tags=['Facts'])
async def create_fact(project_id:UUID,body:FactCreate,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'CONFIRM_FACT')
    obj=await FactService(db).create_candidate(ctx.tenant_id,project_id,ctx.user_id,body,status='PENDING'); await db.commit(); return obj
@router.post('/facts/{fact_id}/confirm',tags=['Facts'])
async def confirm_fact(fact_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    f=await db.get(Fact,fact_id)
    if not f: raise NotFound('FACT_NOT_FOUND','Fact not found')
    await ProjectAccess(db).require(f.project_id,ctx.membership_id,'CONFIRM_FACT')
    obj=await FactService(db).confirm(f.project_id,f.id,ctx.user_id); await db.commit(); return obj
@router.get('/facts/{fact_id}/evidence',tags=['Facts'])
async def fact_evidence(fact_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    f=await db.get(Fact,fact_id)
    if not f: raise NotFound('FACT_NOT_FOUND','Fact not found')
    await ProjectAccess(db).require(f.project_id,ctx.membership_id,'VIEW_FACT')
    q=select(FactEvidence,DocumentAnchor,DocumentVersion,Document).join(DocumentAnchor,FactEvidence.document_anchor_id==DocumentAnchor.id).join(DocumentVersion,DocumentAnchor.document_version_id==DocumentVersion.id).join(Document,DocumentVersion.document_id==Document.id).where(FactEvidence.fact_id==fact_id)
    rows=(await db.execute(q)).all()
    return [{'fact_evidence_id':fe.id,'anchor':{'id':a.id,'type':a.anchor_type,'page':a.page_start,'sheet':a.sheet_name,'cell':a.cell_range,'raw_text':a.raw_text},'document':{'id':d.id,'name':d.name,'version_id':v.id}} for fe,a,v,d in rows]

@router.get('/standards',tags=['Standards'])
async def standards(ctx=Depends(current_context),db=Depends(get_db)): return list((await db.scalars(select(Standard))).all())
@router.get('/standard-versions/{version_id}/disclosures',tags=['Standards'])
async def disclosures(version_id:UUID,ctx=Depends(current_context),db=Depends(get_db)): return list((await db.scalars(select(Disclosure).where(Disclosure.standard_version_id==version_id).order_by(Disclosure.sort_order))).all())
@router.post('/projects/{project_id}/standards',status_code=201,tags=['Standards'])
async def add_project_standard(project_id:UUID,version_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'EDIT_PROJECT')
    ps=ProjectStandard(project_id=project_id,standard_version_id=version_id,is_primary=True); db.add(ps); await db.commit(); await db.refresh(ps); return ps

@router.post('/projects/{project_id}/reports',status_code=201,tags=['Reports'])
async def create_report(project_id:UUID,body:ReportCreate,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'EDIT_REPORT')
    r=await ReportService(db).create_report(ctx.tenant_id,project_id,ctx.user_id,body.title,body.language,body.template_version_id)
    await db.commit(); await db.refresh(r); return r
@router.post('/reports/{report_id}/sections',status_code=201,tags=['Reports'])
async def create_section(report_id:UUID,body:SectionCreate,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    r=await db.get(Report,report_id); await ProjectAccess(db).require(r.project_id,ctx.membership_id,'EDIT_REPORT')
    s=ReportSection(tenant_id=ctx.tenant_id,project_id=r.project_id,report_id=report_id,**body.model_dump()); db.add(s); await db.commit(); await db.refresh(s); return s
@router.get('/reports/{report_id}/sections',tags=['Reports'])
async def sections(report_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    r=await db.get(Report,report_id)
    if not r: raise NotFound('REPORT_NOT_FOUND','Report not found')
    await ProjectAccess(db).require(r.project_id,ctx.membership_id,'VIEW_PROJECT')
    return list((await db.scalars(select(ReportSection).where(ReportSection.report_id==report_id).order_by(ReportSection.sort_order))).all())

async def queue_ai(db,ctx,project_id,task_type,target_type,target_id):
    t=await TaskService(db).create(ctx.tenant_id,project_id,ctx.user_id,task_type,target_type,target_id); await db.commit()
    run_ai_task.delay(str(t.id), str(ctx.tenant_id))
    return {'task_id':t.id,'status':t.status}
@router.post('/document-versions/{version_id}/extract-facts',status_code=202,tags=['AI'])
async def extract_facts(version_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    v=await db.get(DocumentVersion,version_id); d=await db.get(Document,v.document_id) if v else None
    if not d: raise NotFound('DOCUMENT_NOT_FOUND','Document not found')
    await ProjectAccess(db).require(d.project_id,ctx.membership_id,'CONFIRM_FACT'); return await queue_ai(db,ctx,d.project_id,'FACT_EXTRACTION','DOCUMENT_VERSION',version_id)
@router.post('/sections/{section_id}/ai/writing-plan',status_code=202,tags=['AI'])
async def plan(section_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    s=await db.get(ReportSection,section_id); await ProjectAccess(db).require(s.project_id,ctx.membership_id,'GENERATE_REPORT'); return await queue_ai(db,ctx,s.project_id,'SECTION_PLANNING','SECTION',section_id)
@router.post('/sections/{section_id}/ai/generate',status_code=202,tags=['AI'])
async def generate(section_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    s=await db.get(ReportSection,section_id); await ProjectAccess(db).require(s.project_id,ctx.membership_id,'GENERATE_REPORT'); return await queue_ai(db,ctx,s.project_id,'SECTION_WRITING','SECTION',section_id)
@router.get('/tasks/{task_id}',response_model=TaskRead,tags=['Tasks'])
async def task(task_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    t=await db.get(AITask,task_id)
    if not t or t.tenant_id!=ctx.tenant_id: raise NotFound('TASK_NOT_FOUND','Task not found')
    if t.project_id: await ProjectAccess(db).require(t.project_id,ctx.membership_id,'VIEW_PROJECT')
    return t

@router.get('/projects/{project_id}/fact-conflicts',tags=['Facts'])
async def fact_conflicts(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'VIEW_FACT')
    return list((await db.scalars(select(FactConflictGroup).where(FactConflictGroup.project_id==project_id))).all())

@router.post('/fact-conflicts/{group_id}/resolve',tags=['Facts'])
async def resolve_fact_conflict(group_id:UUID,fact_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    g=await db.get(FactConflictGroup,group_id)
    if not g: raise NotFound('FACT_CONFLICT_NOT_FOUND','Fact conflict not found')
    await ProjectAccess(db).require(g.project_id,ctx.membership_id,'CONFIRM_FACT')
    f=await db.get(Fact,fact_id)
    if not f or f.project_id!=g.project_id: raise NotFound('FACT_NOT_FOUND','Fact not found')
    g.status='RESOLVED'; g.resolved_fact_id=fact_id; g.resolved_by=ctx.user_id; g.resolved_at=datetime.now(timezone.utc)
    members=list((await db.scalars(select(Fact).join(FactConflictMember,FactConflictMember.fact_id==Fact.id).where(FactConflictMember.conflict_group_id==g.id))).all())
    for item in members: item.status='CONFIRMED' if item.id==fact_id else 'REJECTED'
    await db.commit()
    return {'status':'RESOLVED','resolved_fact_id':fact_id}

@router.post('/projects/{project_id}/standards/{version_id}',status_code=201,tags=['Standards'])
async def attach_standard(project_id:UUID,version_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'EDIT_PROJECT')
    obj=await StandardService(db).attach_to_project(project_id,version_id); await db.commit(); return obj

@router.post('/projects/{project_id}/ai/disclosure-mapping',status_code=202,tags=['AI'])
async def disclosure_mapping(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'EDIT_PROJECT')
    return await queue_ai(db,ctx,project_id,'DISCLOSURE_MAPPING','PROJECT',project_id)

@router.get('/projects/{project_id}/disclosures',tags=['Standards'])
async def project_disclosures(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'VIEW_PROJECT')
    q=select(ProjectDisclosure,Disclosure).join(Disclosure,ProjectDisclosure.disclosure_id==Disclosure.id).where(ProjectDisclosure.project_id==project_id)
    rows=(await db.execute(q)).all()
    return [{'id':pd.id,'code':d.code,'title':d.title,'applicability':pd.applicability,'coverage_status':pd.coverage_status} for pd,d in rows]

@router.get('/projects/{project_id}/requirements',tags=['Standards'])
async def project_requirements(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'VIEW_PROJECT')
    q=select(ProjectRequirementStatus,DisclosureRequirement).join(DisclosureRequirement,ProjectRequirementStatus.requirement_id==DisclosureRequirement.id).where(ProjectRequirementStatus.project_id==project_id)
    rows=(await db.execute(q)).all()
    return [{'id':x.id,'requirement_id':r.id,'code':r.requirement_code,'content':r.content,'status':x.status,'reason':x.reason} for x,r in rows]

@router.post('/projects/{project_id}/ai/missing-data-analysis',status_code=202,tags=['AI'])
async def missing_analysis(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'EDIT_PROJECT')
    return await queue_ai(db,ctx,project_id,'MISSING_DATA_ANALYSIS','PROJECT',project_id)

@router.get('/projects/{project_id}/missing-items',tags=['Standards'])
async def missing_items(project_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    await ProjectAccess(db).require(project_id,ctx.membership_id,'VIEW_PROJECT')
    return list((await db.scalars(select(MissingItem).where(MissingItem.project_id==project_id).order_by(MissingItem.created_at.desc()))).all())

@router.get('/sections/{section_id}/blocks',tags=['Reports'])
async def report_blocks(section_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    s=await db.get(ReportSection,section_id)
    if not s: raise NotFound('SECTION_NOT_FOUND','Section not found')
    await ProjectAccess(db).require(s.project_id,ctx.membership_id,'VIEW_PROJECT')
    return await ReportService(db).blocks(section_id)

@router.get('/blocks/{block_id}/revisions',tags=['Reports'])
async def block_revisions(block_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    b=await db.get(ReportBlock,block_id)
    if not b: raise NotFound('BLOCK_NOT_FOUND','Block not found')
    await ProjectAccess(db).require(b.project_id,ctx.membership_id,'VIEW_PROJECT')
    return list((await db.scalars(select(ReportBlockRevision).where(ReportBlockRevision.block_id==block_id).order_by(ReportBlockRevision.revision_no.desc()))).all())

@router.get('/block-revisions/{revision_id}/claims',tags=['Reports'])
async def revision_claims(revision_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    rev=await db.get(ReportBlockRevision,revision_id); b=await db.get(ReportBlock,rev.block_id) if rev else None
    if not b: raise NotFound('REVISION_NOT_FOUND','Revision not found')
    await ProjectAccess(db).require(b.project_id,ctx.membership_id,'VIEW_PROJECT')
    return list((await db.scalars(select(Claim).where(Claim.block_revision_id==revision_id))).all())

@router.get('/claims/{claim_id}/citations',tags=['Reports'])
async def claim_citations(claim_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    c=await db.get(Claim,claim_id); rev=await db.get(ReportBlockRevision,c.block_revision_id) if c else None; b=await db.get(ReportBlock,rev.block_id) if rev else None
    if not b: raise NotFound('CLAIM_NOT_FOUND','Claim not found')
    await ProjectAccess(db).require(b.project_id,ctx.membership_id,'VIEW_PROJECT')
    return list((await db.scalars(select(Citation).where(Citation.claim_id==claim_id))).all())

@router.get('/citations/{citation_id}/trace',tags=['Reports'])
async def citation_trace(citation_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    c=await db.get(Citation,citation_id)
    if not c: raise NotFound('CITATION_NOT_FOUND','Citation not found')
    claim=await db.get(Claim,c.claim_id); rev=await db.get(ReportBlockRevision,claim.block_revision_id); b=await db.get(ReportBlock,rev.block_id)
    await ProjectAccess(db).require(b.project_id,ctx.membership_id,'VIEW_PROJECT')
    fact=await db.get(Fact,c.fact_id) if c.fact_id else None; anchor=await db.get(DocumentAnchor,c.document_anchor_id) if c.document_anchor_id else None
    doc=None; version=None
    if anchor:
        version=await db.get(DocumentVersion,anchor.document_version_id); doc=await db.get(Document,version.document_id)
    return {'claim':{'id':claim.id,'text':claim.claim_text,'verification_status':claim.verification_status},'fact':{'id':fact.id,'name':fact.name,'status':fact.status,'unit':fact.unit} if fact else None,'anchor':{'id':anchor.id,'type':anchor.anchor_type,'page':anchor.page_start,'sheet':anchor.sheet_name,'cell':anchor.cell_range,'raw_text':anchor.raw_text} if anchor else None,'document':{'id':doc.id,'name':doc.name,'version_id':version.id} if doc else None}

@router.post('/reports/{report_id}/ai/consistency-check',status_code=202,tags=['AI'])
async def consistency_check(report_id:UUID,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    r=await db.get(Report,report_id)
    if not r: raise NotFound('REPORT_NOT_FOUND','Report not found')
    await ProjectAccess(db).require(r.project_id,ctx.membership_id,'VIEW_PROJECT')
    return await queue_ai(db,ctx,r.project_id,'CONSISTENCY_CHECK','REPORT',report_id)

from app.integrations.export import render_docx
@router.post('/reports/{report_id}/exports',status_code=202,tags=['Reports'])
async def export_report(report_id:UUID,body:ExportRequest,ctx:RequestContext=Depends(current_context),db=Depends(get_db)):
    r=await db.get(Report,report_id)
    if not r: raise NotFound('REPORT_NOT_FOUND','Report not found')
    await ProjectAccess(db).require(r.project_id,ctx.membership_id,'VIEW_PROJECT')
    if body.format.upper()!='DOCX': raise DomainError('EXPORT_FORMAT_UNSUPPORTED','Only DOCX is supported in MVP',422)
    export=ReportExport(report_id=report_id,format='DOCX',status='PENDING',created_by=ctx.user_id); db.add(export); await db.flush()
    task=await TaskService(db).create(ctx.tenant_id,r.project_id,ctx.user_id,'DOCX_EXPORT','REPORT_EXPORT',export.id)
    await db.commit(); run_ai_task.delay(str(task.id), str(ctx.tenant_id))
    return {'id':export.id,'status':export.status,'task_id':task.id}

# Service acceptance extension routers
from app.api.documents_ext import router as documents_ext_router
from app.api.facts_ext import router as facts_ext_router
from app.api.foundation_ext import router as foundation_ext_router
from app.api.operations_ext import router as operations_ext_router
from app.api.reports_ext import router as reports_ext_router
from app.api.standards_ext import router as standards_ext_router
from app.api.templates_ext import router as templates_ext_router

router.include_router(foundation_ext_router)
router.include_router(documents_ext_router)
router.include_router(facts_ext_router)
router.include_router(standards_ext_router)
router.include_router(templates_ext_router)
router.include_router(reports_ext_router)
router.include_router(operations_ext_router)
