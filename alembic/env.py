"""Alembic environment — modo async, lê DATABASE_URL do app.config."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from uuid import uuid4

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base
from app.models import Lead, LeadAnalysis, User  # noqa: F401 — registra modelos no Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="leads",
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="leads",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # NullPool + nomes unicos de prepared statement: obrigatorio com Supabase
    # Transaction Pooler (PgBouncer transaction mode reutiliza conexoes backend
    # e quebra com nomes default __asyncpg_stmt_N__).
    connectable = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
        },
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
