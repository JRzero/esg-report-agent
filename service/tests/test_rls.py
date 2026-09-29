import os

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import SessionLocal
from app.modules.models import Company, Tenant


@pytest.mark.asyncio
async def test_postgresql_rls_isolates_tenants_for_application_role():
    async with SessionLocal() as session:
        tenant_a = Tenant(name="Tenant A", code="tenant-a")
        tenant_b = Tenant(name="Tenant B", code="tenant-b")
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all(
            [
                Company(tenant_id=tenant_a.id, name="Company A"),
                Company(tenant_id=tenant_b.id, name="Company B"),
            ]
        )
        await session.commit()

        await session.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'esg_app_test') THEN
                    CREATE ROLE esg_app_test LOGIN PASSWORD 'esg_app_test' NOSUPERUSER NOBYPASSRLS;
                  END IF;
                END
                $$;
                """
            )
        )
        await session.execute(text("GRANT USAGE ON SCHEMA public TO esg_app_test"))
        await session.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO esg_app_test"))
        await session.commit()

    app_url = make_url(os.environ["DATABASE_URL"]).set(
        username="esg_app_test",
        password="esg_app_test",
    )
    engine = create_async_engine(app_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("select set_config('app.tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_a.id)},
            )
            rows = (
                await connection.execute(select(Company.name).order_by(Company.name))
            ).scalars().all()
            assert rows == ["Company A"]

            await connection.execute(
                text("select set_config('app.tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_b.id)},
            )
            rows = (
                await connection.execute(select(Company.name).order_by(Company.name))
            ).scalars().all()
            assert rows == ["Company B"]
    finally:
        await engine.dispose()
