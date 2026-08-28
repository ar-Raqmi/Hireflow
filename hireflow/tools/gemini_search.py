from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.gemini import GeminiClient

_AGO_RE = re.compile(r"(\d+)\s*(minute|hour|day|week|month)s?\s*ago")
_DATE_FORMATS = ("%b %d, %Y", "%b %d", "%d %b %Y", "%Y-%m-%d", "%m/%d/%Y")


def _parse_posted(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().lower()
    if not text or text == "unknown":
        return None
    now = datetime.now(timezone.utc)
    match = _AGO_RE.search(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        deltas = {
            "minute": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "month": timedelta(days=30 * amount),
        }
        return now - deltas[unit]
    if "today" in text or "just posted" in text:
        return now
    if "yesterday" in text:
        return now - timedelta(days=1)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.year == 1900:
            parsed = parsed.replace(year=now.year)
        return parsed.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class GeminiWebSearchSource:
    """Multi-angle Google Search grounded job discovery.

    Fires one grounded Gemini call per search angle (per role variant), in
    parallel, and extracts the real postings visible in Google's results into
    structured jobs (title, company, location, url, description snippet).
    Deduplicates across angles by title+company (grounding redirect URLs
    differ per query). Every step soft-fails to ``[]`` with ``last_error``.
    Discovered jobs carry ``source="gemini_web"``.
    """

    name = "gemini_web"

    def __init__(self, gemini: GeminiClient, max_jobs: int | None = None) -> None:
        self._gemini = gemini
        self._max_jobs = max(4, max_jobs or SETTINGS.web_discovery_max_links)
        self._max_calls = max(1, SETTINGS.web_discovery_max_calls)
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
        queries: list[str] | None = None,
    ) -> list[JobPosting]:
        self._last_error = None
        role = (query or "").strip() or "software engineer"
        preferred = self._preferred_locations(location, locations)
        loc = ", ".join(preferred)
        if queries:
            base_terms = [q for q in (q.strip() for q in queries) if q]
            terms = [f"{term} jobs {loc}" if loc else term for term in base_terms]
        else:
            terms = [self._query(role, loc) for loc in preferred] or [self._query(role, "")]
        selected = [t for t in (t.strip() for t in terms) if t][: self._max_calls]
        outcomes = await asyncio.gather(
            *(self._grounded_jobs_safe(term) for term in selected),
            return_exceptions=False,
        )
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        for rows in outcomes:
            for row in rows:
                job = self._to_posting(row)
                if job is None:
                    continue
                key = str(job.raw_data.get("dedupe_key") or job.id)
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(job)
        jobs.sort(key=lambda j: 0, reverse=True)
        self._last_summary = (
            f"{len(jobs)} jobs grounded from Google across {len(selected)} search angles"
        )
        return jobs[:limit]

    async def _grounded_jobs_safe(self, term: str) -> list[dict]:
        try:
            return await self._gemini.grounded_jobs(term)
        except Exception as exc:
            self._last_error = f"search {term[:60]}: {type(exc).__name__}: {str(exc)[:200]}"
            return []

    def _to_posting(self, row: dict) -> JobPosting | None:
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url.startswith(("http://", "https://")):
            return None
        company = str(row.get("company") or "").strip()
        location = str(row.get("location") or "").strip()
        description = str(row.get("description") or "").strip()
        posted_raw = str(row.get("posted") or "").strip()
        posted_at = _parse_posted(posted_raw)
        dedupe_key = f"{title.lower()}|{company.lower()}"
        digest = hashlib.sha1(f"{dedupe_key}|{url}".encode()).hexdigest()[:12]
        return JobPosting(
            id=f"{title.lower().replace(' ', '-')}-{digest}",
            source="gemini_web",
            title=title,
            company=company,
            location=location,
            post_url=url,
            posted_at=posted_at,
            raw_data={
                "gemini_web": True,
                "description": description,
                "dedupe_key": dedupe_key,
                "posted_seen": posted_raw or "unknown",
            },
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
