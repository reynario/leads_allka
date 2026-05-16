"""Scheduler diário: às 08:00 (TZ America/Sao_Paulo) puxa leads do Redrive e processa."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import SessionLocal
from app.logging_config import get_logger
from app.repositories import lead_repository as repo
from app.services import redrive
from app.workers import lead_worker

logger = get_logger(__name__)

scheduler: AsyncIOScheduler | None = None


async def run_daily_job() -> dict[str, int]:
    """Job principal: busca lote, persiste como pending, processa."""
    log = logger.bind(job="run_daily_job")
    log.info("scheduler.start")

    async with SessionLocal() as session:
        if await repo.has_active_processing(session, window_minutes=60):
            log.warning("scheduler.skip_active_processing_detected")
            return {"skipped": 1, "fetched": 0, "inserted": 0}

    try:
        rows = await redrive.fetch_pending_leads(limit=settings.daily_lead_batch_size)
    except Exception as exc:  # noqa: BLE001
        log.error("scheduler.redrive_failed", error=str(exc))
        rows = []

    inserted = 0
    if rows:
        async with SessionLocal() as session:
            inserted = await repo.upsert_leads(session, rows)

    stats = await lead_worker.run_batch(limit=settings.daily_lead_batch_size)
    log.info(
        "scheduler.done",
        fetched=len(rows),
        inserted=inserted,
        processed=stats["total"],
        ok=stats["ok"],
        failed=stats["failed"],
    )
    return {"fetched": len(rows), "inserted": inserted, **stats}


def start_scheduler() -> None:
    global scheduler
    if not settings.scheduler_enabled:
        logger.info("scheduler.disabled")
        return

    if scheduler and scheduler.running:
        return

    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        run_daily_job,
        CronTrigger(
            hour=settings.daily_job_hour,
            minute=settings.daily_job_minute,
            timezone=settings.tz,
        ),
        id="daily_lead_job",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "scheduler.started",
        hour=settings.daily_job_hour,
        minute=settings.daily_job_minute,
        tz=settings.tz,
    )


def shutdown_scheduler() -> None:
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
