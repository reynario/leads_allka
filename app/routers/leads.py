from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.repositories import lead_repository as repo
from app.scheduler import run_daily_job

router = APIRouter(prefix="/leads", tags=["leads"])


def _require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Token")


def _serialize_lead(lead: Any) -> dict[str, Any]:
    return {
        "id": lead.id,
        "redrive_id": lead.redrive_id,
        "company_name": lead.company_name,
        "website": lead.website,
        "instagram": lead.instagram,
        "phone": lead.phone,
        "city": lead.city,
        "segment": lead.segment,
        "status": lead.status,
        "bitrix_id": lead.bitrix_id,
        "retry_count": lead.retry_count,
        "error_message": lead.error_message,
        "created_at": lead.created_at,
        "processed_at": lead.processed_at,
    }


@router.get("")
async def list_leads(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    leads = await repo.list_by_status(session, status, limit, offset)
    return {"count": len(leads), "items": [_serialize_lead(l) for l in leads]}


@router.get("/{lead_id}")
async def get_lead(lead_id: int, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    lead = await repo.get_by_id(session, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    analysis = lead.analysis
    return {
        "lead": _serialize_lead(lead),
        "analysis": (
            {
                "site_active": analysis.site_active,
                "has_whatsapp": analysis.has_whatsapp,
                "has_form": analysis.has_form,
                "has_meta_pixel": analysis.has_meta_pixel,
                "has_google_tag": analysis.has_google_tag,
                "has_gtm": analysis.has_gtm,
                "instagram_active": analysis.instagram_active,
                "last_post_date": analysis.last_post_date,
                "posting_frequency": analysis.posting_frequency,
                "best_post_url": analysis.best_post_url,
                "best_post_likes": analysis.best_post_likes,
                "best_post_comments": analysis.best_post_comments,
                "has_meta_ads": analysis.has_meta_ads,
                "has_google_ads": analysis.has_google_ads,
                "ai_summary": analysis.ai_summary,
                "ai_pains": analysis.ai_pains,
                "ai_opportunity": analysis.ai_opportunity,
                "ai_message": analysis.ai_message,
                "score": analysis.score,
            }
            if analysis
            else None
        ),
    }


@router.post("/run-now", dependencies=[Depends(_require_admin)])
async def trigger_run_now() -> dict[str, str]:
    """Dispara o job diário fora do horário programado. Roda em background."""
    asyncio.create_task(run_daily_job())
    return {"status": "started"}


@router.post("/{lead_id}/retry", dependencies=[Depends(_require_admin)])
async def retry_lead(lead_id: int, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    ok = await repo.reset_for_retry(session, lead_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "pending", "lead_id": lead_id}
