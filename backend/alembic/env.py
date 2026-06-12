"""
Async-aware Alembic environment.

The project uses the same async SQLAlchemy engine as the app so migrations
work against any driver the app supports (aiosqlite today; asyncpg /
aiomysql / libsql in prod). The DB URL is pulled from app.config so the
app and Alembic never disagree about which database to touch.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base + every model so autogenerate sees the full metadata.
from app.config import get_settings
from app.database import Base
from app.models import user, organization, role, audit, import_job  # noqa: F401
from app.models.modules import school, hospital, business  # noqa: F401


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the runtime URL at execution time (supports DATABASE_URL env overrides).
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL to stdout)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-safe ALTERs; no-op on other dialects.
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
