"""Cliente Redrive — busca leads pendentes para enriquecimento.

O endpoint exato vai ser ajustado quando o token chegar; o adapter abaixo
centraliza a chamada e o mapping em um só lugar (`_endpoint` + `_map_row`).
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class RedriveError(Exception):
    pass


class RedriveClient:
    _endpoint = "/leads"  # ajustar quando a doc do Redrive chegar
    _timeout = 30.0

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or settings.redrive_base_url).rstrip("/")
        self.token = token or settings.redrive_api_token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def fetch_pending_leads(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.token:
            logger.warning("redrive.token_missing")
            return []

        url = f"{self.base_url}{self._endpoint}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        params = {"status": "new", "limit": limit}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("redrive.request_failed", error=str(exc))
                raise RedriveError(f"Redrive request failed: {exc}") from exc

        payload = response.json()
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise RedriveError(f"Unexpected Redrive payload shape: {type(payload).__name__}")

        return [self._map_row(item) for item in items]

    @staticmethod
    def _map_row(item: dict[str, Any]) -> dict[str, Any]:
        """Mapeia o JSON do Redrive para o shape da tabela leads.leads.

        Ajustar nomes conforme a doc do Redrive — manter sempre `redrive_id` como
        chave única e os demais campos opcionais.
        """
        return {
            "redrive_id": str(item.get("id") or item.get("redrive_id") or item.get("uuid")),
            "company_name": item.get("company_name") or item.get("nome_empresa") or item.get("name"),
            "website": item.get("website") or item.get("site"),
            "instagram": item.get("instagram") or item.get("instagram_handle"),
            "phone": item.get("phone") or item.get("telefone") or item.get("whatsapp"),
            "city": item.get("city") or item.get("cidade"),
            "segment": item.get("segment") or item.get("segmento") or item.get("category"),
        }


async def fetch_pending_leads(limit: int = 20) -> list[dict[str, Any]]:
    return await RedriveClient().fetch_pending_leads(limit=limit)
