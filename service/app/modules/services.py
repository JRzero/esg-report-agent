from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, DomainError, NotFound
from app.core.permissions import allows
from app.core.security import hash_password, verify_password
from app.modules.models import (
    AITask,
    AuditLog,
    Citation,
    Claim,
    Company,
    Disclosure,
    DisclosureFactMap,
    DisclosureRequirement,
    Document,
    DocumentAnchor,
    DocumentVersion,
    Fact,
    FactConflictGroup,
    FactConflictMember,
    FactEvidence,
    FactRevision,
    MetricDefinition,
    MissingItem,
    Project,
    ProjectDisclosure,
    ProjectMember,
    ProjectRequirementStatus,
    ProjectStandard,
    Report,
    ReportBlock,
    ReportBlockRevision,
    ReportSection,
    ReportTemplate,
    ReportTemplateSection,
    ReportTemplateVersion,
    SectionDisclosureMap,
    StandardVersion,
    TenantMembership,
    User,
)


def semantic_key(metric_code: str | None, name: str, period_start, period_end, entity_scope, dimensions: dict) -> str:
    metric = (metric_code or name).strip().upper().replace(" ", "_")
    period = f"{period_start or ''}:{period_end or ''}"
    dims = "|".join(f"{key}={dimensions[key]}" for key in sorted(dimensions))
    return f"{metric}|{period}|{entity_scope or 'UNSPECIFIED'}|{dims}"


async def audit(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    project_id: UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            project_id=project_id,
            before_data=before,
            after_data=after,
        )
    )


class IdentityService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def authenticate(self, email: str, password: str):
        user = await self.s.scalar(select(User).where(User.email == email.lower(), User.status == "ACTIVE"))
        if not user or not verify_password(password, user.password_hash):
            raise DomainError("AUTH_INVALID_CREDENTIALS", "Invalid credentials", 401)
        membership = await self.s.scalar(
            select(TenantMembership)
            .where(TenantMembership.user_id == user.id, TenantMembership.status == "ACTIVE")
            .order_by(TenantMembership.joined_at)
        )
        if not membership:
            raise DomainError("TENANT_MEMBERSHIP_REQUIRED", "No active tenant membership", 403)
        return user, membership


class TenantService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create_member(self, tenant_id: UUID, actor_user_id: UUID, data):
        existing = await self.s.scalar(select(User).where(User.email == str(data.email).lower()))
        if existing:
            user = existing
        else:
            user = User(
                email=str(data.email).lower(),
                name=data.name,
                password_hash=hash_password(data.password),
            )
            self.s.add(user)
            await self.s.flush()

        membership = await self.s.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user.id,
            )
        )
        if membership:
            raise Conflict("TENANT_MEMBER_ALREADY_EXISTS", "User already belongs to tenant")
        membership = TenantMembership(
            tenant_id=tenant_id,
            user_id=user.id,
            member_type=data.member_type,
            tenant_role=data.tenant_role,
            company_id=data.company_id,
        )
        self.s.add(membership)
        await self.s.flush()
        await audit(
            self.s,
            tenant_id,
            actor_user_id,
            "TENANT_MEMBER_ADD",
            "tenant_membership",
            membership.id,
        )
        return user, membership

    async def list_members(self, tenant_id: UUID):
        query = (
            select(TenantMembership, User)
            .join(User, TenantMembership.user_id == User.id)
            .where(TenantMembership.tenant_id == tenant_id, TenantMembership.status == "ACTIVE")
        )
        return (await self.s.execute(query)).all()


class ProjectAccess:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def membership(self, project_id: UUID, membership_id: UUID) -> ProjectMember | None:
        return await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.membership_id == membership_id,
                ProjectMember.status == "ACTIVE",
            )
        )

    async def require(self, project_id: UUID, membership_id: UUID, action: str) -> ProjectMember:
        project = await self.s.scalar(
            select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
        )
        if not project:
            raise NotFound("PROJECT_NOT_FOUND", "Project not found")
        pm = await self.membership(project_id, membership_id)
        if not pm or not allows(pm.project_role, action):
            raise NotFound("PROJECT_NOT_FOUND", "Project not found")
        return pm


class CompanyService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, tenant_id: UUID, user_id: UUID, data):
        obj = Company(tenant_id=tenant_id, **data.model_dump())
        self.s.add(obj)
        await self.s.flush()
        await audit(self.s, tenant_id, user_id, "COMPANY_CREATE", "company", obj.id, after={"name": obj.name})
        return obj

    async def list(self, tenant_id: UUID):
        return list(
            (
                await self.s.scalars(
                    select(Company)
                    .where(Company.tenant_id == tenant_id, Company.deleted_at.is_(None))
                    .order_by(Company.created_at.desc())
                )
            ).all()
        )

    async def get(self, tenant_id: UUID, company_id: UUID):
        obj = await self.s.scalar(
            select(Company).where(
                Company.id == company_id,
                Company.tenant_id == tenant_id,
                Company.deleted_at.is_(None),
            )
        )
        if not obj:
            raise NotFound("COMPANY_NOT_FOUND", "Company not found")
        return obj

    async def update(self, tenant_id: UUID, user_id: UUID, company_id: UUID, data):
        obj = await self.get(tenant_id, company_id)
        before = {"name": obj.name, "short_name": obj.short_name}
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await audit(
            self.s,
            tenant_id,
            user_id,
            "COMPANY_UPDATE",
            "company",
            obj.id,
            before=before,
            after=data.model_dump(exclude_unset=True),
        )
        return obj

    async def delete(self, tenant_id: UUID, user_id: UUID, company_id: UUID):
        obj = await self.get(tenant_id, company_id)
        active_projects = await self.s.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.company_id == company_id,
                Project.deleted_at.is_(None),
                Project.status == "ACTIVE",
            )
        )
        if active_projects:
            raise Conflict("COMPANY_HAS_ACTIVE_PROJECTS", "Company has active projects")
        obj.deleted_at = datetime.now(timezone.utc)
        await audit(self.s, tenant_id, user_id, "COMPANY_DELETE", "company", obj.id)
        return obj


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, tenant_id: UUID, user_id: UUID, membership_id: UUID, data):
        await CompanyService(self.s).get(tenant_id, data.company_id)
        if data.source_project_id:
            source = await self.s.scalar(
                select(Project).where(
                    Project.id == data.source_project_id,
                    Project.tenant_id == tenant_id,
                    Project.deleted_at.is_(None),
                )
            )
            if not source:
                raise NotFound("SOURCE_PROJECT_NOT_FOUND", "Source project not found")
        project = Project(
            tenant_id=tenant_id,
            owner_membership_id=membership_id,
            **data.model_dump(),
        )
        self.s.add(project)
        await self.s.flush()
        self.s.add(
            ProjectMember(
                tenant_id=tenant_id,
                project_id=project.id,
                membership_id=membership_id,
                project_role="OWNER",
            )
        )
        await audit(
            self.s,
            tenant_id,
            user_id,
            "PROJECT_CREATE",
            "project",
            project.id,
            project.id,
            after={"name": project.name},
        )
        return project

    async def list(self, tenant_id: UUID, membership_id: UUID):
        query = (
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                Project.tenant_id == tenant_id,
                Project.deleted_at.is_(None),
                ProjectMember.membership_id == membership_id,
                ProjectMember.status == "ACTIVE",
            )
            .order_by(Project.created_at.desc())
        )
        return list((await self.s.scalars(query)).all())

    async def get(self, tenant_id: UUID, project_id: UUID, membership_id: UUID):
        await ProjectAccess(self.s).require(project_id, membership_id, "VIEW_PROJECT")
        project = await self.s.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.tenant_id == tenant_id,
                Project.deleted_at.is_(None),
            )
        )
        if not project:
            raise NotFound("PROJECT_NOT_FOUND", "Project not found")
        return project

    async def update(self, tenant_id: UUID, user_id: UUID, membership_id: UUID, project_id: UUID, data):
        await ProjectAccess(self.s).require(project_id, membership_id, "EDIT_PROJECT")
        project = await self.get(tenant_id, project_id, membership_id)
        values = data.model_dump(exclude_unset=True)
        start = values.get("period_start", project.period_start)
        end = values.get("period_end", project.period_end)
        if start > end:
            raise DomainError("INVALID_PERIOD", "period_start must not exceed period_end", 422)
        for key, value in values.items():
            setattr(project, key, value)
        await audit(self.s, tenant_id, user_id, "PROJECT_UPDATE", "project", project.id, project.id, after=values)
        return project

    async def list_members(self, project_id: UUID, membership_id: UUID):
        await ProjectAccess(self.s).require(project_id, membership_id, "VIEW_PROJECT")
        return list(
            (
                await self.s.scalars(
                    select(ProjectMember)
                    .where(ProjectMember.project_id == project_id, ProjectMember.status == "ACTIVE")
                    .order_by(ProjectMember.joined_at)
                )
            ).all()
        )

    async def add_member(
        self,
        tenant_id: UUID,
        user_id: UUID,
        owner_membership_id: UUID,
        project_id: UUID,
        membership_id: UUID,
        role: str,
    ):
        await ProjectAccess(self.s).require(project_id, owner_membership_id, "MANAGE_MEMBERS")
        project = await self.s.get(Project, project_id)
        tm = await self.s.scalar(
            select(TenantMembership).where(
                TenantMembership.id == membership_id,
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.status == "ACTIVE",
            )
        )
        if not tm:
            raise NotFound("MEMBERSHIP_NOT_FOUND", "Membership not found")
        if tm.member_type == "CLIENT" and tm.company_id != project.company_id:
            raise Conflict("CLIENT_COMPANY_MISMATCH", "Client member must belong to project company")
        if role == "OWNER":
            raise Conflict("OWNER_TRANSFER_REQUIRED", "Use transfer-owner to change project owner")
        existing = await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.membership_id == membership_id,
            )
        )
        if existing and existing.status == "ACTIVE":
            raise Conflict("PROJECT_MEMBER_ALREADY_EXISTS", "Member already exists")
        if existing:
            existing.status = "ACTIVE"
            existing.project_role = role
            pm = existing
        else:
            pm = ProjectMember(
                tenant_id=tenant_id,
                project_id=project_id,
                membership_id=membership_id,
                project_role=role,
            )
            self.s.add(pm)
        await self.s.flush()
        await audit(self.s, tenant_id, user_id, "PROJECT_MEMBER_ADD", "project_member", pm.id, project_id)
        return pm

    async def update_member_role(
        self,
        tenant_id: UUID,
        user_id: UUID,
        actor_membership_id: UUID,
        project_id: UUID,
        project_member_id: UUID,
        role: str,
    ):
        await ProjectAccess(self.s).require(project_id, actor_membership_id, "MANAGE_MEMBERS")
        pm = await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.id == project_member_id,
                ProjectMember.project_id == project_id,
                ProjectMember.status == "ACTIVE",
            )
        )
        if not pm:
            raise NotFound("PROJECT_MEMBER_NOT_FOUND", "Project member not found")
        if pm.project_role == "OWNER":
            raise Conflict("OWNER_TRANSFER_REQUIRED", "Use transfer-owner to change project owner")
        before = {"project_role": pm.project_role}
        pm.project_role = role
        await audit(
            self.s,
            tenant_id,
            user_id,
            "PROJECT_MEMBER_UPDATE",
            "project_member",
            pm.id,
            project_id,
            before=before,
            after={"project_role": role},
        )
        return pm

    async def remove_member(
        self,
        tenant_id: UUID,
        user_id: UUID,
        actor_membership_id: UUID,
        project_id: UUID,
        project_member_id: UUID,
    ):
        await ProjectAccess(self.s).require(project_id, actor_membership_id, "MANAGE_MEMBERS")
        pm = await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.id == project_member_id,
                ProjectMember.project_id == project_id,
                ProjectMember.status == "ACTIVE",
            )
        )
        if not pm:
            raise NotFound("PROJECT_MEMBER_NOT_FOUND", "Project member not found")
        if pm.project_role == "OWNER":
            raise Conflict("LAST_PROJECT_OWNER", "Transfer ownership before removing owner")
        pm.status = "REMOVED"
        await audit(self.s, tenant_id, user_id, "PROJECT_MEMBER_REMOVE", "project_member", pm.id, project_id)
        return pm

    async def transfer_owner(
        self,
        tenant_id: UUID,
        user_id: UUID,
        actor_membership_id: UUID,
        project_id: UUID,
        new_membership_id: UUID,
    ):
        actor = await ProjectAccess(self.s).require(project_id, actor_membership_id, "MANAGE_MEMBERS")
        if actor.project_role != "OWNER":
            raise NotFound("PROJECT_NOT_FOUND", "Project not found")
        target = await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.membership_id == new_membership_id,
                ProjectMember.status == "ACTIVE",
            )
        )
        if not target:
            raise NotFound("PROJECT_MEMBER_NOT_FOUND", "New owner must already be an active project member")
        if target.project_role == "CLIENT_MEMBER":
            raise Conflict("CLIENT_CANNOT_OWN_PROJECT", "Client member cannot own project")
        project = await self.s.get(Project, project_id)
        old_owner = await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.membership_id == project.owner_membership_id,
                ProjectMember.status == "ACTIVE",
            )
        )
        old_owner.project_role = "EDITOR"
        target.project_role = "OWNER"
        project.owner_membership_id = new_membership_id
        await audit(
            self.s,
            tenant_id,
            user_id,
            "PROJECT_OWNER_TRANSFER",
            "project",
            project_id,
            project_id,
            before={"owner_membership_id": str(actor_membership_id)},
            after={"owner_membership_id": str(new_membership_id)},
        )
        return target


class FactService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def _validate_anchors(self, project_id: UUID, anchor_ids: list[UUID]) -> None:
        for anchor_id in anchor_ids:
            row = await self.s.execute(
                select(DocumentAnchor, Document)
                .join(DocumentVersion, DocumentAnchor.document_version_id == DocumentVersion.id)
                .join(Document, DocumentVersion.document_id == Document.id)
                .where(DocumentAnchor.id == anchor_id, DocumentAnchor.project_id == project_id)
            )
            pair = row.first()
            if not pair:
                raise NotFound("EVIDENCE_ANCHOR_NOT_FOUND", "Evidence anchor not found")
            _, document = pair
            if document.source_type != "EVIDENCE":
                raise Conflict("INVALID_FACT_EVIDENCE", "Only EVIDENCE documents may support client facts")

    async def create_candidate(self, tenant_id, project_id, user_id, data, status="PENDING", confidence=None):
        await self._validate_anchors(project_id, data.anchor_ids)
        sk = semantic_key(
            data.metric_code,
            data.name,
            data.period_start,
            data.period_end,
            data.entity_scope,
            data.dimensions,
        )
        fact = Fact(
            tenant_id=tenant_id,
            project_id=project_id,
            fact_type=data.fact_type,
            metric_definition_id=data.metric_definition_id,
            semantic_key=sk,
            name=data.name,
            value_type=data.value_type,
            number_value=data.number_value,
            text_value=data.text_value,
            boolean_value=data.boolean_value,
            date_value=data.date_value,
            json_value=data.json_value,
            raw_value=data.raw_value,
            unit=data.unit,
            period_start=data.period_start,
            period_end=data.period_end,
            entity_scope=data.entity_scope,
            dimensions=data.dimensions,
            status=status,
            source_type=data.source_type,
            confidence=confidence,
        )
        self.s.add(fact)
        await self.s.flush()
        for anchor_id in data.anchor_ids:
            self.s.add(FactEvidence(fact_id=fact.id, document_anchor_id=anchor_id, created_by=user_id))
        self.s.add(
            FactRevision(
                fact_id=fact.id,
                revision_no=1,
                snapshot=self._snapshot(fact),
                change_type="AI_CREATED" if data.source_type == "AI" else "HUMAN_CREATED",
                changed_by=user_id,
            )
        )
        await self._detect_conflict(fact)
        return fact

    @staticmethod
    def _snapshot(fact: Fact) -> dict:
        return {
            "name": fact.name,
            "value_type": fact.value_type,
            "number_value": str(fact.number_value) if fact.number_value is not None else None,
            "text_value": fact.text_value,
            "boolean_value": fact.boolean_value,
            "date_value": fact.date_value.isoformat() if fact.date_value else None,
            "json_value": fact.json_value,
            "raw_value": fact.raw_value,
            "unit": fact.unit,
            "period_start": fact.period_start.isoformat() if fact.period_start else None,
            "period_end": fact.period_end.isoformat() if fact.period_end else None,
            "entity_scope": fact.entity_scope,
            "dimensions": fact.dimensions,
            "status": fact.status,
            "semantic_key": fact.semantic_key,
        }

    async def _next_revision(self, fact_id: UUID) -> int:
        return (
            await self.s.scalar(
                select(func.max(FactRevision.revision_no)).where(FactRevision.fact_id == fact_id)
            )
            or 0
        ) + 1

    async def _detect_conflict(self, fact: Fact):
        peers = list(
            (
                await self.s.scalars(
                    select(Fact).where(
                        Fact.project_id == fact.project_id,
                        Fact.semantic_key == fact.semantic_key,
                        Fact.id != fact.id,
                        Fact.status.in_(["PENDING", "CONFIRMED", "CONFLICT"]),
                    )
                )
            ).all()
        )

        def value(item):
            return (
                item.number_value,
                item.text_value,
                item.boolean_value,
                item.date_value,
                str(item.json_value),
            )

        diffs = [peer for peer in peers if value(peer) != value(fact)]
        if not diffs:
            return
        group = await self.s.scalar(
            select(FactConflictGroup).where(
                FactConflictGroup.project_id == fact.project_id,
                FactConflictGroup.semantic_key == fact.semantic_key,
                FactConflictGroup.status == "OPEN",
            )
        )
        if not group:
            group = FactConflictGroup(
                tenant_id=fact.tenant_id,
                project_id=fact.project_id,
                semantic_key=fact.semantic_key,
                conflict_type="VALUE",
            )
            self.s.add(group)
            await self.s.flush()
        existing_ids = set(
            (
                await self.s.scalars(
                    select(FactConflictMember.fact_id).where(
                        FactConflictMember.conflict_group_id == group.id
                    )
                )
            ).all()
        )
        for peer in [*diffs, fact]:
            if peer.id not in existing_ids:
                self.s.add(FactConflictMember(conflict_group_id=group.id, fact_id=peer.id))
            peer.status = "CONFLICT"

    async def list(self, project_id):
        return list(
            (
                await self.s.scalars(
                    select(Fact)
                    .where(Fact.project_id == project_id, Fact.deleted_at.is_(None))
                    .order_by(Fact.created_at.desc())
                )
            ).all()
        )

    async def get(self, project_id, fact_id):
        fact = await self.s.scalar(
            select(Fact).where(
                Fact.id == fact_id,
                Fact.project_id == project_id,
                Fact.deleted_at.is_(None),
            )
        )
        if not fact:
            raise NotFound("FACT_NOT_FOUND", "Fact not found")
        return fact

    async def update(self, project_id: UUID, fact_id: UUID, user_id: UUID, data):
        fact = await self.get(project_id, fact_id)
        if fact.status == "CONFIRMED":
            raise Conflict("CONFIRMED_FACT_IMMUTABLE", "Confirmed fact must be revised by rejecting or creating a new fact")
        values = data.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(fact, key, value)
        if any(key in values for key in {"name", "period_start", "period_end", "entity_scope", "dimensions"}):
            fact.semantic_key = semantic_key(
                None,
                fact.name,
                fact.period_start,
                fact.period_end,
                fact.entity_scope,
                fact.dimensions,
            )
        rev = await self._next_revision(fact.id)
        self.s.add(
            FactRevision(
                fact_id=fact.id,
                revision_no=rev,
                snapshot=self._snapshot(fact),
                change_type="HUMAN_EDIT",
                changed_by=user_id,
            )
        )
        await self._detect_conflict(fact)
        return fact

    async def confirm(self, project_id, fact_id, user_id):
        fact = await self.get(project_id, fact_id)
        if fact.status == "REJECTED":
            raise Conflict("FACT_REJECTED", "Rejected fact cannot be confirmed")
        if fact.status == "CONFLICT":
            raise Conflict(
                "FACT_CONFLICT_UNRESOLVED",
                "Conflicting fact must be resolved through its conflict group",
            )
        ev_count = await self.s.scalar(
            select(func.count()).select_from(FactEvidence).where(FactEvidence.fact_id == fact_id)
        )
        if not ev_count and fact.source_type != "HUMAN":
            raise Conflict("FACT_NOT_CONFIRMABLE", "AI fact cannot be confirmed without evidence")
        fact.status = "CONFIRMED"
        fact.confirmed_by = user_id
        fact.confirmed_at = datetime.now(timezone.utc)
        rev = await self._next_revision(fact.id)
        self.s.add(
            FactRevision(
                fact_id=fact.id,
                revision_no=rev,
                snapshot=self._snapshot(fact),
                change_type="CONFIRMED",
                changed_by=user_id,
            )
        )
        return fact

    async def reject(self, project_id: UUID, fact_id: UUID, user_id: UUID, reason: str):
        fact = await self.get(project_id, fact_id)
        if fact.status == "CONFLICT":
            raise Conflict(
                "FACT_CONFLICT_UNRESOLVED",
                "Conflicting fact must be resolved through its conflict group",
            )
        fact.status = "REJECTED"
        fact.confirmed_by = None
        fact.confirmed_at = None
        rev = await self._next_revision(fact.id)
        snapshot = self._snapshot(fact)
        snapshot["reason"] = reason
        self.s.add(
            FactRevision(
                fact_id=fact.id,
                revision_no=rev,
                snapshot=snapshot,
                change_type="REJECTED",
                changed_by=user_id,
            )
        )
        return fact


class TaskService:
    def __init__(self, session: AsyncSession):
        self.s = session

    @staticmethod
    def _same_submission(task: AITask, project_id, task_type, target_type, target_id, input_json) -> bool:
        return (
            task.project_id == project_id
            and task.task_type == task_type
            and task.target_type == target_type
            and task.target_id == target_id
            and (task.input_json or {}) == (input_json or {})
        )

    async def create(
        self,
        tenant_id,
        project_id,
        user_id,
        task_type,
        target_type=None,
        target_id=None,
        input_json=None,
        idempotency_key=None,
    ):
        values = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "created_by": user_id,
            "task_type": task_type,
            "target_type": target_type,
            "target_id": target_id,
            "input_json": input_json or {},
            "idempotency_key": idempotency_key,
        }
        if not idempotency_key:
            task = AITask(**values)
            self.s.add(task)
            await self.s.flush()
            return task

        statement = (
            pg_insert(AITask)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_ai_task_principal_idempotency")
            .returning(AITask.id)
        )
        inserted_id = await self.s.scalar(statement)
        if inserted_id:
            return await self.s.get(AITask, inserted_id)

        existing = await self.s.scalar(
            select(AITask).where(
                AITask.tenant_id == tenant_id,
                AITask.created_by == user_id,
                AITask.idempotency_key == idempotency_key,
            )
        )
        if not existing:
            raise Conflict("IDEMPOTENCY_CONFLICT", "Unable to resolve idempotent submission")
        if not self._same_submission(
            existing, project_id, task_type, target_type, target_id, input_json
        ):
            raise Conflict(
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency-Key was already used for a different request",
            )
        return existing

    async def list(self, tenant_id: UUID, project_id: UUID | None = None):
        query = select(AITask).where(AITask.tenant_id == tenant_id)
        if project_id:
            query = query.where(AITask.project_id == project_id)
        return list((await self.s.scalars(query.order_by(AITask.created_at.desc()))).all())

    async def retry(self, task: AITask):
        if task.status not in {"FAILED", "CANCELLED"}:
            raise Conflict("TASK_NOT_RETRYABLE", "Only failed or cancelled tasks may be retried")
        task.status = "PENDING"
        task.progress = 0
        task.stage = "queued"
        task.error_code = None
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        return task

    async def cancel(self, task: AITask):
        if task.status in {"SUCCESS", "CANCELLED"}:
            raise Conflict("TASK_NOT_CANCELLABLE", "Task is already terminal")
        task.status = "CANCELLED"
        task.stage = "cancelled"
        task.completed_at = datetime.now(timezone.utc)
        return task

    async def recover_stale(self, cutoff: datetime) -> int:
        tasks = list(
            (
                await self.s.scalars(
                    select(AITask).where(
                        AITask.status == "RUNNING",
                        AITask.started_at.is_not(None),
                        AITask.started_at < cutoff,
                    )
                )
            ).all()
        )
        for task in tasks:
            task.status = "FAILED"
            task.stage = "recovered_stale"
            task.error_code = "TASK_STALE_RECOVERED"
            task.error_message = "Worker execution exceeded stale-task threshold"
            task.completed_at = datetime.now(timezone.utc)
        return len(tasks)


class StandardService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def attach_to_project(self, project_id: UUID, version_id: UUID):
        version = await self.s.get(StandardVersion, version_id)
        if not version or version.status != "ACTIVE":
            raise NotFound("STANDARD_VERSION_NOT_FOUND", "Standard version not found")
        exists = await self.s.scalar(
            select(ProjectStandard).where(
                ProjectStandard.project_id == project_id,
                ProjectStandard.standard_version_id == version_id,
            )
        )
        if exists:
            return exists
        ps = ProjectStandard(project_id=project_id, standard_version_id=version_id, is_primary=True)
        self.s.add(ps)
        await self.s.flush()
        disclosures = list(
            (
                await self.s.scalars(
                    select(Disclosure).where(Disclosure.standard_version_id == version_id)
                )
            ).all()
        )
        for disclosure in disclosures:
            if not await self.s.scalar(
                select(ProjectDisclosure).where(
                    ProjectDisclosure.project_id == project_id,
                    ProjectDisclosure.disclosure_id == disclosure.id,
                )
            ):
                self.s.add(ProjectDisclosure(project_id=project_id, disclosure_id=disclosure.id))
            requirements = list(
                (
                    await self.s.scalars(
                        select(DisclosureRequirement).where(
                            DisclosureRequirement.disclosure_id == disclosure.id
                        )
                    )
                ).all()
            )
            for requirement in requirements:
                if not await self.s.scalar(
                    select(ProjectRequirementStatus).where(
                        ProjectRequirementStatus.project_id == project_id,
                        ProjectRequirementStatus.requirement_id == requirement.id,
                    )
                ):
                    self.s.add(
                        ProjectRequirementStatus(
                            project_id=project_id,
                            requirement_id=requirement.id,
                            status="MISSING",
                        )
                    )
        return ps

    async def update_project_disclosure(self, project_id: UUID, project_disclosure_id: UUID, data):
        project_disclosure = await self.s.scalar(
            select(ProjectDisclosure).where(
                ProjectDisclosure.id == project_disclosure_id,
                ProjectDisclosure.project_id == project_id,
            )
        )
        if not project_disclosure:
            raise NotFound("PROJECT_DISCLOSURE_NOT_FOUND", "Project disclosure not found")

        values = data.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(project_disclosure, key, value)

        if "applicability" in values:
            requirements = list(
                (
                    await self.s.scalars(
                        select(ProjectRequirementStatus)
                        .join(
                            DisclosureRequirement,
                            ProjectRequirementStatus.requirement_id == DisclosureRequirement.id,
                        )
                        .where(
                            ProjectRequirementStatus.project_id == project_id,
                            DisclosureRequirement.disclosure_id == project_disclosure.disclosure_id,
                        )
                    )
                ).all()
            )
            if project_disclosure.applicability == "NOT_APPLICABLE":
                for requirement_status in requirements:
                    requirement_status.status = "NOT_APPLICABLE"
                    requirement_status.reason = "Disclosure marked not applicable by project user"
                await self.s.execute(
                    delete(DisclosureFactMap).where(
                        DisclosureFactMap.project_id == project_id,
                        DisclosureFactMap.disclosure_id == project_disclosure.disclosure_id,
                        DisclosureFactMap.source_type == "RULE",
                    )
                )
            else:
                await self.map_confirmed_facts(project_id)

        return project_disclosure

    async def map_confirmed_facts(self, project_id: UUID):
        await self.s.execute(
            delete(DisclosureFactMap).where(
                DisclosureFactMap.project_id == project_id,
                DisclosureFactMap.source_type == "RULE",
            )
        )
        facts = list(
            (
                await self.s.scalars(
                    select(Fact).where(Fact.project_id == project_id, Fact.status == "CONFIRMED")
                )
            ).all()
        )
        metric_ids = {fact.metric_definition_id for fact in facts if fact.metric_definition_id}
        metrics = {}
        if metric_ids:
            metrics = {
                metric.id: metric
                for metric in (
                    await self.s.scalars(
                        select(MetricDefinition).where(MetricDefinition.id.in_(metric_ids))
                    )
                ).all()
            }
        project_disclosures = list(
            (
                await self.s.scalars(
                    select(ProjectDisclosure).where(ProjectDisclosure.project_id == project_id)
                )
            ).all()
        )
        created = 0
        for pd in project_disclosures:
            requirements = list(
                (
                    await self.s.scalars(
                        select(DisclosureRequirement).where(
                            DisclosureRequirement.disclosure_id == pd.disclosure_id
                        )
                    )
                ).all()
            )
            if pd.applicability == "NOT_APPLICABLE":
                for requirement in requirements:
                    status = await self.s.scalar(
                        select(ProjectRequirementStatus).where(
                            ProjectRequirementStatus.project_id == project_id,
                            ProjectRequirementStatus.requirement_id == requirement.id,
                        )
                    )
                    if status:
                        status.status = "NOT_APPLICABLE"
                        status.reason = "Disclosure marked not applicable by project user"
                continue

            covered = 0
            for requirement in requirements:
                codes = set((requirement.required_data_json or {}).get("metric_codes", []))
                matching = [
                    fact
                    for fact in facts
                    if fact.metric_definition_id
                    and metrics.get(fact.metric_definition_id)
                    and metrics[fact.metric_definition_id].code in codes
                ]
                status = await self.s.scalar(
                    select(ProjectRequirementStatus).where(
                        ProjectRequirementStatus.project_id == project_id,
                        ProjectRequirementStatus.requirement_id == requirement.id,
                    )
                )
                if matching:
                    covered += 1
                    if status:
                        status.status = "COVERED"
                        status.reason = "Matched confirmed facts"
                    for fact in matching:
                        if not await self.s.scalar(
                            select(DisclosureFactMap).where(
                                DisclosureFactMap.project_id == project_id,
                                DisclosureFactMap.disclosure_id == pd.disclosure_id,
                                DisclosureFactMap.fact_id == fact.id,
                            )
                        ):
                            self.s.add(
                                DisclosureFactMap(
                                    project_id=project_id,
                                    disclosure_id=pd.disclosure_id,
                                    fact_id=fact.id,
                                    mapping_type="DIRECT",
                                    source_type="RULE",
                                    confirmed=True,
                                )
                            )
                            created += 1
                elif status:
                    status.status = "MISSING"
                    status.reason = "No confirmed fact matched required metric"
            pd.coverage_status = (
                "COVERED"
                if requirements and covered == len(requirements)
                else "PARTIAL"
                if covered
                else "MISSING"
            )
        return created

    async def generate_missing_items(self, tenant_id: UUID, project_id: UUID):
        rows = (
            await self.s.execute(
                select(ProjectRequirementStatus, DisclosureRequirement)
                .join(
                    DisclosureRequirement,
                    ProjectRequirementStatus.requirement_id == DisclosureRequirement.id,
                )
                .where(
                    ProjectRequirementStatus.project_id == project_id,
                    ProjectRequirementStatus.status == "MISSING",
                )
            )
        ).all()
        created = []
        for _, requirement in rows:
            disclosure = await self.s.get(Disclosure, requirement.disclosure_id)
            existing = await self.s.scalar(
                select(MissingItem).where(
                    MissingItem.project_id == project_id,
                    MissingItem.requirement_id == requirement.id,
                    MissingItem.status.in_(["MISSING", "REQUESTED", "RECEIVED"]),
                )
            )
            if existing:
                continue
            item = MissingItem(
                tenant_id=tenant_id,
                project_id=project_id,
                disclosure_id=disclosure.id,
                requirement_id=requirement.id,
                name=f"{disclosure.code} {requirement.requirement_code}",
                description=requirement.content,
                missing_type="DATA",
                suggested_material="Please provide evidence/data supporting this disclosure requirement.",
            )
            self.s.add(item)
            created.append(item)
        await self.s.flush()
        return created


class TemplateService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, tenant_id: UUID, user_id: UUID, data):
        template = ReportTemplate(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            template_type="TENANT",
            created_by=user_id,
        )
        self.s.add(template)
        await self.s.flush()
        return template

    async def list(self, tenant_id: UUID):
        return list(
            (
                await self.s.scalars(
                    select(ReportTemplate)
                    .where(
                        (ReportTemplate.tenant_id == tenant_id) | (ReportTemplate.tenant_id.is_(None)),
                        ReportTemplate.status == "ACTIVE",
                    )
                    .order_by(ReportTemplate.created_at.desc())
                )
            ).all()
        )

    async def create_version(self, template: ReportTemplate, user_id: UUID, data):
        next_no = (
            await self.s.scalar(
                select(func.max(ReportTemplateVersion.version_no)).where(
                    ReportTemplateVersion.template_id == template.id
                )
            )
            or 0
        ) + 1
        version = ReportTemplateVersion(
            template_id=template.id,
            version_no=next_no,
            source_type=data.source_type,
            source_document_id=data.source_document_id,
            created_by=user_id,
        )
        self.s.add(version)
        await self.s.flush()
        return version


class ReportService:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create_report(self, tenant_id, project_id, user_id, title, language="zh-CN", template_version_id=None):
        report = Report(
            tenant_id=tenant_id,
            project_id=project_id,
            title=title,
            language=language,
            template_version_id=template_version_id,
            created_by=user_id,
        )
        self.s.add(report)
        await self.s.flush()
        if template_version_id:
            sections = list(
                (
                    await self.s.scalars(
                        select(ReportTemplateSection)
                        .where(ReportTemplateSection.template_version_id == template_version_id)
                        .order_by(ReportTemplateSection.level, ReportTemplateSection.sort_order)
                    )
                ).all()
            )
            mapping = {}
            for template_section in sections:
                section = ReportSection(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    report_id=report.id,
                    parent_id=mapping.get(template_section.parent_id),
                    source_template_section_id=template_section.id,
                    title=template_section.title,
                    description=template_section.description,
                    level=template_section.level,
                    sort_order=template_section.sort_order,
                )
                self.s.add(section)
                await self.s.flush()
                mapping[template_section.id] = section.id
        return report

    async def blocks(self, section_id):
        return list(
            (
                await self.s.scalars(
                    select(ReportBlock)
                    .where(ReportBlock.section_id == section_id, ReportBlock.deleted_at.is_(None))
                    .order_by(ReportBlock.sort_order)
                )
            ).all()
        )

    async def create_block(self, tenant_id: UUID, project_id: UUID, section_id: UUID, user_id: UUID, data):
        block = ReportBlock(
            tenant_id=tenant_id,
            project_id=project_id,
            section_id=section_id,
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
                created_by=user_id,
            )
        )
        return block

    async def update_block(self, block: ReportBlock, user_id: UUID, data):
        next_no = block.current_revision_no + 1
        block.current_content = data.content
        block.current_content_json = data.content_json
        block.current_revision_no = next_no
        block.source_type = "HUMAN"
        block.updated_by = user_id
        self.s.add(
            ReportBlockRevision(
                block_id=block.id,
                revision_no=next_no,
                content=data.content,
                content_json=data.content_json,
                source_type="HUMAN",
                change_reason=data.change_reason,
                created_by=user_id,
            )
        )
        return block

    async def restore_block(self, block: ReportBlock, revision: ReportBlockRevision, user_id: UUID):
        next_no = block.current_revision_no + 1
        block.current_content = revision.content
        block.current_content_json = revision.content_json
        block.current_revision_no = next_no
        block.source_type = "HUMAN"
        block.updated_by = user_id
        self.s.add(
            ReportBlockRevision(
                block_id=block.id,
                revision_no=next_no,
                content=revision.content,
                content_json=revision.content_json,
                source_type="HUMAN",
                change_reason=f"Restored from revision {revision.revision_no}",
                created_by=user_id,
            )
        )
        return block

    async def verify_claim(self, claim: Claim) -> tuple[str, list[str]]:
        citations = list(
            (await self.s.scalars(select(Citation).where(Citation.claim_id == claim.id, Citation.status == "ACTIVE"))).all()
        )
        reasons: list[str] = []
        if not citations:
            reasons.append("NO_CITATION")
        valid_evidence = False
        for citation in citations:
            if not citation.fact_id:
                reasons.append("CITATION_WITHOUT_FACT")
                continue
            fact = await self.s.get(Fact, citation.fact_id)
            if not fact or fact.status != "CONFIRMED":
                reasons.append("FACT_NOT_CONFIRMED")
                continue
            if not citation.fact_evidence_id or not citation.document_anchor_id:
                reasons.append("FACT_WITHOUT_EVIDENCE")
                continue
            evidence = await self.s.get(FactEvidence, citation.fact_evidence_id)
            anchor = await self.s.get(DocumentAnchor, citation.document_anchor_id)
            if not evidence or evidence.fact_id != fact.id or evidence.document_anchor_id != citation.document_anchor_id:
                reasons.append("EVIDENCE_LINK_INVALID")
                continue
            if not anchor or anchor.project_id != fact.project_id:
                reasons.append("ANCHOR_PROJECT_MISMATCH")
                continue
            version = await self.s.get(DocumentVersion, anchor.document_version_id)
            document = await self.s.get(Document, version.document_id) if version else None
            if not document or document.source_type != "EVIDENCE":
                reasons.append("NON_EVIDENCE_SOURCE")
                continue
            valid_evidence = True
        claim.verification_status = "VERIFIED" if valid_evidence and not reasons else "UNVERIFIED"
        return claim.verification_status, sorted(set(reasons))

    async def consistency(self, report_id):
        sections = list(
            (await self.s.scalars(select(ReportSection).where(ReportSection.report_id == report_id))).all()
        )
        section_ids = [section.id for section in sections]
        if not section_ids:
            return []
        blocks = list(
            (
                await self.s.scalars(
                    select(ReportBlock).where(
                        ReportBlock.section_id.in_(section_ids),
                        ReportBlock.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        block_ids = [block.id for block in blocks]
        if not block_ids:
            return []
        revisions = list(
            (
                await self.s.scalars(
                    select(ReportBlockRevision).where(
                        ReportBlockRevision.block_id.in_(block_ids)
                    )
                )
            ).all()
        )
        revision_ids = [revision.id for revision in revisions]
        claims = (
            list(
                (
                    await self.s.scalars(
                        select(Claim).where(Claim.block_revision_id.in_(revision_ids))
                    )
                ).all()
            )
            if revision_ids
            else []
        )
        issues = []
        for claim in claims:
            if claim.risk_level == "HIGH" and claim.verification_status != "VERIFIED":
                issues.append(
                    {
                        "claim_id": str(claim.id),
                        "type": "UNVERIFIED_HIGH_RISK",
                        "severity": "HIGH",
                        "text": claim.claim_text,
                    }
                )
        return issues
