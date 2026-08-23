from __future__ import annotations

import os
from typing import Any

from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource

_PLAYWRIGHT_ENABLED = os.getenv("HIREFLOW_PLAYWRIGHT", "").strip().lower() in {
    "1",
    "true",
    "yes",
}
_NO_OP_ERROR = "Playwright source disabled (set HIREFLOW_PLAYWRIGHT=1 and bundle Chromium)"


class PlaywrightSource(JobSource):
    """Layer II browser-automation source (last resort, opt-in).

    Wraps ``playwright.async_api`` so a JS-heavy SPA career page that exposes
    neither a public API nor JSON-LD can still be rendered and read. This is
    explicitly NOT a default path: it is a heavy, slow fallback for the
    long-tail, gated behind ``HIREFLOW_PLAYWRIGHT=1``. When disabled the source
    is a no-op returning ``[]`` with ``last_error`` set.

    Chromium must be present in the Cloud Run image for this to ever activate.
    Deploy wiring is a documented TODO (Dockerfile change) — the class itself is
    a scaffold so the pipeline shape stays unchanged when it is enabled.
    """

    name = "playwright"

    def __init__(self, urls: list[str] | None = None) -> None:
        super().__init__()
        self._urls = urls or []

    def _parse_row(self, row: dict) -> JobPosting:
        return JobPosting(source=self.name, raw_data=row)

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        if not _PLAYWRIGHT_ENABLED:
            self._last_error = _NO_OP_ERROR
            return []
        try:
            from playwright.async_api import async_playwright  # local import
        except ImportError as exc:
            self._last_error = f"playwright not installed: {type(exc).__name__}: {str(exc)[:200]}"
            return []
        return await self._render_and_parse(query, limit)

    async def _render_and_parse(self, query: str, limit: int) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for url in self._urls:
                    page = await browser.new_page()
                    try:
                        await page.goto(url, timeout=20000)
                        await page.wait_for_timeout(3000)
                        text = await page.locator("body").inner_text()
                        title = await page.title()
                    except Exception as exc:  # noqa: BLE001 - a page failing is non-fatal
                        self._last_error = f"{url}: {type(exc).__name__}: {str(exc)[:200]}"
                        await page.close()
                        continue
                    job = JobPosting(
                        id=url,
                        source=self.name,
                        title=title or url,
                        company="",
                        location="",
                        post_url=url,
                        raw_data={"description": text[:2000]},
                    )
                    if self._matches(job, query, ""):
                        jobs.append(job)
                    await page.close()
            finally:
                await browser.close()
        return jobs[:limit]