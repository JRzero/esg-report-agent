import os
from datetime import date

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, get_engine
from app.core.security import hash_password
from app.main import app
from app.modules.models import (
    Company,
    Project,
    ProjectMember,
    Tenant,
    TenantMembership,
    User,
)
from app.modules import models as _models  # noqa: F401


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    engine = get_engine()
    async with engine.begin() as connection:
        tables = [f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables)]
        if tables:
            await connection.execute(
                text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")
            )
    yield


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as api:
        yield api


@pytest_asyncio.fixture
async def seeded():
    async with SessionLocal() as session:
        tenant = Tenant(name="Acceptance Consulting", code="acceptance")
        session.add(tenant)
        await session.flush()

        admin = User(
            email="admin@example.com",
            name="Admin",
            password_hash=hash_password("admin12345"),
        )
        editor = User(
            email="editor@example.com",
            name="Editor",
            password_hash=hash_password("editor12345"),
        )
        client_user = User(
            email="client@example.com",
            name="Client",
            password_hash=hash_password("client12345"),
        )
        session.add_all([admin, editor, client_user])
        await session.flush()

        company = Company(tenant_id=tenant.id, name="Example Manufacturing", country="CN")
        other_company = Company(tenant_id=tenant.id, name="Other Manufacturing", country="CN")
        session.add_all([company, other_company])
        await session.flush()

        admin_membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=admin.id,
            tenant_role="ADMIN",
            member_type="INTERNAL",
        )
        editor_membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=editor.id,
            tenant_role="MEMBER",
            member_type="INTERNAL",
        )
        client_membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=client_user.id,
            tenant_role="MEMBER",
            member_type="CLIENT",
            company_id=company.id,
        )
        session.add_all([admin_membership, editor_membership, client_membership])
        await session.flush()

        project = Project(
            tenant_id=tenant.id,
            company_id=company.id,
            name="Example 2026 ESG Report",
            report_year=2026,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            owner_membership_id=admin_membership.id,
        )
        other_project = Project(
            tenant_id=tenant.id,
            company_id=other_company.id,
            name="Other 2026 ESG Report",
            report_year=2026,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            owner_membership_id=admin_membership.id,
        )
        session.add_all([project, other_project])
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    tenant_id=tenant.id,
                    project_id=project.id,
                    membership_id=admin_membership.id,
                    project_role="OWNER",
                ),
                ProjectMember(
                    tenant_id=tenant.id,
                    project_id=other_project.id,
                    membership_id=admin_membership.id,
                    project_role="OWNER",
                ),
            ]
        )
        await session.commit()

        return {
            "tenant": tenant,
            "admin": admin,
            "editor": editor,
            "client_user": client_user,
            "company": company,
            "other_company": other_company,
            "admin_membership": admin_membership,
            "editor_membership": editor_membership,
            "client_membership": client_membership,
            "project": project,
            "other_project": other_project,
        }


@pytest_asyncio.fixture
async def admin_headers(client, seeded):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin12345"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def client_headers(client, seeded):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "client@example.com", "password": "client12345"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
