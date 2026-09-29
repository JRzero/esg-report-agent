from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_context
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import Forbidden
from app.modules.foundation_ext import (
    CompanyLifecycle,
    MembershipLifecycle,
    ProjectLifecycle,
    list_audit_logs,
)
from app.modules.schemas import (
    CompanyRead,
    CompanyUpdate,
    MembershipUpdate,
    ProjectMemberRead,
    ProjectMemberUpdate,
    ProjectRead,
    ProjectUpdate,
    TransferOwnerRequest,
)
from app.modules.services import ProjectAccess

router = APIRouter()


@router.post("/auth/logout", status_code=204, tags=["Auth"])
async def logout():
    # JWT access tokens are intentionally stateless in MVP. Logout invalidates the
    # client session by discarding access/refresh tokens; future SSO can add revocation.
    return Response(status_code=204)


@router.patch("/tenant/members/{membership_id}", tags=["Tenants"])
async def update_tenant_member(
    membership_id: UUID,
    body: MembershipUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    item = await MembershipLifecycle(db).update(ctx.tenant_id, ctx.user_id, membership_id, body)
    await db.commit()
    return item


@router.delete("/tenant/members/{membership_id}", status_code=204, tags=["Tenants"])
async def deactivate_tenant_member(
    membership_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    await MembershipLifecycle(db).deactivate(ctx.tenant_id, ctx.user_id, membership_id)
    await db.commit()
    return Response(status_code=204)


@router.get("/companies/{company_id}", response_model=CompanyRead, tags=["Companies"])
async def get_company(
    company_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.member_type == "CLIENT" and ctx.company_id != company_id:
        from app.core.errors import NotFound
        raise NotFound("COMPANY_NOT_FOUND", "Company not found")
    return await CompanyLifecycle(db).get(ctx.tenant_id, company_id)


@router.patch("/companies/{company_id}", response_model=CompanyRead, tags=["Companies"])
async def update_company(
    company_id: UUID,
    body: CompanyUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    item = await CompanyLifecycle(db).update(ctx.tenant_id, ctx.user_id, company_id, body)
    await db.commit()
    return item


@router.delete("/companies/{company_id}", status_code=204, tags=["Companies"])
async def delete_company(
    company_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.tenant_role != "ADMIN":
        raise Forbidden("TENANT_ADMIN_REQUIRED", "Tenant admin required")
    await CompanyLifecycle(db).delete(ctx.tenant_id, ctx.user_id, company_id)
    await db.commit()
    return Response(status_code=204)


@router.patch("/projects/{project_id}", response_model=ProjectRead, tags=["Projects"])
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "EDIT_PROJECT")
    item = await ProjectLifecycle(db).update(ctx.tenant_id, ctx.user_id, project_id, body)
    await db.commit()
    return item


@router.delete("/projects/{project_id}", status_code=204, tags=["Projects"])
async def delete_project(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "MANAGE_MEMBERS")
    await ProjectLifecycle(db).delete(ctx.tenant_id, ctx.user_id, project_id)
    await db.commit()
    return Response(status_code=204)


@router.get("/projects/{project_id}/members", tags=["Project Members"])
async def list_project_members(
    project_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    rows = await ProjectLifecycle(db).members(project_id)
    return [
        {
            "project_member": {
                "id": pm.id,
                "membership_id": pm.membership_id,
                "project_role": pm.project_role,
                "status": pm.status,
            },
            "membership": {
                "id": membership.id,
                "member_type": membership.member_type,
                "tenant_role": membership.tenant_role,
                "company_id": membership.company_id,
            },
            "user": {"id": user.id, "email": user.email, "name": user.name},
        }
        for pm, membership, user in rows
    ]


@router.patch(
    "/projects/{project_id}/members/{project_member_id}",
    response_model=ProjectMemberRead,
    tags=["Project Members"],
)
async def update_project_member(
    project_id: UUID,
    project_member_id: UUID,
    body: ProjectMemberUpdate,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "MANAGE_MEMBERS")
    item = await ProjectLifecycle(db).change_role(
        ctx.tenant_id,
        ctx.user_id,
        project_id,
        project_member_id,
        body.project_role,
    )
    await db.commit()
    return item


@router.delete(
    "/projects/{project_id}/members/{project_member_id}",
    status_code=204,
    tags=["Project Members"],
)
async def remove_project_member(
    project_id: UUID,
    project_member_id: UUID,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "MANAGE_MEMBERS")
    await ProjectLifecycle(db).remove(
        ctx.tenant_id, ctx.user_id, project_id, project_member_id
    )
    await db.commit()
    return Response(status_code=204)


@router.post(
    "/projects/{project_id}/transfer-owner",
    response_model=ProjectMemberRead,
    tags=["Project Members"],
)
async def transfer_project_owner(
    project_id: UUID,
    body: TransferOwnerRequest,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "MANAGE_MEMBERS")
    item = await ProjectLifecycle(db).transfer_owner(
        ctx.tenant_id, ctx.user_id, project_id, body.membership_id
    )
    await db.commit()
    return item


@router.get("/projects/{project_id}/audit-logs", tags=["Audit"])
async def project_audit_logs(
    project_id: UUID,
    limit: int = 100,
    ctx: RequestContext = Depends(current_context),
    db: AsyncSession = Depends(get_db),
):
    await ProjectAccess(db).require(project_id, ctx.membership_id, "VIEW_PROJECT")
    return await list_audit_logs(db, ctx.tenant_id, project_id, limit)
