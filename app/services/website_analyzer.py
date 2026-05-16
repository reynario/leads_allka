"""Análise estática do site (HTML).

Procura por: Meta Pixel, Google Tag, GTM, WhatsApp, formulários, links sociais.
Tentativa 1: requests + BeautifulSoup.
Tentativa 2 (opt-in via PLAYWRIGHT_ENABLED): renderiza com Chromium headless.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PATTERN_META_PIXEL = re.compile(r"fbq\s*\(|connect\.facebook\.net/.*?/fbevents\.js", re.IGNORECASE)
PATTERN_GOOGLE_TAG = re.compile(r"gtag\s*\(|googletagmanager\.com/gtag/js", re.IGNORECASE)
PATTERN_GTM = re.compile(r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+", re.IGNORECASE)
PATTERN_WHATSAPP = re.compile(r"wa\.me/|api\.whatsapp\.com|whatsapp://", re.IGNORECASE)
PATTERN_CONVERSION_EVENT = re.compile(r"\b(Purchase|Lead|Contact|SubmitForm|CompleteRegistration)\b")


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _empty_result(url: str | None) -> dict[str, Any]:
    return {
        "site_active": False,
        "has_whatsapp": False,
        "has_form": False,
        "has_meta_pixel": False,
        "has_google_tag": False,
        "has_gtm": False,
        "raw_signals": {"url": url, "error": "no_url"},
    }


def _analyze_html(html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    has_form = bool(soup.find("form"))
    has_whatsapp = bool(PATTERN_WHATSAPP.search(html))
    has_meta_pixel = bool(PATTERN_META_PIXEL.search(html))
    has_google_tag = bool(PATTERN_GOOGLE_TAG.search(html))
    has_gtm = bool(PATTERN_GTM.search(html))

    instagram_links = [a.get("href", "") for a in soup.find_all("a") if "instagram.com" in (a.get("href") or "")]
    facebook_links = [a.get("href", "") for a in soup.find_all("a") if "facebook.com" in (a.get("href") or "")]
    conversion_events = PATTERN_CONVERSION_EVENT.findall(html)

    return {
        "site_active": True,
        "has_whatsapp": has_whatsapp,
        "has_form": has_form,
        "has_meta_pixel": has_meta_pixel,
        "has_google_tag": has_google_tag,
        "has_gtm": has_gtm,
        "raw_signals": {
            "url": url,
            "html_length": len(html),
            "title": (soup.title.string.strip() if soup.title and soup.title.string else None),
            "instagram_links": instagram_links[:5],
            "facebook_links": facebook_links[:5],
            "conversion_events": list(set(conversion_events))[:10],
        },
    }


async def _fetch_with_httpx(url: str) -> str | None:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as exc:
        logger.warning("website.httpx_failed", url=url, error=str(exc))
        return None


async def _fetch_with_playwright(url: str) -> str | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("website.playwright_not_installed")
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=USER_AGENT)
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            html = await page.content()
            await browser.close()
            return html
    except Exception as exc:  # noqa: BLE001
        logger.warning("website.playwright_failed", url=url, error=str(exc))
        return None


async def analyze(url: str | None) -> dict[str, Any]:
    if not url:
        return _empty_result(url)

    normalized = _normalize_url(url)
    if not urlparse(normalized).netloc:
        return _empty_result(url)

    html = await _fetch_with_httpx(normalized)

    needs_fallback = html is None or len(html) < 2048 or "<noscript>" in (html or "")
    if needs_fallback and settings.playwright_enabled:
        logger.info("website.fallback_to_playwright", url=normalized)
        rendered = await _fetch_with_playwright(normalized)
        if rendered:
            html = rendered

    if html is None:
        return {**_empty_result(url), "raw_signals": {"url": normalized, "error": "fetch_failed"}}

    return _analyze_html(html, normalized)
