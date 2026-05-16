"""Rotas de autenticacao: login (GET form / POST submit) + logout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services import auth_service
from app.templating import templates

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/") -> HTMLResponse:
    if request.session.get("user_id"):
        return RedirectResponse(url=next or "/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "next_url": next, "error": None},
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    session: AsyncSession = Depends(get_session),
):
    user = await auth_service.authenticate(session, email, password)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next_url": next,
                "error": "E-mail ou senha invalidos.",
                "email": email,
            },
            status_code=401,
        )
    request.session["user_id"] = user.id
    safe_next = next if next and next.startswith("/") else "/"
    return RedirectResponse(url=safe_next, status_code=303)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
