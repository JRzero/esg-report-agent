from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.core.config import get_settings
from app.core.database import Base
from app.modules import models  # noqa
config=context.config
config.set_main_option('sqlalchemy.url',get_settings().database_url)
target_metadata=Base.metadata

def run_migrations_offline():
    context.configure(url=config.get_main_option('sqlalchemy.url'),target_metadata=target_metadata,literal_binds=True,compare_type=True)
    with context.begin_transaction(): context.run_migrations()
async def run_async_migrations():
    connectable=async_engine_from_config(config.get_section(config.config_ini_section),prefix='sqlalchemy.',poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(lambda conn: (context.configure(connection=conn,target_metadata=target_metadata,compare_type=True), context.run_migrations()))
    await connectable.dispose()
def run_migrations_online():
    import asyncio; asyncio.run(run_async_migrations())
if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
