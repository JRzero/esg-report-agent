from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMGateway
from app.ai.schemas import FactExtractionResult, SectionDraft, SectionPlan
from app.core.errors import Conflict, NotFound
from app.evals.quality import validate_fact_extraction, validate_section_draft
from app.modules.models import (
    Citation,
    Claim,
    Document,
    DocumentAnchor,
    DocumentVersion,
    Fact,
    FactEvidence,
    ReportBlock,
    ReportBlockRevision,
    ReportSection,
)
from app.modules.schemas import FactCreate
from app.modules.services import FactService, ReportService


class FactExtractionWorkflow:
    SYSTEM = (
        "You extract only facts explicitly supported by supplied evidence anchors. "
        "Never invent data. Every fact must list one or more supplied anchor_ids."
    )

    def __init__(self, session: AsyncSession, llm: LLMGateway | None = None):
        self.s = session
        self.llm = llm or LLMGateway()

    async def run(self, tenant_id, project_id, user_id, document_version_id):
        version = await self.s.get(DocumentVersion, document_version_id)
        document = await self.s.get(Document, version.document_id) if version else None
        if not version or not document or document.project_id != project_id:
            raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
        if document.source_type != "EVIDENCE":
            raise Conflict(
                "FACT_EXTRACTION_SOURCE_FORBIDDEN",
                "Fact extraction is allowed only for EVIDENCE documents",
            )
        anchors = list(
            (
                await self.s.scalars(
                    select(DocumentAnchor)
                    .where(DocumentAnchor.document_version_id == document_version_id)
                    .order_by(DocumentAnchor.id)
                )
            ).all()
        )
        if not anchors:
            raise Conflict("NO_EVIDENCE_ANCHORS", "Document has no parsed evidence anchors")
        context = "\n".join(
            f"[{anchor.id}] {anchor.anchor_type} {anchor.sheet_name or ''} "
            f"{anchor.cell_range or ''} {anchor.raw_text}"
            for anchor in anchors[:500]
        )
        out = await self.llm.generate_structured(self.SYSTEM, context, FactExtractionResult)
        valid_anchor_ids = {anchor.id for anchor in anchors}
        grounding = validate_fact_extraction(out, valid_anchor_ids)
        if not grounding.passed:
            raise Conflict(
                "AI_OUTPUT_UNGROUNDED",
                "Fact extraction output referenced missing or unknown evidence anchors",
            )
        created = []
        for candidate in out.facts:
            data = FactCreate(**candidate.model_dump(exclude={"confidence"}), source_type="AI")
            created.append(
                await FactService(self.s).create_candidate(
                    tenant_id,
                    project_id,
                    user_id,
                    data,
                    confidence=candidate.confidence,
                )
            )
        version.fact_extraction_status = "READY"
        return created


class SectionPlanningWorkflow:
    def __init__(self, session: AsyncSession, llm: LLMGateway | None = None):
        self.s = session
        self.llm = llm or LLMGateway()

    async def run(self, project_id, section_id):
        section = await self.s.get(ReportSection, section_id)
        if not section or section.project_id != project_id:
            raise NotFound("SECTION_NOT_FOUND", "Section not found")
        facts = list(
            (
                await self.s.scalars(
                    select(Fact)
                    .where(
                        Fact.project_id == project_id,
                        Fact.status == "CONFIRMED",
                        Fact.deleted_at.is_(None),
                    )
                    .order_by(Fact.created_at)
                )
            ).all()
        )
        prompt = (
            f"Section: {section.title}\n"
            f"Description: {section.description or ''}\n"
            "Confirmed facts:\n"
            + "\n".join(
                f"{fact.id}: {fact.name}="
                f"{fact.number_value if fact.number_value is not None else fact.text_value} "
                f"{fact.unit or ''}"
                for fact in facts
            )
        )
        plan = await self.llm.generate_structured(
            "Create an ESG section writing plan. Do not invent facts. "
            "Explicitly identify missing evidence instead of filling gaps.",
            prompt,
            SectionPlan,
            "REASONING",
        )
        allowed_fact_ids = {fact.id for fact in facts}
        unknown_plan_facts = set(plan.fact_ids) - allowed_fact_ids
        if unknown_plan_facts:
            raise Conflict(
                "AI_OUTPUT_UNGROUNDED",
                "Writing plan referenced Facts outside the confirmed project Fact context",
            )
        current = section.writing_plan or {}
        section.writing_plan = {
            "version": int(current.get("version", 0)) + 1,
            **plan.model_dump(mode="json"),
        }
        section.status = "DRAFT"
        return section.writing_plan


class SectionWritingWorkflow:
    def __init__(self, session: AsyncSession, llm: LLMGateway | None = None):
        self.s = session
        self.llm = llm or LLMGateway()

    async def run(self, tenant_id, project_id, user_id, section_id):
        section = await self.s.get(ReportSection, section_id)
        if not section or section.project_id != project_id:
            raise NotFound("SECTION_NOT_FOUND", "Section not found")
        if not section.writing_plan:
            raise Conflict("WRITING_PLAN_REQUIRED", "Generate and confirm a writing plan first")
        facts = list(
            (
                await self.s.scalars(
                    select(Fact)
                    .where(
                        Fact.project_id == project_id,
                        Fact.status == "CONFIRMED",
                        Fact.deleted_at.is_(None),
                    )
                    .order_by(Fact.created_at)
                )
            ).all()
        )
        prompt = (
            f"Section: {section.title}\n"
            f"Plan: {section.writing_plan}\n"
            "Confirmed facts:\n"
            + "\n".join(
                f"{fact.id}: {fact.name}="
                f"{fact.number_value if fact.number_value is not None else fact.text_value} "
                f"{fact.unit or ''}"
                for fact in facts
            )
        )
        draft = await self.llm.generate_structured(
            "Write professional ESG content. "
            "Every factual or numeric claim must cite one or more provided fact IDs. "
            "Never invent client facts. If evidence is insufficient, omit the claim.",
            prompt,
            SectionDraft,
        )
        grounding = validate_section_draft(draft, {fact.id for fact in facts})
        if not grounding.passed:
            raise Conflict(
                "AI_OUTPUT_UNGROUNDED",
                "Section draft contains factual claims without valid confirmed Fact references",
            )
        max_order = (
            await self.s.scalar(
                select(func.max(ReportBlock.sort_order)).where(
                    ReportBlock.section_id == section_id,
                    ReportBlock.deleted_at.is_(None),
                )
            )
            or -1
        )
        blocks = []
        verifier = ReportService(self.s)
        for draft_block in draft.blocks:
            max_order += 1
            block = ReportBlock(
                tenant_id=tenant_id,
                project_id=project_id,
                section_id=section_id,
                block_type=draft_block.type,
                sort_order=max_order,
                current_content=draft_block.content,
                current_content_json={},
                current_revision_no=1,
                source_type="AI",
                created_by=user_id,
                updated_by=user_id,
            )
            self.s.add(block)
            await self.s.flush()
            revision = ReportBlockRevision(
                block_id=block.id,
                revision_no=1,
                content=draft_block.content,
                content_json={},
                source_type="AI",
                created_by=user_id,
            )
            self.s.add(revision)
            await self.s.flush()
            for claim_data in draft_block.claims:
                claim = Claim(
                    block_revision_id=revision.id,
                    claim_text=claim_data.text,
                    claim_type=claim_data.claim_type,
                    risk_level=claim_data.risk_level,
                )
                self.s.add(claim)
                await self.s.flush()
                for fact_id in claim_data.fact_ids:
                    fact = next((item for item in facts if item.id == fact_id), None)
                    if not fact:
                        continue
                    evidence = await self.s.scalar(
                        select(FactEvidence)
                        .where(FactEvidence.fact_id == fact_id)
                        .order_by(FactEvidence.id)
                        .limit(1)
                    )
                    self.s.add(
                        Citation(
                            claim_id=claim.id,
                            citation_type="FACT",
                            fact_id=fact_id,
                            fact_evidence_id=evidence.id if evidence else None,
                            document_anchor_id=evidence.document_anchor_id if evidence else None,
                            created_by=user_id,
                        )
                    )
                await self.s.flush()
                await verifier.verify_claim(claim)
            blocks.append(block)
        section.status = "DRAFT"
        return blocks
