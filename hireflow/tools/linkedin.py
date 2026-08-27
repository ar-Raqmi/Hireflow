from __future__ import annotations

import asyncio
import re

import httpx

from hireflow.domain import JobPosting
from hireflow.tools.job_source import USER_AGENT, JobSource

_LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_LINKEDIN_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
_WORKPLACE_FILTER = {"remote": "2", "hybrid": "3", "onsite": "1"}
_CARD_RE = re.compile(
    r'data-entity-urn="urn:li:jobPosting:(?P<id>\d+)"'
    r'.*?base-card__full-link[^>]+href="(?P<url>[^"]+)"'
    r'.*?base-search-card__title[^>]*>(?P<title>.*?)</h3>'
    r'.*?base-search-card__subtitle[^>]*>(?P<company>.*?)</h4>'
    r'.*?job-search-card__location[^>]*>(?P<location>.*?)</span>',
    re.S,
)
_DETAIL_RE = re.compile(r'show-more-less-html__markup[^>]*>(.*?)</div>\s*(?:</div>|<div)', re.S)


class LinkedInSource(JobSource):
    """Keyless LinkedIn guest job search.

    Uses the unauthenticated ``jobs-guest`` endpoints. LinkedIn's ToS forbid
    scraping/automation, so this source is intentionally low-volume and
    personal-use only (small ``limit``, no aggressive paging, no distributed
    crawling). Marked soft-fail: if LinkedIn blocks (403/999) or a request
    errors, ``search`` returns ``[]`` and records ``last_error``.

    The guest HTML is shallow and stable: each result card carries the job id,
    title, company, location and a ``/jobs/view`` URL. A capped extra detail
    call per card recovers the description so the pipeline's work-type gate and
    matcher have context. https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<id>
    """

    name = "linkedin"
    _url = _LINKEDIN_SEARCH_URL
    _COOLDOWN_SECONDS = 180.0

    def __init__(self, limit: int = 10, detail: bool = True) -> None:
        super().__init__()
        self._cap = max(1, min(limit, 15))
        self._fetch_detail = detail
        self._cooldown_until = 0.0

    def _cooling_down(self) -> bool:
        return asyncio.get_event_loop().time() < self._cooldown_until

    def _trip_cooldown(self) -> None:
        self._cooldown_until = asyncio.get_event_loop().time() + self._COOLDOWN_SECONDS

    def _blocked_status(self, exc: httpx.HTTPError) -> bool:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", 0)
        return status in {403, 429, 999}

    def _parse_row(self, row: dict) -> JobPosting:
        return JobPosting(
            id=str(row.get("id", "")),
            source=self.name,
            title=str(row.get("title", "") or ""),
            company=str(row.get("company", "") or ""),
            location=str(row.get("location", "") or ""),
            post_url=str(row.get("post_url", "") or ""),
            raw_data=row,
        )

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        if self._cooling_down():
            self._last_error = "linkedin: cooling down after recent rate-limit"
            return []
        try:
            params = self._params(query, location, work_type=work_type, locations=locations)
            html = await self._fetch_html(self._url, params)
        except httpx.HTTPStatusError as exc:
            self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            if self._blocked_status(exc):
                self._trip_cooldown()
            return []
        except (httpx.HTTPError, ValueError) as exc:
            self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            return []
        jobs = [self._parse_card(card) for card in _CARD_RE.finditer(html)]
        jobs = [job for job in jobs if job.id and self._matches(job, query, "")]
        if self._fetch_detail:
            for job in jobs[: self._cap]:
                if self._cooling_down():
                    break
                await self._attach_description(job)
        return jobs[: min(limit, self._cap)]

    def _params(
        self,
        query: str,
        location: str,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> dict[str, str]:
        params: dict[str, str] = {"keywords": query or "", "start": "0"}
        preferred = locations or []
        if work_type in _WORKPLACE_FILTER:
            params["f_WT"] = _WORKPLACE_FILTER[work_type]
            if work_type == "remote" and not preferred:
                params["location"] = "remote"
        if preferred:
            params["location"] = preferred[0]
        return params

    async def _fetch_html(self, url: str, params: dict[str, str]) -> str:
        await asyncio.sleep(1.5)
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_card(match: re.Match) -> JobPosting:
        return JobPosting(
            id=match.group("id"),
            source="linkedin",
            title=re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group("title"))).strip(),
            company=re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group("company"))).strip(),
            location=re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group("location"))).strip(),
            post_url=match.group("url").replace("&amp;", "&").replace("&amp;", "&"),
            raw_data={},
        )

    async def _attach_description(self, job: JobPosting) -> None:
        try:
            html = await self._fetch_html(_LINKEDIN_DETAIL_URL.format(job_id=job.id), {})
        except httpx.HTTPStatusError as exc:
            self._last_error = f"detail {job.id}: {type(exc).__name__}: {str(exc)[:200]}"
            if self._blocked_status(exc):
                self._trip_cooldown()
            return
        except (httpx.HTTPError, ValueError) as exc:
            self._last_error = f"detail {job.id}: {type(exc).__name__}: {str(exc)[:200]}"
            return
        detail = _DETAIL_RE.search(html)
        description = ""
        if detail:
            description = re.sub(r"<[^>]+>", " ", detail.group(1))
            description = re.sub(r"\s+", " ", description).strip()
        job.raw_data["description"] = description
