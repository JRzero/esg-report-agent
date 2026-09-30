from __future__ import annotations

from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, get_engine
from app.core.security import hash_password
from app.main import app
from app.modules import models  # noqa: F401
from app.modules.models import Tenant, TenantMembership, User


@pytest_asyncio.fixture(autouse=True)
async def clean_database(tmp_path: Path):
    settings = get_settings()
    original_settings = settings.model_dump()
    settings.storage_backend = "local"
    settings.local_storage_path = str(tmp_path / "storage")
    settings.openviking_enabled = False
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    for key, value in original_settings.items():
        setattr(settings, key, value)
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(monkeypatch):
    from app.api import router as router_module

    monkeypatch.setattr(router_module.process_document, "delay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(router_module.run_ai_task, "delay", lambda *_args, **_kwargs: None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def seed_tenant(
    *,
    code: str = "tenant-a",
    email: str = "admin@example.com",
    password: str = "admin12345",
    tenant_role: str = "ADMIN",
    member_type: str = "INTERNAL",
):
    async with SessionLocal() as session:
        tenant = Tenant(name=code, code=code)
        user = User(
            email=email,
            name=email.split("@")[0],
            password_hash=hash_password(password),
        )
        session.add_all([tenant, user])
        await session.flush()
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            tenant_role=tenant_role,
            member_type=member_type,
        )
        session.add(membership)
        await session.commit()
        return tenant.id, user.id, membership.id


async def login(client: AsyncClient, email: str, password: str = "admin12345") -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
