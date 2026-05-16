"""Dependencias FastAPI compartilhadas (sessao, current_user, admin token)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import User
from app.services import auth_service


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = await auth_service.get_user(session, int(user_id))
    if user is None or not user.is_active:
        request.session.clear()
        return None
    return user


async def require_user(
    request: Request, user: User | None = Depends(get_current_user)
) -> User:
    if user is None:
        next_url = request.url.path
        if request.url.query:
            next_url += f"?{request.url.query}"
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/login?next={next_url}"},
        )
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Apenas administradores.")
    return user


async def require_admin_token(request: Request) -> None:
    token = request.headers.get("x-admin-token")
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Token")
