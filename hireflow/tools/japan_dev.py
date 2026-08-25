from __future__ import annotations

import httpx

from hireflow.domain import JobPosting
from hireflow.tools.job_source import USER_AGENT, JobSource
from hireflow.tools.jsonld import JsonLdSource


class JapanDevSource(JobSource):
    """Keyless Japan Dev (JP) job board for English-speaking tech roles.

    Intended route: ``https://japan-dev.com/jobs?q=...`` SSR HTML carrying
    ``application/ld+json`` ``JobPosting`` nodes. As of 2026-08-23 the SSR
    carries only WebSite/Organization JSON-LD — the actual job postings are
    embedded in a client-side Nuxt state blob — so this source is a
    best-effort tap: it walks any JSON-LD ``JobPosting`` found and otherwise
    degrades to ``[]``. Kept flag-gated (``USE_UNVERIFIED_SOURCES=1``) until a
    live-verified extraction path is confirmed. ``source="japan_dev"``.
    """

    name = "japan_dev"
    _url = "https://japan-dev.com/jobs"

    def _params(
        self,
        query: str,
        location: str,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> dict[str, str] | None:
        return {"q": query} if query else None

    def _parse_row(self, row: dict) -> JobPosting:
        posting = JsonLdSource._parse_posting(row)
        return posting if posting else JobPosting()

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        try:
            params = self._params(query, location, work_type=work_type, locations=locations)
            html = await self._fetch_html(self._url, params)
        except (httpx.HTTPError, ValueError) as exc:
            self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            return []
        jobs: list[JobPosting] = []
        for posting in JsonLdSource._extract_postings(html):
            job = JsonLdSource._parse_posting(posting)
            if not job or not job.title or not self._matches(job, query, ""):
                continue
            job.source = self.name
            jobs.append(job)
        return jobs[:limit]

    async def _fetch_html(self, url: str, params: dict[str, str]) -> str:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        return response.text