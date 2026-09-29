from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, DomainError, NotFound
from app.modules.models import (
    AuditLog,
    Company,
    Project,
    ProjectMember,
    TenantMembership,
    User,
)
from app.modules.services import audit


VALID_PROJECT_ROLES = {"OWNER", "EDITOR", "REVIEWER", "CLIENT_MEMBER"}


class MembershipLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, tenant_id: UUID, membership_id: UUID) -> TenantMembership:
        item = await self.s.scalar(
            select(TenantMembership).where(
                TenantMembership.id == membership_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        if not item:
            raise NotFound("MEMBERSHIP_NOT_FOUND", "Membership not found")
        return item

    async def update(self, tenant_id: UUID, actor_id: UUID, membership_id: UUID, data):
        item = await self.get(tenant_id, membership_id)
        values = data.model_dump(exclude_unset=True)
        if values.get("member_type") == "CLIENT" and not values.get("company_id", item.company_id):
            raise DomainError("CLIENT_COMPANY_REQUIRED", "Client member requires company_id", 422)
        if values.get("company_id"):
            company = await self.s.scalar(
                select(Company).where(
                    Company.id == values["company_id"],
                    Company.tenant_id == tenant_id,
                    Company.deleted_at.is_(None),
                )
            )
            if not company:
                raise NotFound("COMPANY_NOT_FOUND", "Company not found")
        for key, value in values.items():
            setattr(item, key, value)
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "TENANT_MEMBER_UPDATE",
            "tenant_membership",
            item.id,
            after=values,
        )
        return item

    async def deactivate(self, tenant_id: UUID, actor_id: UUID, membership_id: UUID):
        item = await self.get(tenant_id, membership_id)
        if item.tenant_role == "ADMIN" and item.status == "ACTIVE":
            count = await self.s.scalar(
                select(func.count())
                .select_from(TenantMembership)
                .where(
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.tenant_role == "ADMIN",
                    TenantMembership.status == "ACTIVE",
                )
            )
            if count <= 1:
                raise Conflict("LAST_TENANT_ADMIN", "Cannot deactivate the last tenant admin")
        item.status = "DISABLED"
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "TENANT_MEMBER_DEACTIVATE",
            "tenant_membership",
            item.id,
        )
        return item


class CompanyLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, tenant_id: UUID, company_id: UUID) -> Company:
        item = await self.s.scalar(
            select(Company).where(
                Company.id == company_id,
                Company.tenant_id == tenant_id,
                Company.deleted_at.is_(None),
            )
        )
        if not item:
            raise NotFound("COMPANY_NOT_FOUND", "Company not found")
        return item

    async def update(self, tenant_id: UUID, actor_id: UUID, company_id: UUID, data):
        item = await self.get(tenant_id, company_id)
        values = data.model_dump(exclude_unset=True)
        before = {"name": item.name}
        for key, value in values.items():
            setattr(item, key, value)
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "COMPANY_UPDATE",
            "company",
            item.id,
            before=before,
            after=values,
        )
        return item

    async def delete(self, tenant_id: UUID, actor_id: UUID, company_id: UUID):
        item = await self.get(tenant_id, company_id)
        active = await self.s.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.company_id == company_id,
                Project.tenant_id == tenant_id,
                Project.deleted_at.is_(None),
                Project.status == "ACTIVE",
            )
        )
        if active:
            raise Conflict("COMPANY_HAS_ACTIVE_PROJECTS", "Company has active projects")
        item.deleted_at = datetime.now(timezone.utc)
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "COMPANY_DELETE",
            "company",
            item.id,
        )


class ProjectLifecycle:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def project(self, tenant_id: UUID, project_id: UUID) -> Project:
        item = await self.s.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.tenant_id == tenant_id,
                Project.deleted_at.is_(None),
            )
        )
        if not item:
            raise NotFound("PROJECT_NOT_FOUND", "Project not found")
        return item

    async def update(self, tenant_id: UUID, actor_id: UUID, project_id: UUID, data):
        item = await self.project(tenant_id, project_id)
        values = data.model_dump(exclude_unset=True)
        start = values.get("period_start", item.period_start)
        end = values.get("period_end", item.period_end)
        if start > end:
            raise DomainError("INVALID_PERIOD", "period_start must not exceed period_end", 422)
        for key, value in values.items():
            setattr(item, key, value)
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "PROJECT_UPDATE",
            "project",
            item.id,
            item.id,
            after=values,
        )
        return item

    async def delete(self, tenant_id: UUID, actor_id: UUID, project_id: UUID):
        item = await self.project(tenant_id, project_id)
        item.deleted_at = datetime.now(timezone.utc)
        item.status = "ARCHIVED"
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "PROJECT_DELETE",
            "project",
            item.id,
            item.id,
        )

    async def members(self, project_id: UUID):
        query = (
            select(ProjectMember, TenantMembership, User)
            .join(TenantMembership, ProjectMember.membership_id == TenantMembership.id)
            .join(User, TenantMembership.user_id == User.id)
            .where(ProjectMember.project_id == project_id, ProjectMember.status == "ACTIVE")
        )
        return (await self.s.execute(query)).all()

    async def _validate_role(self, project: Project, membership: TenantMembership, role: str):
        if role not in VALID_PROJECT_ROLES:
            raise DomainError("INVALID_PROJECT_ROLE", "Invalid project role", 422)
        if membership.member_type == "CLIENT":
            if membership.company_id != project.company_id:
                raise DomainError(
                    "CLIENT_COMPANY_MISMATCH",
                    "Client member can only join projects for its own company",
                    422,
                )
            if role != "CLIENT_MEMBER":
                raise DomainError(
                    "CLIENT_ROLE_REQUIRED",
                    "Client tenant memberships require CLIENT_MEMBER project role",
                    422,
                )
        elif role == "CLIENT_MEMBER":
            raise DomainError(
                "CLIENT_ROLE_INVALID",
                "Internal tenant memberships cannot use CLIENT_MEMBER role",
                422,
            )

    async def change_role(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        project_member_id: UUID,
        role: str,
    ):
        project = await self.project(tenant_id, project_id)
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
            raise Conflict("PROJECT_OWNER_TRANSFER_REQUIRED", "Use owner transfer endpoint")
        membership = await self.s.get(TenantMembership, pm.membership_id)
        await self._validate_role(project, membership, role)
        pm.project_role = role
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "PROJECT_MEMBER_UPDATE",
            "project_member",
            pm.id,
            project_id,
            after={"project_role": role},
        )
        return pm

    async def remove(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        project_member_id: UUID,
    ):
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
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "PROJECT_MEMBER_REMOVE",
            "project_member",
            pm.id,
            project_id,
        )

    async def transfer_owner(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        membership_id: UUID,
    ):
        project = await self.project(tenant_id, project_id)
        target = await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.membership_id == membership_id,
                ProjectMember.status == "ACTIVE",
            )
        )
        if not target:
            raise NotFound("PROJECT_MEMBER_NOT_FOUND", "Target must already be a project member")
        membership = await self.s.get(TenantMembership, membership_id)
        if not membership or membership.member_type != "INTERNAL":
            raise DomainError("OWNER_MUST_BE_INTERNAL", "Project owner must be an internal member", 422)
        current = await self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.membership_id == project.owner_membership_id,
                ProjectMember.status == "ACTIVE",
            )
        )
        if current and current.id != target.id:
            current.project_role = "EDITOR"
        target.project_role = "OWNER"
        project.owner_membership_id = membership_id
        await audit(
            self.s,
            tenant_id,
            actor_id,
            "PROJECT_OWNER_TRANSFER",
            "project",
            project.id,
            project.id,
            after={"owner_membership_id": str(membership_id)},
        )
        return target


async def list_audit_logs(session: AsyncSession, tenant_id: UUID, project_id: UUID, limit: int):
    query = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id, AuditLog.project_id == project_id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    return list((await session.scalars(query)).all())
