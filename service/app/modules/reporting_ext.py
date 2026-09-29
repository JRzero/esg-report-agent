from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, DomainError, NotFound
from app.modules.models import (
    Citation,
    Claim,
    Comment,
    Disclosure,
    Report,
    ReportBlock,
    ReportBlockRevision,
    ReportExport,
    ReportSection,
    ReportTemplate,
    ReportTemplateSection,
    ReportTemplateVersion,
    SectionDisclosureMap,
)


class TemplateLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def list(self, tenant_id: UUID):
        query = select(ReportTemplate).where(
            (ReportTemplate.tenant_id.is_(None)) | (ReportTemplate.tenant_id == tenant_id),
            ReportTemplate.status == "ACTIVE",
        ).order_by(ReportTemplate.created_at.desc())
        return list((await self.s.scalars(query)).all())

    async def create(self, tenant_id: UUID, user_id: UUID, data):
        item = ReportTemplate(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            template_type="TENANT",
            created_by=user_id,
        )
        self.s.add(item)
        await self.s.flush()
        return item

    async def get(self, tenant_id: UUID, template_id: UUID):
        item = await self.s.scalar(
            select(ReportTemplate).where(
                ReportTemplate.id == template_id,
                (ReportTemplate.tenant_id.is_(None)) | (ReportTemplate.tenant_id == tenant_id),
            )
        )
        if not item:
            raise NotFound("REPORT_TEMPLATE_NOT_FOUND", "Report template not found")
        return item

    async def add_version(self, template: ReportTemplate, user_id: UUID, data):
        number = (
            await self.s.scalar(
                select(func.max(ReportTemplateVersion.version_no)).where(
                    ReportTemplateVersion.template_id == template.id
                )
            )
            or 0
        ) + 1
        version = ReportTemplateVersion(
            template_id=template.id,
            version_no=number,
            source_type=data.source_type,
            source_document_id=data.source_document_id,
            created_by=user_id,
        )
        self.s.add(version)
        await self.s.flush()
        return version

    async def add_section(self, tenant_id: UUID, version_id: UUID, data):
        version = await self.s.get(ReportTemplateVersion, version_id)
        if not version:
            raise NotFound("TEMPLATE_VERSION_NOT_FOUND", "Template version not found")
        template = await self.get(tenant_id, version.template_id)
        if template.tenant_id is None:
            raise Conflict("SYSTEM_TEMPLATE_READ_ONLY", "System templates are read-only")
        if data.parent_id:
            parent = await self.s.get(ReportTemplateSection, data.parent_id)
            if not parent or parent.template_version_id != version_id:
                raise DomainError("INVALID_TEMPLATE_PARENT", "Invalid template parent", 422)
        item = ReportTemplateSection(
            template_version_id=version_id,
            **data.model_dump(),
        )
        self.s.add(item)
        await self.s.flush()
        return item


class ReportLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def list(self, project_id: UUID):
        return list(
            (
                await self.s.scalars(
                    select(Report)
                    .where(Report.project_id == project_id)
                    .order_by(Report.created_at.desc())
                )
            ).all()
        )

    async def get(self, project_id: UUID, report_id: UUID):
        item = await self.s.scalar(
            select(Report).where(Report.id == report_id, Report.project_id == project_id)
        )
        if not item:
            raise NotFound("REPORT_NOT_FOUND", "Report not found")
        return item

    async def update(self, report: Report, data):
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(report, key, value)
        return report

    async def section(self, section_id: UUID) -> ReportSection:
        item = await self.s.get(ReportSection, section_id)
        if not item:
            raise NotFound("SECTION_NOT_FOUND", "Section not found")
        return item

    async def update_section(self, section: ReportSection, data):
        values = data.model_dump(exclude_unset=True)
        if "parent_id" in values and values["parent_id"]:
            parent = await self.section(values["parent_id"])
            if parent.report_id != section.report_id or parent.id == section.id:
                raise DomainError("INVALID_SECTION_PARENT", "Invalid section parent", 422)
        for key, value in values.items():
            setattr(section, key, value)
        return section

    async def delete_section(self, section: ReportSection):
        children = await self.s.scalar(
            select(func.count())
            .select_from(ReportSection)
            .where(ReportSection.parent_id == section.id)
        )
        blocks = await self.s.scalar(
            select(func.count())
            .select_from(ReportBlock)
            .where(ReportBlock.section_id == section.id, ReportBlock.deleted_at.is_(None))
        )
        if children or blocks:
            raise Conflict("SECTION_NOT_EMPTY", "Remove child sections and blocks first")
        await self.s.delete(section)

    async def reorder(self, report_id: UUID, items):
        for item in items:
            section = await self.section(item.section_id)
            if section.report_id != report_id:
                raise DomainError("SECTION_REPORT_MISMATCH", "Section belongs to another report", 422)
            if item.parent_id:
                parent = await self.section(item.parent_id)
                if parent.report_id != report_id or parent.id == section.id:
                    raise DomainError("INVALID_SECTION_PARENT", "Invalid section parent", 422)
            section.parent_id = item.parent_id
            section.sort_order = item.sort_order

    async def add_disclosure(self, section: ReportSection, disclosure_id: UUID, mapping_type: str):
        disclosure = await self.s.get(Disclosure, disclosure_id)
        if not disclosure:
            raise NotFound("DISCLOSURE_NOT_FOUND", "Disclosure not found")
        existing = await self.s.scalar(
            select(SectionDisclosureMap).where(
                SectionDisclosureMap.section_id == section.id,
                SectionDisclosureMap.disclosure_id == disclosure_id,
            )
        )
        if existing:
            return existing
        item = SectionDisclosureMap(
            section_id=section.id,
            disclosure_id=disclosure_id,
            mapping_type=mapping_type,
        )
        self.s.add(item)
        await self.s.flush()
        return item

    async def block(self, block_id: UUID) -> ReportBlock:
        item = await self.s.scalar(
            select(ReportBlock).where(
                ReportBlock.id == block_id,
                ReportBlock.deleted_at.is_(None),
            )
        )
        if not item:
            raise NotFound("BLOCK_NOT_FOUND", "Block not found")
        return item

    async def create_block(self, section: ReportSection, user_id: UUID, data):
        block = ReportBlock(
            tenant_id=section.tenant_id,
            project_id=section.project_id,
            section_id=section.id,
            block_type=data.block_type,
            sort_order=data.sort_order,
            current_content=data.content,
            current_content_json=data.content_json,
            current_revision_no=1,
            source_type="HUMAN",
            created_by=user_id,
            updated_by=user_id,
        )
        self.s.add(block)
        await self.s.flush()
        self.s.add(
            ReportBlockRevision(
                block_id=block.id,
                revision_no=1,
                content=data.content,
                content_json=data.content_json,
                source_type="HUMAN",
                change_reason="Created",
                created_by=user_id,
            )
        )
        return block

    async def update_block(self, block: ReportBlock, user_id: UUID, data):
        next_revision = block.current_revision_no + 1
        block.current_content = data.content
        block.current_content_json = data.content_json
        block.current_revision_no = next_revision
        block.source_type = "HUMAN"
        block.updated_by = user_id
        self.s.add(
            ReportBlockRevision(
                block_id=block.id,
                revision_no=next_revision,
                content=data.content,
                content_json=data.content_json,
                source_type="HUMAN",
                change_reason=data.change_reason,
                created_by=user_id,
            )
        )
        return block

    async def restore_block(self, block: ReportBlock, revision_no: int, user_id: UUID):
        source = await self.s.scalar(
            select(ReportBlockRevision).where(
                ReportBlockRevision.block_id == block.id,
                ReportBlockRevision.revision_no == revision_no,
            )
        )
        if not source:
            raise NotFound("REVISION_NOT_FOUND", "Block revision not found")
        next_revision = block.current_revision_no + 1
        block.current_content = source.content
        block.current_content_json = source.content_json or {}
        block.current_revision_no = next_revision
        block.source_type = "HUMAN"
        block.updated_by = user_id
        self.s.add(
            ReportBlockRevision(
                block_id=block.id,
                revision_no=next_revision,
                content=source.content,
                content_json=source.content_json or {},
                source_type="HUMAN",
                change_reason=f"Restore revision {revision_no}",
                created_by=user_id,
            )
        )
        return block

    async def delete_block(self, block: ReportBlock):
        block.deleted_at = datetime.now(timezone.utc)


class CommentLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, tenant_id: UUID, project_id: UUID, user_id: UUID, data):
        if not data.section_id and not data.block_id:
            raise DomainError("COMMENT_TARGET_REQUIRED", "Comment requires section_id or block_id", 422)
        if data.section_id:
            section = await self.s.get(ReportSection, data.section_id)
            if not section or section.project_id != project_id:
                raise NotFound("SECTION_NOT_FOUND", "Section not found")
        if data.block_id:
            block = await self.s.get(ReportBlock, data.block_id)
            if not block or block.project_id != project_id:
                raise NotFound("BLOCK_NOT_FOUND", "Block not found")
        if data.parent_id:
            parent = await self.s.get(Comment, data.parent_id)
            if not parent or parent.project_id != project_id:
                raise NotFound("COMMENT_NOT_FOUND", "Parent comment not found")
        item = Comment(
            tenant_id=tenant_id,
            project_id=project_id,
            section_id=data.section_id,
            block_id=data.block_id,
            parent_id=data.parent_id,
            author_user_id=user_id,
            body=data.body,
        )
        self.s.add(item)
        await self.s.flush()
        return item

    async def resolve(self, comment_id: UUID, user_id: UUID):
        item = await self.s.get(Comment, comment_id)
        if not item:
            raise NotFound("COMMENT_NOT_FOUND", "Comment not found")
        item.status = "RESOLVED"
        item.resolved_by = user_id
        item.resolved_at = datetime.now(timezone.utc)
        return item


async def verify_claim(session: AsyncSession, claim_id: UUID):
    claim = await session.get(Claim, claim_id)
    if not claim:
        raise NotFound("CLAIM_NOT_FOUND", "Claim not found")
    citations = list(
        (await session.scalars(select(Citation).where(Citation.claim_id == claim.id))).all()
    )
    claim.verification_status = "VERIFIED" if citations else "UNVERIFIED"
    return claim


async def get_export(session: AsyncSession, export_id: UUID):
    item = await session.get(ReportExport, export_id)
    if not item:
        raise NotFound("EXPORT_NOT_FOUND", "Report export not found")
    return item


class AgentReportWriter:
    """Persistence boundary used by Agent workflows.

    Agent code may reason and call external models, but all report mutations pass
    through this service so revision/citation invariants stay centralized.
    """

    def __init__(self, session: AsyncSession):
        self.s = session

    async def apply_plan(self, section_id: UUID, plan: dict):
        section = await self.s.get(ReportSection, section_id)
        if not section:
            raise NotFound("SECTION_NOT_FOUND", "Section not found")
        version = int((section.writing_plan or {}).get("version", 0)) + 1
        section.writing_plan = {"version": version, **plan}
        return section.writing_plan

    async def apply_draft(
        self,
        tenant_id: UUID,
        project_id: UUID,
        user_id: UUID,
        section_id: UUID,
        draft,
        facts: list,
    ):
        from app.modules.models import FactEvidence

        section = await self.s.get(ReportSection, section_id)
        if not section or section.project_id != project_id:
            raise NotFound("SECTION_NOT_FOUND", "Section not found")
        existing_max = (
            await self.s.scalar(
                select(func.max(ReportBlock.sort_order)).where(
                    ReportBlock.section_id == section_id,
                    ReportBlock.deleted_at.is_(None),
                )
            )
            or -1
        )
        fact_map = {fact.id: fact for fact in facts}
        blocks = []
        order = existing_max + 1
        for draft_block in draft.blocks:
            block = ReportBlock(
                tenant_id=tenant_id,
                project_id=project_id,
                section_id=section_id,
                block_type=draft_block.type,
                sort_order=order,
                current_content=draft_block.content,
                current_content_json={},
                current_revision_no=1,
                source_type="AI",
                created_by=user_id,
                updated_by=user_id,
            )
            order += 1
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
            for claim_draft in draft_block.claims:
                claim = Claim(
                    block_revision_id=revision.id,
                    claim_text=claim_draft.text,
                    claim_type=claim_draft.claim_type,
                    risk_level=claim_draft.risk_level,
                )
                self.s.add(claim)
                await self.s.flush()
                verified = False
                for fact_id in claim_draft.fact_ids:
                    fact = fact_map.get(fact_id)
                    if not fact:
                        continue
                    evidence = await self.s.scalar(
                        select(FactEvidence).where(FactEvidence.fact_id == fact_id).limit(1)
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
                    verified = verified or bool(evidence or fact.source_type == "HUMAN")
                claim.verification_status = "VERIFIED" if verified else "UNVERIFIED"
            blocks.append(block)
        section.status = "DRAFT"
        return blocks
