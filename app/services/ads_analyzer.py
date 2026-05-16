"""Análise de anúncios ativos.

Meta: consulta https://graph.facebook.com/v19.0/ads_archive (Ad Library API).
Google: stub controlado por GOOGLE_ADS_ENABLED (até definirmos provedor).

Espelha o padrão de async httpx usado em ia_allka/backend/services/meta_service.py.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

META_BASE_URL = "https://graph.facebook.com/v19.0"


async def _meta_ads(search_term: str | None) -> dict[str, Any]:
    if not search_term:
        return {"has_ads": False, "ads_count": 0, "prints": [], "summary": "Sem termo de busca."}
    if not settings.meta_access_token:
        logger.warning("ads.meta_token_missing")
        return {"has_ads": None, "ads_count": 0, "prints": [], "summary": "Token Meta ausente."}

    params = {
        "access_token": settings.meta_access_token,
        "search_terms": search_term,
        "ad_reached_countries": "['BR']",
        "ad_active_status": "ACTIVE",
        "fields": "id,page_name,ad_snapshot_url,ad_delivery_start_time,ad_creative_link_titles",
        "limit": 10,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.get(f"{META_BASE_URL}/ads_archive", params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("ads.meta_request_failed", error=str(exc), term=search_term)
            return {"has_ads": None, "ads_count": 0, "prints": [], "summary": f"Erro Meta: {exc}"}

    data = response.json().get("data", [])
    snapshots = [item.get("ad_snapshot_url") for item in data if item.get("ad_snapshot_url")]

    return {
        "has_ads": len(data) > 0,
        "ads_count": len(data),
        "prints": snapshots[:5],
        "summary": (
            f"Encontrados {len(data)} anúncios ativos."
            if data
            else "Nenhum anúncio ativo encontrado."
        ),
        "raw": data[:10],
    }


async def _google_ads(domain: str | None) -> dict[str, Any]:
    if not settings.google_ads_enabled:
        return {"has_ads": None, "ads_count": 0, "prints": [], "summary": "Google Ads desabilitado."}

    # Placeholder: ainda não há provedor definido.
    # Quando definir (Google Ads Transparency Center / SerpAPI / etc),
    # implementar aqui mantendo o mesmo shape de retorno.
    return {"has_ads": None, "ads_count": 0, "prints": [], "summary": f"Stub Google para {domain}."}


def _extract_search_term(lead: Any) -> str | None:
    return (
        getattr(lead, "company_name", None)
        or getattr(lead, "website", None)
        or getattr(lead, "instagram", None)
    )


def _extract_domain(lead: Any) -> str | None:
    website = getattr(lead, "website", None)
    if not website:
        return None
    return website.replace("https://", "").replace("http://", "").split("/")[0]


async def analyze(lead: Any) -> dict[str, Any]:
    """Retorna `{meta: {...}, google: {...}}` com a estrutura usada pelo worker e pela IA."""
    meta = await _meta_ads(_extract_search_term(lead))
    google = await _google_ads(_extract_domain(lead))

    return {
        "meta": meta,
        "google": google,
        "has_meta_ads": bool(meta.get("has_ads")),
        "has_google_ads": bool(google.get("has_ads")) if google.get("has_ads") is not None else None,
        "meta_ads_print": (meta.get("prints") or [None])[0],
        "google_ads_print": (google.get("prints") or [None])[0],
    }
