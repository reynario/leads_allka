"""Análise de Instagram via Apify.

Roda o ator configurado em APIFY_INSTAGRAM_ACTOR (default: apify/instagram-profile-scraper),
extrai métricas do perfil e calcula a frequência de postagem.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from dateutil import parser as date_parser

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def _empty_result(reason: str = "no_handle") -> dict[str, Any]:
    return {
        "profile_found": False,
        "followers": None,
        "last_post_date": None,
        "posting_frequency": None,
        "best_post_url": None,
        "best_post_likes": None,
        "best_post_comments": None,
        "raw_signals": {"error": reason},
    }


def _normalize_handle(value: str) -> str:
    handle = value.strip().lstrip("@")
    if handle.startswith("http"):
        handle = handle.rstrip("/").split("/")[-1]
    return handle.split("?")[0]


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = date_parser.parse(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _calc_frequency(posts: list[dict[str, Any]]) -> str | None:
    dates = sorted(
        [d for d in (_parse_date(p.get("timestamp") or p.get("takenAt")) for p in posts) if d],
        reverse=True,
    )
    if len(dates) < 2:
        return None

    span_days = (dates[0] - dates[-1]).days or 1
    posts_per_week = len(dates) / (span_days / 7)

    if posts_per_week >= 5:
        return "Mais de 5 posts por semana"
    if posts_per_week >= 1:
        return f"{round(posts_per_week)} posts por semana"
    posts_per_month = posts_per_week * 4
    if posts_per_month >= 1:
        return f"{round(posts_per_month)} posts por mês"
    return "Menos de 1 post por mês"


def _pick_best_post(posts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not posts:
        return None
    return max(posts, key=lambda p: (p.get("likesCount") or 0) + (p.get("commentsCount") or 0) * 2)


def _run_apify_sync(handle: str) -> dict[str, Any]:
    """Executa o ator Apify de forma síncrona (chamado via to_thread)."""
    from apify_client import ApifyClient

    client = ApifyClient(settings.apify_token)

    run_input = {
        "usernames": [handle],
        "resultsLimit": 12,
        "resultsType": "details",
    }

    actor = client.actor(settings.apify_instagram_actor)
    run = actor.call(run_input=run_input, timeout_secs=120)

    if not run:
        return {}

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return {}

    items = list(client.dataset(dataset_id).iterate_items())
    if not items:
        return {}

    return items[0]


async def analyze(instagram: str | None) -> dict[str, Any]:
    if not instagram:
        return _empty_result("no_handle")
    if not settings.apify_token:
        logger.warning("instagram.token_missing")
        return _empty_result("apify_token_missing")

    handle = _normalize_handle(instagram)
    if not handle:
        return _empty_result("invalid_handle")

    try:
        profile = await asyncio.to_thread(_run_apify_sync, handle)
    except Exception as exc:  # noqa: BLE001
        logger.error("instagram.apify_failed", handle=handle, error=str(exc))
        return {**_empty_result("apify_call_failed"), "raw_signals": {"handle": handle, "error": str(exc)}}

    if not profile:
        return _empty_result("profile_not_found")

    posts = profile.get("latestPosts") or profile.get("posts") or []
    best_post = _pick_best_post(posts)
    last_date = _parse_date(profile.get("latestPostsTimestamp")) or (
        _parse_date(posts[0].get("timestamp")) if posts else None
    )

    return {
        "profile_found": True,
        "followers": profile.get("followersCount"),
        "last_post_date": last_date,
        "posting_frequency": _calc_frequency(posts),
        "best_post_url": (best_post or {}).get("url"),
        "best_post_likes": (best_post or {}).get("likesCount"),
        "best_post_comments": (best_post or {}).get("commentsCount"),
        "raw_signals": {
            "handle": handle,
            "username": profile.get("username"),
            "fullName": profile.get("fullName"),
            "biography": profile.get("biography"),
            "postsCount": profile.get("postsCount"),
            "verified": profile.get("verified"),
        },
    }
