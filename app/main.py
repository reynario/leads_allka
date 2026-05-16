from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.logging_config import configure_logging, get_logger
from app.routers import health, leads
from app.scheduler import shutdown_scheduler, start_scheduler

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("app.startup")
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
        logger.info("app.shutdown")


app = FastAPI(
    title="Sistema de Leads Allka",
    version="1.0.0",
    description="Robô diário que enriquece leads do Redrive e envia para o Bitrix24.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(leads.router)
