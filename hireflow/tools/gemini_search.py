from __future__ import annotations

import hashlib

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.gemini import GeminiClient


class GeminiWebSearchSource:
    """Google Search grounded job discovery via Gemini.

    One grounded generate_content per query: Gemini searches Google for the
    role+location and extracts the real postings visible in its results into
    structured jobs (title, company, location, url) via
    ``GeminiClient.grounded_jobs``. This replaces the fetch-the-landing-page
    approach - grounding returns listing pages that no parser could turn into
    single postings. Every step soft-fails to ``[]`` with ``last_error`` set.
    Discovered jobs carry ``source="gemini_web"``.
    """

    name = "gemini_web"

    def __init__(self, gemini: GeminiClient, max_jobs: int | None = None) -> None:
        self._gemini = gemini
        self._max_jobs = max(4, max_jobs or SETTINGS.web_discovery_max_links)
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
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        for term in terms:
            try:
                rows = await self._gemini.grounded_jobs(term)
            except Exception as exc:
                self._last_error = f"search {term[:60]}: {type(exc).__name__}: {str(exc)[:200]}"
                continue
            for row in rows:
                job = self._to_posting(row)
                if job is None or job.id in seen:
                    continue
                seen.add(job.id)
                jobs.append(job)
            if len(jobs) >= self._max_jobs:
                break
        self._last_summary = f"{len(jobs)} found via Google Search grounding"
        return jobs[:limit]

    def _to_posting(self, row: dict) -> JobPosting | None:
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url.startswith(("http://", "https://")):
            return None
        company = str(row.get("company") or "").strip()
        location = str(row.get("location") or "").strip()
        description = str(row.get("description") or "").strip()
        digest = hashlib.sha1(f"{url}|{title}|{company}".encode()).hexdigest()[:12]
        return JobPosting(
            id=f"{title.lower().replace(' ', '-')}-{digest}",
            source="gemini_web",
            title=title,
            company=company,
            location=location,
            post_url=url,
            raw_data={"gemini_web": True, "description": description},
        )

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
        return f"{role} jobs {location}".strip()
