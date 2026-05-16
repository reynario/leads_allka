"""Auth service: hash de senha (bcrypt) + autenticacao + CRUD basico de users."""

from __future__ import annotations

from datetime import datetime, timezone

from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import User

logger = get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:  # noqa: BLE001
        return False


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    stmt = select(User).where(User.email == email.lower().strip())
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    await session.commit()
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def list_users(session: AsyncSession) -> list[User]:
    stmt = select(User).order_by(User.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(User)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower().strip())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    email: str,
    password: str,
    name: str = "",
    is_admin: bool = False,
    is_active: bool = True,
) -> User:
    user = User(
        email=email.lower().strip(),
        name=name.strip(),
        password_hash=hash_password(password),
        is_admin=is_admin,
        is_active=is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession,
    user_id: int,
    name: str | None = None,
    is_admin: bool | None = None,
    is_active: bool | None = None,
    new_password: str | None = None,
) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    if name is not None:
        user.name = name.strip()
    if is_admin is not None:
        user.is_admin = is_admin
    if is_active is not None:
        user.is_active = is_active
    if new_password:
        user.password_hash = hash_password(new_password)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    user = await session.get(User, user_id)
    if user is None:
        return False
    await session.delete(user)
    await session.commit()
    return True
