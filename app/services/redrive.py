"""Cliente Redrive CRM — busca contatos para enriquecimento.

Fluxo de autenticacao:
  1. POST /login com {login, password} → recebe JWT
  2. Usar JWT como Bearer nas chamadas seguintes
  3. Renovar automaticamente quando receber 401

Configuracao no .env:
  REDRIVE_API_TOKEN   = JWT pre-obtido manualmente (se ja tiver)
  REDRIVE_LOGIN       = e-mail da conta Redrive (para login automatico)
  REDRIVE_PASSWORD    = senha da conta Redrive
  REDRIVE_BASE_URL    = https://api.redrive.com.br
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_jwt_cache: dict[str, Any] = {"token": None, "expires_at": None}
_jwt_lock = asyncio.Lock()


class RedriveError(Exception):
    pass


class RedriveClient:
    _timeout = 30.0

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        login: str | None = None,
        password: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.redrive_base_url).rstrip("/")
        self._static_token = token or settings.redrive_api_token
        self._login = login or getattr(settings, "redrive_login", "")
        self._password = password or getattr(settings, "redrive_password", "")

    async def _get_jwt(self) -> str | None:
        """Retorna o JWT valido, fazendo login se necessario."""
        global _jwt_cache

        # Se ja tem token estatico (obtido manualmente), usa direto.
        if self._static_token:
            return self._static_token

        if not self._login or not self._password:
            logger.warning("redrive.no_credentials")
            return None

        async with _jwt_lock:
            now = datetime.now(timezone.utc)
            if _jwt_cache["token"] and _jwt_cache["expires_at"] and now < _jwt_cache["expires_at"]:
                return _jwt_cache["token"]

            # Faz login para obter novo JWT.
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/login",
                        json={"login": self._login, "password": self._password},
                        headers={"Content-Type": "application/json"},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                token = (
                    data.get("token")
                    or data.get("access_token")
                    or data.get("jwt")
                    or (data.get("data") or {}).get("token")
                )
                if not token:
                    logger.error("redrive.login_no_token", response=str(data)[:200])
                    return None

                _jwt_cache["token"] = token
                # JWT do Redrive normalmente valido por 24h; renovamos com folga.
                _jwt_cache["expires_at"] = now + timedelta(hours=22)
                logger.info("redrive.login_ok")
                return token

            except httpx.HTTPError as exc:
                logger.error("redrive.login_failed", error=str(exc))
                return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def fetch_pending_leads(self, limit: int = 20) -> list[dict[str, Any]]:
        token = await self._get_jwt()
        if not token:
            logger.warning("redrive.no_token_available")
            return []

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # POST /v1/crm/contact — lista contatos com paginacao.
        # Busca os mais recentes (sem filtro de data para pegar todos disponíveis).
        body: dict[str, Any] = {"params": {"offset": "0", "limit": str(limit)}}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/v1/crm/contact",
                    json=body,
                    headers=headers,
                )
                if response.status_code == 401:
                    # JWT expirou; invalida cache e retenta na proxima chamada do tenacity.
                    _jwt_cache["token"] = None
                    _jwt_cache["expires_at"] = None
                    raise RedriveError("JWT expirado (401). Renovando na proxima tentativa.")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("redrive.request_failed", error=str(exc))
                raise RedriveError(f"Redrive request failed: {exc}") from exc

        payload = response.json()
        logger.debug("redrive.raw_response", payload_keys=list(payload.keys()) if isinstance(payload, dict) else "list")

        # Normaliza: a API pode retornar {data: [...]} ou diretamente [...]
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            # Tenta outras chaves comuns
            for key in ("contacts", "leads", "results", "items"):
                if isinstance(payload, dict) and isinstance(payload.get(key), list):
                    items = payload[key]
                    break
            else:
                logger.warning("redrive.unexpected_shape", payload_preview=str(payload)[:300])
                return []

        logger.info("redrive.fetched", count=len(items))
        return [self._map_row(item) for item in items]

    @staticmethod
    def _map_row(item: dict[str, Any]) -> dict[str, Any]:
        """Mapeia contato do Redrive para o schema da tabela leads.leads.

        Campos CRM do Redrive: id, firstname, lastname, company, phone,
        mobilephone, email, city, uf, zipcode, address, number, district,
        date_of_birth, tags, ...
        """
        first = item.get("firstname") or ""
        last = item.get("lastname") or ""
        full_name = f"{first} {last}".strip() or item.get("name") or item.get("nome")

        return {
            "redrive_id": str(
                item.get("id") or item.get("uuid") or item.get("_id") or ""
            ),
            "company_name": (
                item.get("company")
                or item.get("company_name")
                or item.get("nome_empresa")
                or full_name
                or ""
            ),
            "website": item.get("website") or item.get("site") or "",
            "instagram": (
                item.get("instagram")
                or item.get("instagram_handle")
                or _extract_instagram(item.get("tags") or "")
                or ""
            ),
            "phone": (
                item.get("phone")
                or item.get("mobilephone")
                or item.get("telefone")
                or item.get("whatsapp")
                or ""
            ),
            "city": item.get("city") or item.get("cidade") or "",
            "segment": (
                item.get("segment")
                or item.get("segmento")
                or item.get("category")
                or item.get("uf")
                or ""
            ),
        }


def _extract_instagram(tags: str) -> str:
    """Tenta extrair handle do Instagram de uma string de tags separadas por virgula."""
    for tag in tags.split(","):
        tag = tag.strip().lower()
        if tag.startswith("ig:") or tag.startswith("instagram:"):
            return tag.split(":", 1)[-1].strip().lstrip("@")
    return ""


async def fetch_pending_leads(limit: int = 20) -> list[dict[str, Any]]:
    return await RedriveClient().fetch_pending_leads(limit=limit)
