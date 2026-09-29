from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.llm import LLMGateway
from app.ai.schemas import FactExtractionResult, SectionPlan, SectionDraft
from app.modules.models import DocumentAnchor, Fact, Disclosure, DisclosureRequirement, ReportSection, ReportBlock, ReportBlockRevision, Claim, Citation, FactEvidence
from app.modules.schemas import FactCreate
from app.modules.services import FactService

class FactExtractionWorkflow:
    SYSTEM="You extract only facts explicitly supported by supplied evidence anchors. Never invent data. Every fact must list one or more supplied anchor_ids."
    def __init__(self,s:AsyncSession,llm:LLMGateway|None=None): self.s=s; self.llm=llm or LLMGateway()
    async def run(self,tenant_id,project_id,user_id,document_version_id):
        anchors=list((await self.s.scalars(select(DocumentAnchor).where(DocumentAnchor.document_version_id==document_version_id))).all())
        context='\n'.join(f'[{a.id}] {a.anchor_type} {a.sheet_name or ""} {a.cell_range or ""} {a.raw_text}' for a in anchors[:500])
        out=await self.llm.generate_structured(self.SYSTEM,context,FactExtractionResult)
        created=[]
        for c in out.facts:
            d=FactCreate(**c.model_dump(exclude={'confidence'}),source_type='AI')
            created.append(await FactService(self.s).create_candidate(tenant_id,project_id,user_id,d,confidence=c.confidence))
        return created

class SectionPlanningWorkflow:
    def __init__(self,s,llm=None): self.s=s; self.llm=llm or LLMGateway()
    async def run(self,project_id,section_id):
        section=await self.s.get(ReportSection,section_id)
        facts=list((await self.s.scalars(select(Fact).where(Fact.project_id==project_id,Fact.status=='CONFIRMED'))).all())
        prompt=f'Section: {section.title}\nConfirmed facts:\n'+'\n'.join(f'{f.id}: {f.name}={f.number_value or f.text_value} {f.unit or ""}' for f in facts)
        plan=await self.llm.generate_structured('Create an ESG section writing plan. Do not invent facts.',prompt,SectionPlan,'REASONING')
        section.writing_plan={'version':int(section.writing_plan.get('version',0))+1,**plan.model_dump(mode='json')}
        return section.writing_plan

class SectionWritingWorkflow:
    def __init__(self,s,llm=None): self.s=s; self.llm=llm or LLMGateway()
    async def run(self,tenant_id,project_id,user_id,section_id):
        section=await self.s.get(ReportSection,section_id)
        facts=list((await self.s.scalars(select(Fact).where(Fact.project_id==project_id,Fact.status=='CONFIRMED'))).all())
        prompt=f'Section: {section.title}\nPlan: {section.writing_plan}\nFacts:\n'+'\n'.join(f'{f.id}: {f.name}={f.number_value or f.text_value} {f.unit or ""}' for f in facts)
        draft=await self.llm.generate_structured('Write professional ESG content. Numeric/factual claims must cite provided fact IDs. Never invent client facts.',prompt,SectionDraft)
        blocks=[]
        max_order=0
        for db in draft.blocks:
            b=ReportBlock(tenant_id=tenant_id,project_id=project_id,section_id=section_id,block_type=db.type,sort_order=max_order,current_content=db.content,current_content_json={},current_revision_no=1,source_type='AI',created_by=user_id,updated_by=user_id); max_order+=1; self.s.add(b); await self.s.flush()
            rev=ReportBlockRevision(block_id=b.id,revision_no=1,content=db.content,content_json={},source_type='AI',created_by=user_id); self.s.add(rev); await self.s.flush()
            for cd in db.claims:
                claim=Claim(block_revision_id=rev.id,claim_text=cd.text,claim_type=cd.claim_type,risk_level=cd.risk_level); self.s.add(claim); await self.s.flush()
                for fid in cd.fact_ids:
                    f=next((x for x in facts if x.id==fid),None)
                    if not f: continue
                    fe=await self.s.scalar(select(FactEvidence).where(FactEvidence.fact_id==fid).limit(1))
                    self.s.add(Citation(claim_id=claim.id,citation_type='FACT',fact_id=fid,fact_evidence_id=fe.id if fe else None,document_anchor_id=fe.document_anchor_id if fe else None,created_by=user_id))
                    claim.verification_status='VERIFIED' if fe or f.source_type=='HUMAN' else 'UNVERIFIED'
            blocks.append(b)
        section.status='DRAFT'
        return blocks
