from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Lead, LeadAnalysis, LeadStatus


async def upsert_leads(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Insere leads novos (ignora `redrive_id` já existente). Retorna quantos foram inseridos."""
    if not rows:
        return 0

    stmt = (
        insert(Lead)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["redrive_id"])
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def list_pending(session: AsyncSession, limit: int) -> list[Lead]:
    """Retorna leads para processar.

    Ordem: failed (com retry < max) primeiro, depois pending novos.
    """
    stmt = (
        select(Lead)
        .where(
            or_(
                Lead.status == LeadStatus.PENDING.value,
                and_(
                    Lead.status == LeadStatus.FAILED.value,
                    Lead.retry_count < settings.max_retry_count,
                ),
            )
        )
        .order_by(
            (Lead.status == LeadStatus.FAILED.value).desc(),
            Lead.created_at.asc(),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def has_active_processing(session: AsyncSession, window_minutes: int = 60) -> bool:
    """Verifica se já existe lead em status 'processing' há menos de N minutos (lock anti-concorrência)."""
    threshold = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    stmt = (
        select(Lead.id)
        .where(Lead.status == LeadStatus.PROCESSING.value)
        .where(Lead.created_at >= threshold)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.first() is not None


async def mark_processing(session: AsyncSession, lead_id: int) -> None:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        return
    lead.status = LeadStatus.PROCESSING.value
    lead.error_message = None
    await session.commit()


async def mark_completed(session: AsyncSession, lead_id: int, bitrix_id: int | None) -> None:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        return
    lead.status = LeadStatus.SENT_TO_BITRIX.value
    lead.bitrix_id = bitrix_id
    lead.processed_at = datetime.now(timezone.utc)
    lead.error_message = None
    await session.commit()


async def mark_failed(session: AsyncSession, lead_id: int, error_message: str) -> None:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        return
    lead.status = LeadStatus.FAILED.value
    lead.error_message = error_message[:2000]
    lead.retry_count = (lead.retry_count or 0) + 1
    lead.processed_at = datetime.now(timezone.utc)
    await session.commit()


async def reset_for_retry(session: AsyncSession, lead_id: int) -> bool:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        return False
    lead.status = LeadStatus.PENDING.value
    lead.error_message = None
    await session.commit()
    return True


async def upsert_analysis(
    session: AsyncSession, lead_id: int, data: dict[str, Any]
) -> LeadAnalysis:
    """Cria ou atualiza a análise 1:1 do lead."""
    stmt = select(LeadAnalysis).where(LeadAnalysis.lead_id == lead_id)
    result = await session.execute(stmt)
    analysis = result.scalar_one_or_none()

    if analysis is None:
        analysis = LeadAnalysis(lead_id=lead_id, **data)
        session.add(analysis)
    else:
        for key, value in data.items():
            setattr(analysis, key, value)

    await session.commit()
    await session.refresh(analysis)
    return analysis


async def get_by_id(session: AsyncSession, lead_id: int) -> Lead | None:
    return await session.get(Lead, lead_id)


async def list_by_status(
    session: AsyncSession, status: str | None, limit: int, offset: int
) -> list[Lead]:
    stmt = select(Lead).order_by(Lead.id.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Lead.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())
