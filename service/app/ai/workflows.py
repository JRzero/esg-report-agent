from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMGateway
from app.ai.schemas import FactExtractionResult, SectionDraft, SectionPlan
from app.core.errors import DomainError, NotFound
from app.modules.models import (
    Document,
    DocumentAnchor,
    DocumentVersion,
    Fact,
    MissingItem,
    ReportSection,
)
from app.modules.reporting_ext import AgentReportWriter
from app.modules.schemas import FactCreate
from app.modules.services import FactService


class FactExtractionWorkflow:
    SYSTEM = (
        "You extract only client facts explicitly supported by the supplied evidence anchors. "
        "Never invent data, policies, actions or outcomes. Every fact must list one or more "
        "anchor_ids from the supplied evidence."
    )

    def __init__(self, session: AsyncSession, llm: LLMGateway | None = None):
        self.s = session
        self.llm = llm or LLMGateway()

    async def run(self, tenant_id, project_id, user_id, document_version_id):
        version = await self.s.get(DocumentVersion, document_version_id)
        document = await self.s.get(Document, version.document_id) if version else None
        if not document or document.project_id != project_id:
            raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
        if document.source_type not in {"EVIDENCE", "HISTORICAL"}:
            raise DomainError(
                "DOCUMENT_NOT_FACT_EVIDENCE",
                "Reference and standard documents cannot establish client facts",
                422,
            )

        anchors = list(
            (
                await self.s.scalars(
                    select(DocumentAnchor).where(
                        DocumentAnchor.document_version_id == document_version_id
                    )
                )
            ).all()
        )
        evidence_anchors = [anchor for anchor in anchors if anchor.raw_text.strip()]
        if not evidence_anchors:
            raise DomainError(
                "NO_TEXTUAL_EVIDENCE",
                "No textual evidence anchors are available for fact extraction",
                422,
            )
        allowed_ids = {anchor.id for anchor in evidence_anchors}
        context = "\n".join(
            f"[{anchor.id}] {anchor.anchor_type} {anchor.sheet_name or ''} "
            f"{anchor.cell_range or ''} {anchor.raw_text}"
            for anchor in evidence_anchors[:500]
        )

        # End the read transaction before the external model call.
        await self.s.commit()
        output = await self.llm.generate_structured(
            self.SYSTEM,
            context,
            FactExtractionResult,
        )

        created = []
        for candidate in output.facts:
            if not candidate.anchor_ids or any(
                anchor_id not in allowed_ids for anchor_id in candidate.anchor_ids
            ):
                raise DomainError(
                    "AI_EVIDENCE_OUT_OF_SCOPE",
                    "Model returned evidence outside the supplied document version",
                    422,
                )
            data = FactCreate(
                **candidate.model_dump(exclude={"confidence"}),
                source_type="AI",
            )
            created.append(
                await FactService(self.s).create_candidate(
                    tenant_id,
                    project_id,
                    user_id,
                    data,
                    confidence=candidate.confidence,
                )
            )
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
                    select(Fact).where(
                        Fact.project_id == project_id,
                        Fact.status == "CONFIRMED",
                        Fact.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        missing = list(
            (
                await self.s.scalars(
                    select(MissingItem).where(
                        MissingItem.project_id == project_id,
                        MissingItem.status.in_(["MISSING", "REQUESTED"]),
                    )
                )
            ).all()
        )
        prompt = (
            f"Section: {section.title}\n"
            f"Confirmed facts:\n"
            + "\n".join(
                f"{fact.id}: {fact.name}="
                f"{fact.number_value if fact.number_value is not None else fact.text_value} "
                f"{fact.unit or ''}"
                for fact in facts
            )
            + "\nMissing items:\n"
            + "\n".join(item.name for item in missing[:100])
        )
        await self.s.commit()
        plan = await self.llm.generate_structured(
            "Create an ESG section writing plan. Use confirmed facts only. "
            "Explicitly surface missing evidence instead of inventing content.",
            prompt,
            SectionPlan,
            "REASONING",
        )
        return await AgentReportWriter(self.s).apply_plan(
            section_id,
            plan.model_dump(mode="json"),
        )


class SectionWritingWorkflow:
    def __init__(self, session: AsyncSession, llm: LLMGateway | None = None):
        self.s = session
        self.llm = llm or LLMGateway()

    async def run(self, tenant_id, project_id, user_id, section_id):
        section = await self.s.get(ReportSection, section_id)
        if not section or section.project_id != project_id:
            raise NotFound("SECTION_NOT_FOUND", "Section not found")
        facts = list(
            (
                await self.s.scalars(
                    select(Fact).where(
                        Fact.project_id == project_id,
                        Fact.status == "CONFIRMED",
                        Fact.deleted_at.is_(None),
                    )
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
        await self.s.commit()
        draft = await self.llm.generate_structured(
            "Write professional ESG content. Every numeric or client factual claim must "
            "cite one or more provided fact IDs. Never invent client facts, policies, "
            "certifications, actions, achievements or effectiveness.",
            prompt,
            SectionDraft,
        )
        return await AgentReportWriter(self.s).apply_draft(
            tenant_id,
            project_id,
            user_id,
            section_id,
            draft,
            facts,
        )
