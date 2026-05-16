from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.bootstrap import bootstrap_admin_user
from app.config import settings
from app.logging_config import configure_logging, get_logger
from app.routers import api_leads, auth, health, ui, users
from app.scheduler import shutdown_scheduler, start_scheduler

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("app.startup")
    try:
        await bootstrap_admin_user()
    except Exception as exc:  # noqa: BLE001
        logger.warning("app.bootstrap_admin_failed", error=str(exc))
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
        logger.info("app.shutdown")


app = FastAPI(
    title="Sistema de Leads Allka",
    version="1.1.0",
    description="Robo diario que enriquece leads do Redrive e envia para o Bitrix24.",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=False,  # Traefik termina TLS; cookie continua seguro via SameSite + secret
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ordem dos routers: health primeiro (path "/"), depois auth (login antes do middleware exigir).
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(users.router)
app.include_router(api_leads.router)
