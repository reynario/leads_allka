from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


def _unique_prepared_statement_name() -> str:
    """Gera um nome unico para cada prepared statement.

    O Supabase Transaction Pooler (PgBouncer pool_mode=transaction) multiplexa
    transacoes em conexoes backend compartilhadas. Se asyncpg usar o nome
    padrao (__asyncpg_stmt_1__), uma conexao logica nova pode bater com
    prepared statement de outra deixado na mesma conexao backend e disparar
    DuplicatePreparedStatementError. Usando UUID, cada statement tem nome
    distinto e o conflito desaparece.
    """
    return f"__asyncpg_{uuid4().hex}__"


# NullPool: delegamos pooling para o PgBouncer do Supabase (Transaction Pooler).
# Manter um pool local do SQLAlchemy aumenta a chance de conexoes presas e
# duplica gestao de estado. Para Session Pooler ou Direct Connection, pode-se
# trocar por QueuePool com pool_size pequeno sem outras mudancas.
engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    future=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": _unique_prepared_statement_name,
    },
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
