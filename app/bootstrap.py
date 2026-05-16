"""Bootstrap inicial: cria admin do .env se a tabela users estiver vazia."""

from __future__ import annotations

from app.config import settings
from app.database import SessionLocal
from app.logging_config import get_logger
from app.services import auth_service

logger = get_logger(__name__)


async def bootstrap_admin_user() -> None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        logger.info("bootstrap.admin_skipped_no_env")
        return

    async with SessionLocal() as session:
        count = await auth_service.count_users(session)
        if count > 0:
            logger.info("bootstrap.admin_skipped_users_exist", count=count)
            return

        user = await auth_service.create_user(
            session,
            email=settings.bootstrap_admin_email,
            password=settings.bootstrap_admin_password,
            name=settings.bootstrap_admin_name,
            is_admin=True,
            is_active=True,
        )
        logger.info("bootstrap.admin_created", email=user.email, user_id=user.id)
