"""Rotas da UI HTML: dashboard, lista de leads, detalhe, retry, run-now."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.deps import require_user
from app.models import User
from app.repositories import lead_repository as repo
from app import scheduler as scheduler_module
from app.scheduler import run_daily_job
from app.templating import templates

router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    by_status = await repo.count_by_status(session)
    last_24h = await repo.count_processed_in_window(session, hours=24)
    last_7d = await repo.count_processed_in_window(session, hours=24 * 7)
    avg_score = await repo.avg_score_in_window(session, hours=24 * 7)

    success_rate_7d = None
    if last_7d["total"] > 0:
        success_rate_7d = round((last_7d["sent"] / last_7d["total"]) * 100, 1)

    next_run = None
    sched = scheduler_module.scheduler
    if sched and sched.running:
        job = sched.get_job("daily_lead_job")
        if job and job.next_run_time:
            next_run = job.next_run_time

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "by_status": by_status,
            "last_24h": last_24h,
            "last_7d": last_7d,
            "avg_score": round(avg_score, 1) if avg_score is not None else None,
            "success_rate_7d": success_rate_7d,
            "next_run": next_run,
            "batch_size": settings.daily_lead_batch_size,
            "scheduler_enabled": settings.scheduler_enabled,
        },
    )


@router.get("/leads", response_class=HTMLResponse)
async def list_leads_page(
    request: Request,
    status: str | None = Query(default=None),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    leads = await repo.list_by_status(session, status, limit=100, offset=0)
    return templates.TemplateResponse(
        "leads_list.html",
        {
            "request": request,
            "user": user,
            "leads": leads,
            "current_status": status,
        },
    )


@router.get("/leads/{lead_id}", response_class=HTMLResponse)
async def lead_detail_page(
    request: Request,
    lead_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    lead = await repo.get_by_id(session, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    return templates.TemplateResponse(
        "lead_detail.html",
        {
            "request": request,
            "user": user,
            "lead": lead,
            "analysis": lead.analysis,
        },
    )


@router.post("/leads/{lead_id}/retry")
async def retry_lead_ui(
    request: Request,
    lead_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    await repo.reset_for_retry(session, lead_id)
    return RedirectResponse(url=f"/leads/{lead_id}", status_code=303)


@router.post("/run-now")
async def run_now_ui(user: User = Depends(require_user)) -> RedirectResponse:
    asyncio.create_task(run_daily_job())
    return RedirectResponse(url="/dashboard?triggered=1", status_code=303)
