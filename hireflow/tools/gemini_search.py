from __future__ import annotations

from urllib.parse import urlsplit

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.webfetch import WebFetchSource


class GeminiWebSearchSource:
    """Google Search grounded job discovery via Gemini.

    Runs a role+location query through Gemini with Google Search grounding
    enabled (``GeminiClient.grounded_search``) to get real, current source
    URLs, then turns each URL into jobs via ``WebFetchSource.fetch_url``.
    Replaces the fragile keyless DuckDuckGo scrape (which got rate-limited).
    Every step soft-fails to ``[]`` with ``last_error`` set - it never raises.
    Discovered jobs carry ``source="gemini_web"``.
    """

    name = "gemini_web"

    def __init__(
        self,
        gemini: GeminiClient,
        fetcher: WebFetchSource | None = None,
        max_links: int | None = None,
    ) -> None:
        self._gemini = gemini
        self._fetcher = fetcher or WebFetchSource(timeout=SETTINGS.web_fetch_timeout)
        self._max_links = max(4, max_links or SETTINGS.web_discovery_max_links)
        self._last_error: str | None = None
        self._last_summary: str = ""

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def last_summary(self) -> str:
        return self._last_summary

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        self._last_error = None
        role = (query or "").strip() or "software engineer"
        preferred = self._preferred_locations(location, locations)
        terms = [self._query(role, loc) for loc in preferred] or [self._query(role, "")]
        urls = await self._search_urls(terms)
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        for url in urls[: self._max_links]:
            try:
                found = await self._fetcher.fetch_url(url, query_hint=role)
            except Exception as exc:
                self._last_error = f"fetch {url}: {type(exc).__name__}: {str(exc)[:200]}"
                found = []
            for job in found:
                job.source = "gemini_web"
                if not job.id or job.id in seen:
                    continue
                seen.add(job.id)
                jobs.append(job)
        self._last_summary = (
            f"{len(jobs)} found via Google Search grounding ({len(urls)} URLs)"
            if urls
            else "0 found via Google Search grounding"
        )
        return jobs[:limit]

    async def _search_urls(self, terms: list[str]) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for term in terms:
            try:
                results = await self._gemini.grounded_search(term)
            except Exception as exc:
                self._last_error = f"search {term[:60]}: {type(exc).__name__}: {str(exc)[:200]}"
                continue
            for item in results:
                target = (item.get("uri") or "").strip()
                if not target.startswith(("http://", "https://")):
                    continue
                if target in seen:
                    continue
                seen.add(target)
                urls.append(target)
            if len(urls) >= self._max_links:
                break
        return urls

    @classmethod
    def _preferred_locations(cls, location: str, locations: list[str] | None) -> list[str]:
        preferred: list[str] = []
        for part in locations or []:
            part = part.strip()
            if part and part not in preferred:
                preferred.append(part)
        if location:
            for part in (p.strip() for p in location.split(",")):
                if part and part not in preferred:
                    preferred.append(part)
        return preferred

    @classmethod
    def _query(cls, role: str, location: str) -> str:
        base = f"{role} jobs {location}".strip()
        return base if location else f"{role} jobs"
