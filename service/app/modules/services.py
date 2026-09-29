from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import Conflict, Forbidden, NotFound, DomainError
from app.core.permissions import allows
from app.core.security import hash_password, verify_password
from app.modules.models import *

def semantic_key(metric_code:str|None,name:str,period_start,period_end,entity_scope,dimensions:dict)->str:
    metric=(metric_code or name).strip().upper().replace(' ','_')
    period=f"{period_start or ''}:{period_end or ''}"
    dims='|'.join(f'{k}={dimensions[k]}' for k in sorted(dimensions))
    return f'{metric}|{period}|{entity_scope or "UNSPECIFIED"}|{dims}'

async def audit(session,tenant_id,user_id,action,resource_type,resource_id=None,project_id=None,before=None,after=None):
    session.add(AuditLog(tenant_id=tenant_id,user_id=user_id,action=action,resource_type=resource_type,resource_id=resource_id,project_id=project_id,before_data=before,after_data=after))

class IdentityService:
    def __init__(self,s:AsyncSession): self.s=s
    async def authenticate(self,email,password):
        user=await self.s.scalar(select(User).where(User.email==email,User.status=='ACTIVE'))
        if not user or not verify_password(password,user.password_hash): raise DomainError('AUTH_INVALID_CREDENTIALS','Invalid credentials',401)
        membership=await self.s.scalar(select(TenantMembership).where(TenantMembership.user_id==user.id,TenantMembership.status=='ACTIVE'))
        if not membership: raise Forbidden('TENANT_MEMBERSHIP_REQUIRED','No active tenant membership')
        return user,membership

class TenantService:
    def __init__(self,s:AsyncSession): self.s=s
    async def create_member(self,tenant_id:UUID,actor_user_id:UUID,data):
        existing=await self.s.scalar(select(User).where(User.email==str(data.email).lower()))
        if existing:
            user=existing
        else:
            user=User(email=str(data.email).lower(),name=data.name,password_hash=hash_password(data.password)); self.s.add(user); await self.s.flush()
        membership=await self.s.scalar(select(TenantMembership).where(TenantMembership.tenant_id==tenant_id,TenantMembership.user_id==user.id))
        if membership: raise Conflict('TENANT_MEMBER_ALREADY_EXISTS','User already belongs to tenant')
        if data.member_type=='CLIENT' and not data.company_id: raise DomainError('CLIENT_COMPANY_REQUIRED','Client member requires company_id',422)
        membership=TenantMembership(tenant_id=tenant_id,user_id=user.id,member_type=data.member_type,tenant_role=data.tenant_role,company_id=data.company_id); self.s.add(membership); await self.s.flush()
        await audit(self.s,tenant_id,actor_user_id,'TENANT_MEMBER_ADD','tenant_membership',membership.id)
        return user,membership
    async def list_members(self,tenant_id:UUID):
        q=select(TenantMembership,User).join(User,TenantMembership.user_id==User.id).where(TenantMembership.tenant_id==tenant_id,TenantMembership.status=='ACTIVE')
        return (await self.s.execute(q)).all()

class ProjectAccess:
    def __init__(self,s:AsyncSession): self.s=s
    async def membership(self,project_id:UUID,membership_id:UUID)->ProjectMember|None:
        return await self.s.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.membership_id==membership_id,ProjectMember.status=='ACTIVE'))
    async def require(self,project_id,membership_id,action):
        pm=await self.membership(project_id,membership_id)
        if not pm or not allows(pm.project_role,action): raise NotFound('PROJECT_NOT_FOUND','Project not found')
        return pm

class CompanyService:
    def __init__(self,s:AsyncSession): self.s=s
    async def create(self,tenant_id,user_id,data):
        obj=Company(tenant_id=tenant_id,**data.model_dump())
        self.s.add(obj); await self.s.flush(); await audit(self.s,tenant_id,user_id,'COMPANY_CREATE','company',obj.id,after={'name':obj.name}); return obj
    async def list(self,tenant_id): return list((await self.s.scalars(select(Company).where(Company.tenant_id==tenant_id,Company.deleted_at.is_(None)).order_by(Company.created_at.desc()))).all())
    async def get(self,tenant_id,id):
        x=await self.s.scalar(select(Company).where(Company.id==id,Company.tenant_id==tenant_id,Company.deleted_at.is_(None)))
        if not x: raise NotFound('COMPANY_NOT_FOUND','Company not found')
        return x

class ProjectService:
    def __init__(self,s:AsyncSession): self.s=s
    async def create(self,tenant_id,user_id,membership_id,data):
        company=await CompanyService(self.s).get(tenant_id,data.company_id)
        if data.period_start>data.period_end: raise DomainError('INVALID_PERIOD','period_start must not exceed period_end',422)
        p=Project(tenant_id=tenant_id,owner_membership_id=membership_id,**data.model_dump())
        self.s.add(p); await self.s.flush(); self.s.add(ProjectMember(tenant_id=tenant_id,project_id=p.id,membership_id=membership_id,project_role='OWNER'))
        await audit(self.s,tenant_id,user_id,'PROJECT_CREATE','project',p.id,p.id,after={'name':p.name}); return p
    async def list(self,tenant_id,membership_id):
        q=select(Project).join(ProjectMember,ProjectMember.project_id==Project.id).where(Project.tenant_id==tenant_id,Project.deleted_at.is_(None),ProjectMember.membership_id==membership_id,ProjectMember.status=='ACTIVE')
        return list((await self.s.scalars(q)).all())
    async def get(self,tenant_id,id,membership_id):
        await ProjectAccess(self.s).require(id,membership_id,'VIEW_PROJECT')
        p=await self.s.scalar(select(Project).where(Project.id==id,Project.tenant_id==tenant_id,Project.deleted_at.is_(None)))
        if not p: raise NotFound('PROJECT_NOT_FOUND','Project not found')
        return p
    async def add_member(self,tenant_id,user_id,owner_membership_id,project_id,membership_id,role):
        await ProjectAccess(self.s).require(project_id,owner_membership_id,'MANAGE_MEMBERS')
        project=await self.s.scalar(select(Project).where(Project.id==project_id,Project.tenant_id==tenant_id,Project.deleted_at.is_(None)))
        if not project: raise NotFound('PROJECT_NOT_FOUND','Project not found')
        tm=await self.s.scalar(select(TenantMembership).where(TenantMembership.id==membership_id,TenantMembership.tenant_id==tenant_id,TenantMembership.status=='ACTIVE'))
        if not tm: raise NotFound('MEMBERSHIP_NOT_FOUND','Membership not found')
        valid_roles={'OWNER','EDITOR','REVIEWER','CLIENT_MEMBER'}
        if role not in valid_roles: raise DomainError('INVALID_PROJECT_ROLE','Invalid project role',422)
        if role=='OWNER': raise DomainError('OWNER_TRANSFER_REQUIRED','Use owner transfer endpoint',422)
        if tm.member_type=='CLIENT':
            if tm.company_id!=project.company_id: raise DomainError('CLIENT_COMPANY_MISMATCH','Client member can only join projects for its own company',422)
            if role!='CLIENT_MEMBER': raise DomainError('CLIENT_ROLE_REQUIRED','Client membership requires CLIENT_MEMBER role',422)
        elif role=='CLIENT_MEMBER':
            raise DomainError('CLIENT_ROLE_INVALID','Internal member cannot use CLIENT_MEMBER role',422)
        exists=await self.s.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.membership_id==membership_id))
        if exists and exists.status=='ACTIVE': raise Conflict('PROJECT_MEMBER_ALREADY_EXISTS','Member already exists')
        if exists: exists.status='ACTIVE'; exists.project_role=role; pm=exists
        else: pm=ProjectMember(tenant_id=tenant_id,project_id=project_id,membership_id=membership_id,project_role=role); self.s.add(pm)
        await self.s.flush(); await audit(self.s,tenant_id,user_id,'PROJECT_MEMBER_ADD','project_member',pm.id,project_id); return pm

class FactService:
    def __init__(self,s:AsyncSession): self.s=s
    async def create_candidate(self,tenant_id,project_id,user_id,data,status='PENDING',confidence=None):
        metric_definition_id=data.metric_definition_id
        metric_code=data.metric_code
        if not metric_definition_id and metric_code:
            md=await self.s.scalar(select(MetricDefinition).where(MetricDefinition.code==metric_code,((MetricDefinition.tenant_id==tenant_id)|(MetricDefinition.tenant_id.is_(None)))).order_by(MetricDefinition.tenant_id.desc().nullslast()))
            if md: metric_definition_id=md.id
        if metric_definition_id and not metric_code:
            md=await self.s.get(MetricDefinition,metric_definition_id)
            metric_code=md.code if md else None
        sk=semantic_key(metric_code,data.name,data.period_start,data.period_end,data.entity_scope,data.dimensions)
        f=Fact(tenant_id=tenant_id,project_id=project_id,fact_type=data.fact_type,metric_definition_id=metric_definition_id,semantic_key=sk,name=data.name,value_type=data.value_type,number_value=data.number_value,text_value=data.text_value,boolean_value=data.boolean_value,date_value=data.date_value,json_value=data.json_value,raw_value=data.raw_value,unit=data.unit,period_start=data.period_start,period_end=data.period_end,entity_scope=data.entity_scope,dimensions=data.dimensions,status=status,source_type=data.source_type,confidence=confidence)
        self.s.add(f); await self.s.flush()
        for aid in data.anchor_ids:
            row=(await self.s.execute(select(DocumentAnchor,DocumentVersion,Document).join(DocumentVersion,DocumentAnchor.document_version_id==DocumentVersion.id).join(Document,DocumentVersion.document_id==Document.id).where(DocumentAnchor.id==aid,DocumentAnchor.project_id==project_id,Document.deleted_at.is_(None)))).first()
            if not row: raise NotFound('EVIDENCE_ANCHOR_NOT_FOUND','Evidence anchor not found')
            anchor,_,document=row
            if document.source_type not in {'EVIDENCE','HISTORICAL'}:
                raise DomainError('DOCUMENT_NOT_FACT_EVIDENCE','Reference and standard documents cannot establish client facts',422)
            self.s.add(FactEvidence(fact_id=f.id,document_anchor_id=anchor.id,created_by=user_id))
        self.s.add(FactRevision(fact_id=f.id,revision_no=1,snapshot={'name':f.name,'status':f.status,'semantic_key':sk},change_type='AI_CREATED' if data.source_type=='AI' else 'HUMAN_EDIT',changed_by=user_id))
        await self._detect_conflict(f)
        return f
    async def _detect_conflict(self,f):
        peers=list((await self.s.scalars(select(Fact).where(Fact.project_id==f.project_id,Fact.semantic_key==f.semantic_key,Fact.id!=f.id,Fact.status.in_(['PENDING','CONFIRMED','CONFLICT'])))).all())
        def val(x): return (x.number_value,x.text_value,x.boolean_value,x.date_value,str(x.json_value))
        diffs=[x for x in peers if val(x)!=val(f)]
        if diffs:
            group=await self.s.scalar(select(FactConflictGroup).where(FactConflictGroup.project_id==f.project_id,FactConflictGroup.semantic_key==f.semantic_key,FactConflictGroup.status=='OPEN'))
            if not group:
                group=FactConflictGroup(tenant_id=f.tenant_id,project_id=f.project_id,semantic_key=f.semantic_key,conflict_type='VALUE'); self.s.add(group); await self.s.flush()
                for p in diffs: self.s.add(FactConflictMember(conflict_group_id=group.id,fact_id=p.id)); p.status='CONFLICT'
            self.s.add(FactConflictMember(conflict_group_id=group.id,fact_id=f.id)); f.status='CONFLICT'
    async def list(self,project_id): return list((await self.s.scalars(select(Fact).where(Fact.project_id==project_id,Fact.deleted_at.is_(None)).order_by(Fact.created_at.desc()))).all())
    async def get(self,project_id,id):
        f=await self.s.scalar(select(Fact).where(Fact.id==id,Fact.project_id==project_id,Fact.deleted_at.is_(None)))
        if not f: raise NotFound('FACT_NOT_FOUND','Fact not found')
        return f
    async def confirm(self,project_id,id,user_id):
        f=await self.get(project_id,id)
        ev_count=await self.s.scalar(select(func.count()).select_from(FactEvidence).where(FactEvidence.fact_id==id))
        if not ev_count and f.source_type!='HUMAN': raise Conflict('FACT_NOT_CONFIRMABLE','Fact cannot be confirmed without evidence')
        rev=(await self.s.scalar(select(func.max(FactRevision.revision_no)).where(FactRevision.fact_id==id)) or 0)+1
        f.status='CONFIRMED'; f.confirmed_by=user_id; f.confirmed_at=datetime.now(timezone.utc)
        self.s.add(FactRevision(fact_id=id,revision_no=rev,snapshot={'status':'CONFIRMED'},change_type='CONFIRMED',changed_by=user_id)); return f

class TaskService:
    def __init__(self,s:AsyncSession): self.s=s
    async def create(self,tenant_id,project_id,user_id,task_type,target_type=None,target_id=None,input_json=None,idempotency_key=None):
        if idempotency_key:
            existing=await self.s.scalar(select(AITask).where(AITask.idempotency_key==idempotency_key))
            if existing: return existing
        t=AITask(tenant_id=tenant_id,project_id=project_id,created_by=user_id,task_type=task_type,target_type=target_type,target_id=target_id,input_json=input_json or {},idempotency_key=idempotency_key)
        self.s.add(t); await self.s.flush(); return t

class StandardService:
    def __init__(self,s:AsyncSession): self.s=s
    async def attach_to_project(self, project_id:UUID, version_id:UUID):
        exists=await self.s.scalar(select(ProjectStandard).where(ProjectStandard.project_id==project_id,ProjectStandard.standard_version_id==version_id))
        if exists: return exists
        ps=ProjectStandard(project_id=project_id,standard_version_id=version_id,is_primary=True); self.s.add(ps); await self.s.flush()
        disclosures=list((await self.s.scalars(select(Disclosure).where(Disclosure.standard_version_id==version_id))).all())
        for d in disclosures:
            if not await self.s.scalar(select(ProjectDisclosure).where(ProjectDisclosure.project_id==project_id,ProjectDisclosure.disclosure_id==d.id)):
                self.s.add(ProjectDisclosure(project_id=project_id,disclosure_id=d.id))
            reqs=list((await self.s.scalars(select(DisclosureRequirement).where(DisclosureRequirement.disclosure_id==d.id))).all())
            for r in reqs:
                if not await self.s.scalar(select(ProjectRequirementStatus).where(ProjectRequirementStatus.project_id==project_id,ProjectRequirementStatus.requirement_id==r.id)):
                    self.s.add(ProjectRequirementStatus(project_id=project_id,requirement_id=r.id,status='MISSING'))
        return ps
    async def map_confirmed_facts(self,project_id:UUID):
        facts=list((await self.s.scalars(select(Fact).where(Fact.project_id==project_id,Fact.status=='CONFIRMED'))).all())
        pds=list((await self.s.scalars(select(ProjectDisclosure).where(ProjectDisclosure.project_id==project_id))).all())
        created=0
        for pd in pds:
            reqs=list((await self.s.scalars(select(DisclosureRequirement).where(DisclosureRequirement.disclosure_id==pd.disclosure_id))).all())
            covered=0
            for r in reqs:
                codes=set((r.required_data_json or {}).get('metric_codes',[])); matching=[]
                if codes:
                    for f in facts:
                        if not f.metric_definition_id: continue
                        md=await self.s.get(MetricDefinition,f.metric_definition_id)
                        if md and md.code in codes: matching.append(f)
                prs=await self.s.scalar(select(ProjectRequirementStatus).where(ProjectRequirementStatus.project_id==project_id,ProjectRequirementStatus.requirement_id==r.id))
                if matching:
                    covered+=1
                    if prs: prs.status='COVERED'; prs.reason='Matched confirmed facts'
                    for f in matching:
                        if not await self.s.scalar(select(DisclosureFactMap).where(DisclosureFactMap.project_id==project_id,DisclosureFactMap.disclosure_id==pd.disclosure_id,DisclosureFactMap.fact_id==f.id)):
                            self.s.add(DisclosureFactMap(project_id=project_id,disclosure_id=pd.disclosure_id,fact_id=f.id,mapping_type='DIRECT',source_type='RULE',confirmed=True)); created+=1
                elif prs:
                    prs.status='MISSING'
            pd.coverage_status='COVERED' if reqs and covered==len(reqs) else ('PARTIAL' if covered else 'MISSING')
        return created
    async def generate_missing_items(self,tenant_id:UUID,project_id:UUID):
        rows=(await self.s.execute(select(ProjectRequirementStatus,DisclosureRequirement).join(DisclosureRequirement,ProjectRequirementStatus.requirement_id==DisclosureRequirement.id).where(ProjectRequirementStatus.project_id==project_id,ProjectRequirementStatus.status=='MISSING'))).all()
        created=[]
        for prs,r in rows:
            d=await self.s.get(Disclosure,r.disclosure_id)
            existing=await self.s.scalar(select(MissingItem).where(MissingItem.project_id==project_id,MissingItem.requirement_id==r.id,MissingItem.status.in_(['MISSING','REQUESTED','RECEIVED'])))
            if existing: continue
            m=MissingItem(tenant_id=tenant_id,project_id=project_id,disclosure_id=d.id,requirement_id=r.id,name=f'{d.code} {r.requirement_code}',description=r.content,missing_type='DATA',suggested_material='Please provide evidence/data supporting this disclosure requirement.')
            self.s.add(m); created.append(m)
        await self.s.flush(); return created

class ReportService:
    def __init__(self,s:AsyncSession): self.s=s
    async def create_report(self,tenant_id,project_id,user_id,title,language='zh-CN',template_version_id=None):
        r=Report(tenant_id=tenant_id,project_id=project_id,title=title,language=language,template_version_id=template_version_id,created_by=user_id); self.s.add(r); await self.s.flush()
        if template_version_id:
            sections=list((await self.s.scalars(select(ReportTemplateSection).where(ReportTemplateSection.template_version_id==template_version_id).order_by(ReportTemplateSection.level,ReportTemplateSection.sort_order))).all())
            mapping={}
            for ts in sections:
                s=ReportSection(tenant_id=tenant_id,project_id=project_id,report_id=r.id,parent_id=mapping.get(ts.parent_id),source_template_section_id=ts.id,title=ts.title,description=ts.description,level=ts.level,sort_order=ts.sort_order)
                self.s.add(s); await self.s.flush(); mapping[ts.id]=s.id
        return r
    async def blocks(self,section_id): return list((await self.s.scalars(select(ReportBlock).where(ReportBlock.section_id==section_id,ReportBlock.deleted_at.is_(None)).order_by(ReportBlock.sort_order))).all())
    async def consistency(self,report_id):
        sections=list((await self.s.scalars(select(ReportSection).where(ReportSection.report_id==report_id))).all()); ids=[s.id for s in sections]
        if not ids: return []
        blocks=list((await self.s.scalars(select(ReportBlock).where(ReportBlock.section_id.in_(ids),ReportBlock.deleted_at.is_(None)))).all()); b_ids=[b.id for b in blocks]
        if not b_ids: return []
        revs=list((await self.s.scalars(select(ReportBlockRevision).where(ReportBlockRevision.block_id.in_(b_ids)))).all()); r_ids=[r.id for r in revs]
        claims=list((await self.s.scalars(select(Claim).where(Claim.block_revision_id.in_(r_ids)))).all()) if r_ids else []
        issues=[]
        for c in claims:
            if c.risk_level=='HIGH' and c.verification_status!='VERIFIED': issues.append({'claim_id':str(c.id),'type':'UNVERIFIED_HIGH_RISK','severity':'HIGH','text':c.claim_text})
        return issues
