from __future__ import annotations

import json
import re
from typing import Any, Iterable

import httpx

from hireflow.domain import JobPosting
from hireflow.tools.job_source import USER_AGENT, JobSource

_LD_SCRIPT_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S
)

class JsonLdSource(JobSource):
    """Career-page source built on schema.org ``JobPosting`` JSON-LD.

    Given a list of company career-page URLs, fetches each page, regexes out
    ``<script type="application/ld+json">`` blocks, and turns any
    ``JobPosting`` node into a ``JobPosting``. Pages without JSON-LD or that
    block the request degrade to ``[]`` (recorded in ``last_error``) - a page
    with no structured data simply contributes nothing.

    Scope is intentionally narrow: this is the "career page tap" layer for
    companies that expose structured job data without a public API. The URL
    list is constructor-injected so config owns the registry; nothing here
    invents coverage that a live ``curl`` has not confirmed.
    """

    name = "jsonld"

    def __init__(self, urls: list[str] | None = None) -> None:
        super().__init__()
        self._urls = urls or []

    def _parse_row(self, row: dict) -> JobPosting:
        return self._parse_posting(row) or JobPosting(source=self.name)

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for url in self._urls:
            try:
                html = await self._fetch_html(url)
            except (httpx.HTTPError, ValueError) as exc:
                self._last_error = f"{url}: {type(exc).__name__}: {str(exc)[:200]}"
                continue
            for posting in self._extract_postings(html):
                job = self._parse_posting(posting)
                if job and job.title and self._matches(job, query, ""):
                    jobs.append(job)
        return jobs[:limit]

    async def _fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        return response.text

    @classmethod
    def _extract_postings(cls, html: str) -> Iterable[dict[str, Any]]:
        for block in _LD_SCRIPT_RE.findall(html):
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, ValueError):
                continue
            yield from cls._walk(data)

    @classmethod
    def _walk(cls, node: Any) -> Iterable[dict[str, Any]]:
        if isinstance(node, dict):
            if cls._is_posting(node):
                yield node
                return
            for value in node.values():
                yield from cls._walk(value)
        elif isinstance(node, list):
            for item in node:
                yield from cls._walk(item)

    @staticmethod
    def _is_posting(node: dict[str, Any]) -> bool:
        type_ = node.get("@type")
        if isinstance(type_, str):
            return type_ == "JobPosting"
        if isinstance(type_, list):
            return "JobPosting" in type_
        return False

    @staticmethod
    def _posting_url(posting: dict[str, Any]) -> str:
        for key in ("sameAs", "url", "id"):
            value = posting.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        return ""

    @classmethod
    def _parse_posting(cls, posting: dict[str, Any]) -> JobPosting | None:
        title = cls._string(posting.get("title"))
        if not title:
            return None
        org = posting.get("hiringOrganization") or {}
        if isinstance(org, dict):
            company = cls._string(org.get("name"))
        else:
            company = cls._string(org)
        address = posting.get("jobLocation") or {}
        if isinstance(address, dict):
            address = address.get("address") or address
        if isinstance(address, dict):
            locality = cls._string(address.get("addressLocality"))
            region = cls._string(address.get("addressRegion"))
            country = cls._string(address.get("addressCountry"))
            location = ", ".join(part for part in (locality, region, country) if part)
        else:
            location = cls._string(address)
        return JobPosting(
            id=cls._posting_url(posting) or cls._string(posting.get("title")),
            source="jsonld",
            title=title,
            company=company,
            location=location,
            post_url=cls._posting_url(posting),
            posted_at=cls._parse_iso(posting.get("datePosted")),
            raw_data={"description": cls._string(posting.get("description"))},
        )

    @staticmethod
    def _string(value: Any) -> str:
        return str(value or "").strip()
