from __future__ import annotations

import json
import re
from typing import Any, Iterable

import httpx

from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource

_LD_SCRIPT_RE = re.compile(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


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
        for posting in self._extract_postings(html):
            job = self._parse_posting(posting)
            if job and job.title and self._matches(job, query, ""):
                jobs.append(job)
        return jobs[:limit]

    async def _fetch_html(self, url: str, params: dict[str, str]) -> str:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": _USER_AGENT}) as client:
            response = await client.get(url, params=params)
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
    def _string(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _posting_url(posting: dict[str, Any]) -> str:
        for key in ("sameAs", "url", "id"):
            value = posting.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        return ""

    def _parse_posting(self, posting: dict[str, Any]) -> JobPosting | None:
        title = self._string(posting.get("title"))
        if not title:
            return None
        org = posting.get("hiringOrganization") or {}
        company = self._string(org.get("name")) if isinstance(org, dict) else self._string(org)
        address = posting.get("jobLocation") or {}
        if isinstance(address, dict):
            address = address.get("address") or address
        if isinstance(address, dict):
            parts = [
                self._string(address.get("addressLocality")),
                self._string(address.get("addressRegion")),
                self._string(address.get("addressCountry")),
            ]
            location = ", ".join(part for part in parts if part)
        else:
            location = self._string(address)
        return JobPosting(
            id=self._posting_url(posting) or title,
            source=self.name,
            title=title,
            company=company,
            location=location,
            post_url=self._posting_url(posting),
            posted_at=self._parse_iso(posting.get("datePosted")),
            raw_data={"description": self._string(posting.get("description"))},
        )