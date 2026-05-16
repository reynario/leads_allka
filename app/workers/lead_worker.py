"""Worker que orquestra o enriquecimento de um lead.

Tolerância a falhas parciais: se Instagram/anúncios/site falharem, segue com o
resto. Só falha o lead inteiro se Bitrix24 falhar (que é o destino do dado).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.logging_config import get_logger
from app.models import Lead
from app.repositories import lead_repository as repo
from app.services import (
    ads_analyzer,
    ai_analyzer,
    bitrix,
    instagram_analyzer,
    website_analyzer,
)

logger = get_logger(__name__)


async def _run_step(name: str, coro, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001
        logger.warning("worker.step_failed", step=name, error=str(exc))
        return {**default, "error": str(exc)}


def _build_analysis_row(
    site_data: dict[str, Any],
    instagram_data: dict[str, Any],
    ads_data: dict[str, Any],
    ai_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "site_active": site_data.get("site_active"),
        "has_whatsapp": site_data.get("has_whatsapp"),
        "has_form": site_data.get("has_form"),
        "has_meta_pixel": site_data.get("has_meta_pixel"),
        "has_google_tag": site_data.get("has_google_tag"),
        "has_gtm": site_data.get("has_gtm"),
        "instagram_active": instagram_data.get("profile_found"),
        "last_post_date": instagram_data.get("last_post_date"),
        "posting_frequency": instagram_data.get("posting_frequency"),
        "best_post_url": instagram_data.get("best_post_url"),
        "best_post_likes": instagram_data.get("best_post_likes"),
        "best_post_comments": instagram_data.get("best_post_comments"),
        "has_meta_ads": ads_data.get("has_meta_ads"),
        "has_google_ads": ads_data.get("has_google_ads"),
        "meta_ads_print": ads_data.get("meta_ads_print"),
        "google_ads_print": ads_data.get("google_ads_print"),
        "ai_summary": ai_result.get("resumo"),
        "ai_pains": ai_result.get("dores"),
        "ai_opportunity": ai_result.get("oportunidade"),
        "ai_message": ai_result.get("mensagem_abordagem"),
        "score": ai_result.get("score"),
        "raw_payload": {
            "site": site_data,
            "instagram": instagram_data,
            "ads": ads_data,
            "ai": ai_result,
        },
    }


async def process_lead(lead: Lead, session: AsyncSession) -> int | None:
    """Enriquece um lead, salva análise e cria no Bitrix24. Retorna o bitrix_id."""
    log = logger.bind(lead_id=lead.id, redrive_id=lead.redrive_id, company=lead.company_name)
    log.info("worker.lead_start")

    site_data = await _run_step(
        "website", website_analyzer.analyze(lead.website), {"site_active": False}
    )
    instagram_data = await _run_step(
        "instagram", instagram_analyzer.analyze(lead.instagram), {"profile_found": False}
    )
    ads_data = await _run_step(
        "ads", ads_analyzer.analyze(lead), {"has_meta_ads": None, "has_google_ads": None}
    )

    try:
        ai_result = await ai_analyzer.generate(lead, site_data, instagram_data, ads_data)
    except Exception as exc:  # noqa: BLE001
        log.warning("worker.ai_failed", error=str(exc))
        ai_result = {
            "resumo": f"Falha na análise IA: {exc}",
            "dores": None,
            "oportunidade": None,
            "score": None,
            "mensagem_abordagem": None,
        }

    bitrix_id = await bitrix.send_lead(lead, site_data, instagram_data, ads_data, ai_result)

    analysis_row = _build_analysis_row(site_data, instagram_data, ads_data, ai_result)
    await repo.upsert_analysis(session, lead.id, analysis_row)

    log.info("worker.lead_done", bitrix_id=bitrix_id)
    return bitrix_id


async def run_batch(limit: int) -> dict[str, int]:
    """Processa um lote de leads pendentes. Cada lead em sua própria sessão."""
    stats = {"total": 0, "ok": 0, "failed": 0}

    async with SessionLocal() as session:
        leads = await repo.list_pending(session, limit)
        stats["total"] = len(leads)

    for lead in leads:
        async with SessionLocal() as session:
            await repo.mark_processing(session, lead.id)
            try:
                bitrix_id = await process_lead(lead, session)
                await repo.mark_completed(session, lead.id, bitrix_id)
                stats["ok"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("worker.lead_failed", lead_id=lead.id, error=str(exc))
                await repo.mark_failed(session, lead.id, str(exc))
                stats["failed"] += 1

    return stats
