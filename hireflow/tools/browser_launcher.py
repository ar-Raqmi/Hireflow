from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any


_LOCATION_HINTS: dict[str, tuple[str, str, str]] = {
    "kuala lumpur": ("Asia/Kuala_Lumpur", "en-MY,ms-MY;q=0.9,en;q=0.8", "en-MY"),
    "selangor": ("Asia/Kuala_Lumpur", "en-MY,ms-MY;q=0.9,en;q=0.8", "en-MY"),
    "johor": ("Asia/Kuala_Lumpur", "en-MY,ms-MY;q=0.9,en;q=0.8", "en-MY"),
    "singapore": ("Asia/Singapore", "en-SG,en;q=0.9", "en-SG"),
    "tokyo": ("Asia/Tokyo", "ja-JP,ja;q=0.9,en;q=0.8", "ja-JP"),
    "osaka": ("Asia/Tokyo", "ja-JP,ja;q=0.9,en;q=0.8", "ja-JP"),
    "jakarta": ("Asia/Jakarta", "id-ID,id;q=0.9,en;q=0.8", "id-ID"),
    "bandung": ("Asia/Jakarta", "id-ID,id;q=0.9,en;q=0.8", "id-ID"),
    "bangkok": ("Asia/Bangkok", "th-TH,th;q=0.9,en;q=0.8", "th-TH"),
    "ho chi minh": ("Asia/Ho_Chi_Minh", "vi-VN,vi;q=0.9,en;q=0.8", "vi-VN"),
    "hanoi": ("Asia/Ho_Chi_Minh", "vi-VN,vi;q=0.9,en;q=0.8", "vi-VN"),
    "manila": ("Asia/Manila", "en-PH,tl;q=0.9,en;q=0.8", "en-PH"),
    "seoul": ("Asia/Seoul", "ko-KR,ko;q=0.9,en;q=0.8", "ko-KR"),
    "london": ("Europe/London", "en-GB,en;q=0.9", "en-GB"),
    "berlin": ("Europe/Berlin", "de-DE,de;q=0.9,en;q=0.8", "de-DE"),
    "paris": ("Europe/Paris", "fr-FR,fr;q=0.9,en;q=0.8", "fr-FR"),
    "sydney": ("Australia/Sydney", "en-AU,en;q=0.9", "en-AU"),
    "new york": ("America/New_York", "en-US,en;q=0.9", "en-US"),
    "san francisco": ("America/Los_Angeles", "en-US,en;q=0.9", "en-US"),
    "los angeles": ("America/Los_Angeles", "en-US,en;q=0.9", "en-US"),
}


def _resolve_hint(locations: list[str] | None) -> tuple[str, str, str]:
    """Pick timezone/language from the first known preferred location."""
    for raw in locations or []:
        key = str(raw).strip().lower()
        for name, hint in _LOCATION_HINTS.items():
            if name in key:
                return hint
    return "Asia/Kuala_Lumpur", "en-MY,ms-MY;q=0.9,en;q=0.8", "en-MY"


STEALTH_INIT_SCRIPT = r"""
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
const origQuery = window.navigator.permissions && window.navigator.permissions.query;
if (origQuery) {
  window.navigator.permissions.query = (parameters) =>
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : origQuery(parameters);
}
"""


def stealth_launch_kwargs() -> dict[str, Any]:
    """Chromium launch args that let headless Chromium run as root in a
    container AND look more like a real browser (reduces Cloudflare/anti-bot
    challenge). No third-party deps; stays fully on Cloud Run."""
    return {
        "headless": True,
        "chromium_sandbox": False,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
        ],
    }


def stealth_context_kwargs(locations: list[str] | None = None) -> dict[str, Any]:
    """A realistic browser context derived from the user's preferred location.

    Falls back to a Malaysia default (the tool's origin market) when the
    location is unknown or empty. Only the request's *fingerprint* is derived
    from the user's location - the outbound IP is always Cloud Run's egress.
    """
    tz, accept_lang, locale = _resolve_hint(locations)
    return {
        "locale": locale,
        "timezone_id": tz,
        "viewport": {"width": 1366, "height": 900},
        "screen": {"width": 1366, "height": 900},
        "device_scale_factor": 1,
        "java_script_enabled": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "extra_http_headers": {
            "Accept-Language": accept_lang,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "color_scheme": "light",
    }


def apply_stealth(page: Any) -> None:
    """Inject the anti-detection script into a freshly created page."""
    await page.add_init_script(STEALTH_INIT_SCRIPT)


@asynccontextmanager
async def stealth_browser():
    """Launch headless stealth Chromium; close it on exit.

    Shared by every Playwright source so the launch/sandbox flags live in one
    place. The caller catches a missing Chromium as non-fatal.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(**stealth_launch_kwargs())
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def stealth_page(browser: Any, locations: list[str] | None = None):
    """A new stealth context+page (location-fingerprinted), closed on exit."""
    context = await browser.new_context(**stealth_context_kwargs(locations))
    page = await context.new_page()
    apply_stealth(page)
    try:
        yield page
    finally:
        await context.close()
