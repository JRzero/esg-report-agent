from collections.abc import AsyncIterator
from functools import lru_cache
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_label)s', 'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s', 'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        options = {"pool_pre_ping": True}
        if settings.app_env == "test":
            options["poolclass"] = NullPool
        _engine = create_async_engine(settings.database_url, **options)
    return _engine

def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory

# Backward-compatible factory callable used by workers/scripts.
def SessionLocal() -> AsyncSession:
    return get_session_factory()()

async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session

async def set_tenant_context(session: AsyncSession, tenant_id: str | None) -> None:
    bind = session.get_bind()
    if tenant_id and bind.dialect.name == 'postgresql':
        await session.execute(text("select set_config('app.tenant_id', :tenant_id, true)"), {'tenant_id': tenant_id})
