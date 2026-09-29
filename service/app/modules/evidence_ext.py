from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, DomainError, NotFound
from app.modules.models import (
    Document,
    DocumentAnchor,
    DocumentVersion,
    Fact,
    FactEvidence,
    FactRevision,
)
from app.modules.services import audit, semantic_key


ALLOWED_SOURCE_TYPES = {"EVIDENCE", "REFERENCE", "STANDARD", "HISTORICAL"}
FACT_EVIDENCE_SOURCE_TYPES = {"EVIDENCE", "HISTORICAL"}


class DocumentLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    @staticmethod
    def validate_source_type(source_type: str) -> str:
        value = source_type.upper()
        if value not in ALLOWED_SOURCE_TYPES:
            raise DomainError("INVALID_DOCUMENT_SOURCE_TYPE", "Invalid document source type", 422)
        return value

    async def get(self, project_id: UUID, document_id: UUID) -> Document:
        item = await self.s.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.project_id == project_id,
                Document.deleted_at.is_(None),
            )
        )
        if not item:
            raise NotFound("DOCUMENT_NOT_FOUND", "Document not found")
        return item

    async def list(self, project_id: UUID):
        return list(
            (
                await self.s.scalars(
                    select(Document)
                    .where(Document.project_id == project_id, Document.deleted_at.is_(None))
                    .order_by(Document.created_at.desc())
                )
            ).all()
        )

    async def versions(self, document_id: UUID):
        return list(
            (
                await self.s.scalars(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == document_id)
                    .order_by(DocumentVersion.version_no.desc())
                )
            ).all()
        )

    async def create_version(
        self,
        document: Document,
        user_id: UUID,
        filename: str,
        mime_type: str | None,
        data: bytes,
    ) -> DocumentVersion:
        max_version = (
            await self.s.scalar(
                select(func.max(DocumentVersion.version_no)).where(
                    DocumentVersion.document_id == document.id
                )
            )
            or 0
        )
        version_no = max_version + 1
        extension = Path(filename).suffix.lower()
        object_key = (
            f"tenants/{document.tenant_id}/projects/{document.project_id}/documents/"
            f"{document.id}/versions/v{version_no}/original{extension}"
        )
        version = DocumentVersion(
            document_id=document.id,
            version_no=version_no,
            original_filename=filename,
            mime_type=mime_type,
            file_extension=extension,
            file_size=len(data),
            object_key=object_key,
            sha256=sha256(data).hexdigest(),
            uploaded_by=user_id,
        )
        self.s.add(version)
        await self.s.flush()
        await audit(
            self.s,
            document.tenant_id,
            user_id,
            "DOCUMENT_VERSION_UPLOAD",
            "document_version",
            version.id,
            document.project_id,
            after={"version_no": version_no, "filename": filename},
        )
        return version

    async def delete(self, document: Document, user_id: UUID):
        document.deleted_at = datetime.now(timezone.utc)
        document.status = "DELETED"
        await audit(
            self.s,
            document.tenant_id,
            user_id,
            "DOCUMENT_DELETE",
            "document",
            document.id,
            document.project_id,
        )


class FactLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, project_id: UUID, fact_id: UUID) -> Fact:
        item = await self.s.scalar(
            select(Fact).where(
                Fact.id == fact_id,
                Fact.project_id == project_id,
                Fact.deleted_at.is_(None),
            )
        )
        if not item:
            raise NotFound("FACT_NOT_FOUND", "Fact not found")
        return item

    async def _revision(self, fact: Fact, user_id: UUID, change_type: str, snapshot: dict):
        revision = (
            await self.s.scalar(
                select(func.max(FactRevision.revision_no)).where(FactRevision.fact_id == fact.id)
            )
            or 0
        ) + 1
        self.s.add(
            FactRevision(
                fact_id=fact.id,
                revision_no=revision,
                snapshot=snapshot,
                change_type=change_type,
                changed_by=user_id,
            )
        )

    async def update(self, fact: Fact, user_id: UUID, data):
        values = data.model_dump(exclude_unset=True)
        if not values:
            return fact
        before = {
            "name": fact.name,
            "status": fact.status,
            "number_value": str(fact.number_value) if fact.number_value is not None else None,
            "text_value": fact.text_value,
            "unit": fact.unit,
        }
        for key, value in values.items():
            setattr(fact, key, value)
        fact.semantic_key = semantic_key(
            None,
            fact.name,
            fact.period_start,
            fact.period_end,
            fact.entity_scope,
            fact.dimensions or {},
        )
        fact.status = "PENDING"
        fact.confirmed_by = None
        fact.confirmed_at = None
        await self._revision(
            fact,
            user_id,
            "HUMAN_EDIT",
            {"before": before, "after": values, "status": "PENDING"},
        )
        return fact

    async def reject(self, fact: Fact, user_id: UUID, reason: str):
        fact.status = "REJECTED"
        fact.confirmed_by = None
        fact.confirmed_at = None
        await self._revision(
            fact,
            user_id,
            "REJECTED",
            {"status": "REJECTED", "reason": reason},
        )
        return fact

    async def _validate_anchor(self, project_id: UUID, anchor_id: UUID) -> DocumentAnchor:
        query = (
            select(DocumentAnchor, DocumentVersion, Document)
            .join(DocumentVersion, DocumentAnchor.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentAnchor.id == anchor_id,
                DocumentAnchor.project_id == project_id,
                Document.deleted_at.is_(None),
            )
        )
        row = (await self.s.execute(query)).first()
        if not row:
            raise NotFound("EVIDENCE_ANCHOR_NOT_FOUND", "Evidence anchor not found")
        anchor, _, document = row
        if document.source_type not in FACT_EVIDENCE_SOURCE_TYPES:
            raise DomainError(
                "DOCUMENT_NOT_FACT_EVIDENCE",
                "Reference and standard documents cannot establish client facts",
                422,
            )
        return anchor

    async def add_evidence(
        self,
        fact: Fact,
        user_id: UUID,
        anchor_id: UUID,
        evidence_role: str = "PRIMARY",
    ):
        await self._validate_anchor(fact.project_id, anchor_id)
        existing = await self.s.scalar(
            select(FactEvidence).where(
                FactEvidence.fact_id == fact.id,
                FactEvidence.document_anchor_id == anchor_id,
            )
        )
        if existing:
            return existing
        item = FactEvidence(
            fact_id=fact.id,
            document_anchor_id=anchor_id,
            evidence_role=evidence_role,
            created_by=user_id,
        )
        self.s.add(item)
        await self.s.flush()
        await self._revision(
            fact,
            user_id,
            "EVIDENCE_ADDED",
            {"anchor_id": str(anchor_id), "evidence_role": evidence_role},
        )
        return item

    async def remove_evidence(self, fact: Fact, user_id: UUID, anchor_id: UUID):
        item = await self.s.scalar(
            select(FactEvidence).where(
                FactEvidence.fact_id == fact.id,
                FactEvidence.document_anchor_id == anchor_id,
            )
        )
        if not item:
            raise NotFound("FACT_EVIDENCE_NOT_FOUND", "Fact evidence not found")
        if fact.status == "CONFIRMED" and fact.source_type != "HUMAN":
            count = await self.s.scalar(
                select(func.count())
                .select_from(FactEvidence)
                .where(FactEvidence.fact_id == fact.id)
            )
            if count <= 1:
                raise Conflict(
                    "CONFIRMED_FACT_REQUIRES_EVIDENCE",
                    "Cannot remove the last evidence from a confirmed AI fact",
                )
        await self.s.delete(item)
        await self._revision(
            fact,
            user_id,
            "EVIDENCE_REMOVED",
            {"anchor_id": str(anchor_id)},
        )
