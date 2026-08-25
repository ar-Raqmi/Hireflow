from __future__ import annotations

import json
from typing import Any

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource

_DISABLED_ERROR = (
    "Playwright source disabled (set HIREFLOW_PLAYWRIGHT=1 with Chromium bundled in the image)"
)


class PlaywrightSource(JobSource):
    """Layer II browser-automation source (opt-in, last resort).

    Wraps ``playwright.async_api`` so JS-heavy SPA career pages (Kalibrr,
    MyCareersFuture, Wantedly-SPA, anti-bot pages) can still be read when they
    expose neither a public API nor JSON-LD to a plain fetch. Gated behind
    ``HIREFLOW_PLAYWRIGHT=1``; when disabled it is a no-op returning ``[]`` with
    ``last_error`` set. Parses any ``application/ld+json`` ``JobPosting`` nodes
    the page renders (the common SPA pattern) and falls back to one row per
    page when there are none. Soft-fails at every step — a missing Chromium, a
    failed navigation or a refused connection never sinks a run. Personal-use,
    low volume; respect each site's terms of service and robots.txt. Never a
    brute-force scraper.
    """

    name = "playwright"

    def __init__(self, urls: list[str] | None = None) -> None:
        super().__init__()
        self._urls = urls or SETTINGS.playwright_spa_urls

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        if not SETTINGS.playwright_enabled:
            self._last_error = _DISABLED_ERROR
            return []
        try:
            import playwright
        except ImportError as exc:
            self._last_error = f"playwright not installed: {type(exc).__name__}: {str(exc)[:200]}"
            return []
        return await self._render_and_parse(query, limit, locations)

    async def _render_and_parse(
        self, query: str, limit: int, locations: list[str] | None = None
    ) -> list[JobPosting]:
        from hireflow.tools.browser_launcher import stealth_browser, stealth_page

        jobs: list[JobPosting] = []
        try:
            async with stealth_browser() as browser:
                for url in self._urls:
                    try:
                        async with stealth_page(browser, locations) as page:
                            await page.goto(url, timeout=30000)
                            await page.wait_for_timeout(4000)
                            rows = await self._page_rows(page, url)
                    except Exception as exc:
                        self._last_error = f"{url}: {type(exc).__name__}: {str(exc)[:200]}"
                        continue
                    for row in rows:
                        job = self._parse_row(row)
                        if job.id and self._matches(job, query, ""):
                            jobs.append(job)
                    if len(jobs) >= limit:
                        break
        except Exception as exc:
            self._last_error = f"chromium launch failed: {type(exc).__name__}: {str(exc)[:200]}"
            return []
        return jobs[:limit]

    async def _page_rows(self, page: Any, url: str) -> list[dict[str, Any]]:
        scripts = await page.locator('script[type="application/ld+json"]').all_inner_texts()
        rows: list[dict[str, Any]] = []
        for script in scripts:
            try:
                payload = json.loads(script)
            except json.JSONDecodeError:
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if isinstance(item, dict) and self._is_job_posting(item):
                    rows.append(self._ld_row(item, url))
        if rows:
            return rows
        body = await page.locator("body").inner_text()
        title = await page.title()
        return [
            {
                "title": title or url,
                "url": url,
                "company": "",
                "location": "",
                "description": body[:4000],
            }
        ]

    def _parse_row(self, row: dict) -> JobPosting:
        return JobPosting(
            id=str(row.get("id", "") or row.get("url", "") or ""),
            source=self.name,
            title=str(row.get("title", "") or "").strip(),
            company=str(row.get("company", "") or "").strip(),
            location=str(row.get("location", "") or "").strip(),
            post_url=str(row.get("url", "") or ""),
            posted_at=self._parse_iso(row.get("posted_at")),
            raw_data=row,
        )

    @staticmethod
    def _is_job_posting(item: dict[str, Any]) -> bool:
        types = item.get("@type")
        if isinstance(types, list):
            return "JobPosting" in types
        return types == "JobPosting"

    @staticmethod
    def _ld_row(item: dict[str, Any], url: str) -> dict[str, Any]:
        location = ""
        base = item.get("jobLocation")
        if isinstance(base, dict):
            address = base.get("address")
            if isinstance(address, dict):
                location = " ".join(
                    part
                    for part in (
                        str(address.get("addressLocality", "") or ""),
                        str(address.get("addressRegion", "") or ""),
                        str(address.get("addressCountry", "") or ""),
                    )
                    if part
                )
        hiring = item.get("hiringOrganization")
        company = ""
        if isinstance(hiring, dict):
            company = str(hiring.get("name", "") or "")
        identifier = item.get("identifier")
        if isinstance(identifier, dict):
            identifier = identifier.get("value", "")
        return {
            "id": str(identifier or "") or url,
            "title": str(item.get("title", "") or "").strip(),
            "company": company,
            "location": location,
            "url": str(item.get("url", "") or "") or url,
            "posted_at": str(item.get("datePosted", "") or ""),
            "description": str(item.get("description", "") or "")[:4000],
        }