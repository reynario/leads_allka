"""Gestao de usuarios (apenas admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.deps import require_admin
from app.models import User
from app.services import auth_service
from app.templating import templates

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_class=HTMLResponse)
async def list_users_page(
    request: Request,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    users = await auth_service.list_users(session)
    return templates.TemplateResponse(
        "users_list.html",
        {"request": request, "user": admin, "users": users, "flash": None},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_user_page(
    request: Request, admin: User = Depends(require_admin)
) -> HTMLResponse:
    return templates.TemplateResponse(
        "user_form.html",
        {"request": request, "user": admin, "target": None, "error": None},
    )


@router.post("/new")
async def create_user_action(
    request: Request,
    email: str = Form(...),
    name: str = Form(""),
    password: str = Form(...),
    is_admin: str = Form(""),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    existing = await auth_service.get_by_email(session, email)
    if existing:
        return templates.TemplateResponse(
            "user_form.html",
            {
                "request": request,
                "user": admin,
                "target": None,
                "error": f"Ja existe um usuario com o e-mail {email}.",
            },
            status_code=400,
        )
    await auth_service.create_user(
        session,
        email=email,
        password=password,
        name=name,
        is_admin=bool(is_admin),
    )
    return RedirectResponse(url="/users", status_code=303)


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_page(
    request: Request,
    user_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    target = await auth_service.get_user(session, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return templates.TemplateResponse(
        "user_form.html",
        {"request": request, "user": admin, "target": target, "error": None},
    )


@router.post("/{user_id}/edit")
async def update_user_action(
    request: Request,
    user_id: int,
    name: str = Form(""),
    password: str = Form(""),
    is_admin: str = Form(""),
    is_active: str = Form(""),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await auth_service.update_user(
        session,
        user_id=user_id,
        name=name,
        is_admin=bool(is_admin),
        is_active=bool(is_active),
        new_password=password or None,
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return RedirectResponse(url="/users", status_code=303)


@router.post("/{user_id}/delete")
async def delete_user_action(
    user_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Voce nao pode deletar a propria conta.")
    await auth_service.delete_user(session, user_id)
    return RedirectResponse(url="/users", status_code=303)
