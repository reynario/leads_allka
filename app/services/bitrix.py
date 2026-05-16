"""Cliente Bitrix24 — criação de leads via webhook REST.

Use o método clássico `crm.lead.add`. Os campos UF_CRM_* precisam ser criados
no Bitrix antes (Configurações > CRM > Campos personalizados de Lead).
Se algum UF_CRM ainda não existir, o Bitrix devolve erro 400 — basta ajustar
o mapping em UF_FIELDS.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


UF_FIELDS = {
    "ai_summary": "UF_CRM_ANALISE_IA",
    "ai_score": "UF_CRM_SCORE_IA",
    "meta_pixel": "UF_CRM_META_PIXEL",
    "google_tag": "UF_CRM_GOOGLE_TAG",
    "instagram_status": "UF_CRM_INSTAGRAM_STATUS",
    "meta_ads": "UF_CRM_META_ADS",
    "google_ads": "UF_CRM_GOOGLE_ADS",
}


class BitrixError(Exception):
    pass


def _yes_no(value: Any) -> str:
    if value is True:
        return "Sim"
    if value is False:
        return "Não"
    return "Indefinido"


def _build_payload(
    lead: Any,
    site_data: dict[str, Any],
    instagram_data: dict[str, Any],
    ads_data: dict[str, Any],
    ai_result: dict[str, Any],
) -> dict[str, Any]:
    instagram_status = "Ativo" if instagram_data.get("profile_found") else "Inativo"

    fields: dict[str, Any] = {
        "TITLE": getattr(lead, "company_name", None) or f"Lead Redrive {getattr(lead, 'redrive_id', '')}",
        "NAME": getattr(lead, "company_name", None),
        "SOURCE_ID": settings.bitrix_source_id,
        "COMMENTS": ai_result.get("resumo") or "Análise gerada pelo Sistema de Leads Allka.",
        UF_FIELDS["ai_summary"]: ai_result.get("resumo") or "",
        UF_FIELDS["ai_score"]: ai_result.get("score"),
        UF_FIELDS["meta_pixel"]: _yes_no(site_data.get("has_meta_pixel")),
        UF_FIELDS["google_tag"]: _yes_no(site_data.get("has_google_tag")),
        UF_FIELDS["instagram_status"]: instagram_status,
        UF_FIELDS["meta_ads"]: _yes_no(ads_data.get("has_meta_ads")),
        UF_FIELDS["google_ads"]: _yes_no(ads_data.get("has_google_ads")),
    }

    if getattr(lead, "phone", None):
        fields["PHONE"] = [{"VALUE": lead.phone, "VALUE_TYPE": "WORK"}]
    if getattr(lead, "website", None):
        fields["WEB"] = [{"VALUE": lead.website, "VALUE_TYPE": "WORK"}]

    return {"fields": fields}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def send_lead(
    lead: Any,
    site_data: dict[str, Any],
    instagram_data: dict[str, Any],
    ads_data: dict[str, Any],
    ai_result: dict[str, Any],
) -> int:
    if not settings.bitrix_webhook_url:
        raise BitrixError("BITRIX_WEBHOOK_URL não configurado.")

    payload = _build_payload(lead, site_data, instagram_data, ads_data, ai_result)
    url = f"{settings.bitrix_webhook_url.rstrip('/')}/crm.lead.add.json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)

    if response.status_code >= 400:
        logger.error("bitrix.http_error", status=response.status_code, body=response.text[:500])
        raise BitrixError(f"Bitrix HTTP {response.status_code}: {response.text[:300]}")

    data = response.json()
    if "error" in data:
        logger.error("bitrix.api_error", error=data.get("error"), description=data.get("error_description"))
        raise BitrixError(f"Bitrix erro: {data.get('error_description') or data.get('error')}")

    result = data.get("result")
    if not isinstance(result, int):
        raise BitrixError(f"Bitrix retornou resultado inesperado: {data}")

    logger.info("bitrix.lead_created", lead_id=getattr(lead, "id", None), bitrix_id=result)
    return result
