"""Geração da análise comercial via OpenAI (JSON mode).

Recebe lead + 3 análises e retorna: resumo, dores, oportunidade, score, mensagem_abordagem.
"""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "Você é um analista comercial sênior que prepara briefings para SDRs. "
    "Receba os dados de uma empresa (site, Instagram, anúncios) e gere uma análise "
    "curta, prática e acionável. Responda SEMPRE em JSON válido com as chaves: "
    "resumo (string, 2-3 frases), dores (array de strings, 2-4 itens), "
    "oportunidade (string, 1-2 frases), score (inteiro 0-100), "
    "mensagem_abordagem (string, até 400 caracteres, tom consultivo)."
)


def _build_user_prompt(
    lead: Any, site_data: dict[str, Any], instagram_data: dict[str, Any], ads_data: dict[str, Any]
) -> str:
    return (
        "Analise os dados abaixo e gere uma análise comercial para um SDR.\n\n"
        f"Empresa: {getattr(lead, 'company_name', None)}\n"
        f"Cidade: {getattr(lead, 'city', None)}\n"
        f"Segmento: {getattr(lead, 'segment', None)}\n"
        f"Site: {getattr(lead, 'website', None)}\n"
        f"Instagram: {getattr(lead, 'instagram', None)}\n\n"
        f"Análise do site:\n{json.dumps(site_data, default=str, ensure_ascii=False)}\n\n"
        f"Análise do Instagram:\n{json.dumps(instagram_data, default=str, ensure_ascii=False)}\n\n"
        f"Análise de anúncios:\n{json.dumps(ads_data, default=str, ensure_ascii=False)}\n\n"
        "Retorne APENAS o JSON solicitado."
    )


async def _call_openai(messages: list[dict[str, str]]) -> dict[str, Any]:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _coerce_score(value: Any) -> int | None:
    try:
        score = int(value)
        return max(0, min(100, score))
    except (TypeError, ValueError):
        return None


def _coerce_pains(value: Any) -> str | None:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value if v)
    if isinstance(value, str):
        return value
    return None


async def generate(
    lead: Any,
    site_data: dict[str, Any],
    instagram_data: dict[str, Any],
    ads_data: dict[str, Any],
) -> dict[str, Any]:
    if not settings.openai_api_key:
        logger.warning("ai.openai_key_missing")
        return {
            "resumo": "Análise IA indisponível (sem OPENAI_API_KEY).",
            "dores": None,
            "oportunidade": None,
            "score": None,
            "mensagem_abordagem": None,
        }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(lead, site_data, instagram_data, ads_data)},
    ]

    for attempt in (1, 2):
        try:
            raw = await _call_openai(messages)
            return {
                "resumo": raw.get("resumo"),
                "dores": _coerce_pains(raw.get("dores")),
                "oportunidade": raw.get("oportunidade"),
                "score": _coerce_score(raw.get("score")),
                "mensagem_abordagem": raw.get("mensagem_abordagem"),
            }
        except json.JSONDecodeError as exc:
            logger.warning("ai.invalid_json", attempt=attempt, error=str(exc))
            if attempt == 2:
                raise
        except Exception as exc:  # noqa: BLE001
            logger.error("ai.call_failed", attempt=attempt, error=str(exc))
            if attempt == 2:
                raise

    raise RuntimeError("Falha inesperada na geração da análise IA.")
