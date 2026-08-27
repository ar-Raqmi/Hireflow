from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

import httpx

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.webfetch import WebFetchSource
from hireflow.tools.job_source import USER_AGENT

_DDG_LINK_RE = re.compile(r'<a\b[^>]*rel="nofollow"[^>]*href="([^"]+)"', re.I)
_UDDG_RE = re.compile(r"[?&]uddg=([^&\s'\"]+)")
_DEFAULT_ENDPOINT = "https://lite.duckduckgo.com/lite/"
_LOCATION_HINTS: dict[str, tuple[str, ...]] = {
    "malaysia": ("jobstreet.com.my",),
    "my": ("jobstreet.com.my",),
    "singapore": ("jobstreet.com.sg",),
    "sg": ("jobstreet.com.sg",),
    "indonesia": ("kalibrr.com",),
    "id": ("kalibrr.com",),
    "philippines": ("kalibrr.com",),
    "ph": ("kalibrr.com",),
    "japan": ("wantedly.com",),
    "jp": ("wantedly.com",),
    "united kingdom": ("reed.co.uk",),
    "uk": ("reed.co.uk",),
    "gb": ("reed.co.uk",),
}


class WebDiscoverySource:
    """Keyless web discovery layer - finds candidate job URLs, then webfetches.

    Given a role + preferred locations, runs a keyless HTML search
    (DuckDuckGo Lite - curl-verified 200 + parseable this session) and turns
    the organic result links into jobs via ``WebFetchSource``. Site hints are
    per-location best-effort (e.g. ``site:jobstreet.com.my`` for MY) - there is
    no global 50-domain whitelist, and an unknown location simply searches
    ``"{role} jobs {location}"``. An explicit per-run ``companies`` list is
    probed via ``WebFetchSource.webfetch_company``. Every step soft-fails:
    a blocked search or unparseable page contributes nothing and is recorded in
    ``last_error``. Discovered jobs carry ``source="web"``.
    """

    name = "web"

    def __init__(
        self,
        fetcher: WebFetchSource | None = None,
        endpoint: str | None = None,
        max_links: int | None = None,
        companies: list[str] | None = None,
        timeout: float | None = None,
    ) -> None:
        self._fetcher = fetcher or WebFetchSource(timeout=timeout)
        self._endpoint = endpoint or SETTINGS.web_search_endpoint or _DEFAULT_ENDPOINT
        self._max_links = max(4, max_links or SETTINGS.web_discovery_max_links)
        self._companies = companies if companies is not None else SETTINGS.web_discovery_companies
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
        companies: list[str] | None = None,
    ) -> list[JobPosting]:
        self._last_error = None
        role = (query or "").strip() or "software engineer"
        preferred = self._preferred_locations(location, locations)
        terms = [self._query(role, loc) for loc in preferred] or [self._query(role, "")]
        candidate_urls = await self._search_links(terms, limit=min(limit, self._max_links))

        print(f"[WEB DEBUG] search terms: {terms}")
        print(f"[WEB DEBUG] candidate URLs ({len(candidate_urls)}): {candidate_urls}")
        
        jobs, seen = await self._collect(candidate_urls, role, seen=set())
        company_names = companies if companies is not None else self._companies
        jobs, seen = await self._collect(
            [], role, seen=seen, company_names=company_names, preferred=preferred
        )
        self._last_summary = self._summarize(jobs, candidate_urls, company_names)
        return jobs[:limit]

    async def _collect(
        self,
        urls: list[str],
        role: str,
        seen: set[str],
        company_names: list[str] | None = None,
        preferred: list[str] | None = None,
    ) -> tuple[list[JobPosting], set[str]]:
        jobs: list[JobPosting] = []
        for url in urls:
            try:
                found = await self._fetcher.fetch_url(url, query_hint=role)
            except Exception as exc:
                self._last_error = f"fetch {url}: {type(exc).__name__}: {str(exc)[:200]}"
                found = []
            for job in found:
                job.source = "web"
                if not job.id or job.id in seen:
                    continue
                seen.add(job.id)
                jobs.append(job)
        for company in company_names or []:
            try:
                found = await self._fetcher.webfetch_company(company, preferred, role)
            except Exception as exc:
                self._last_error = f"company {company}: {type(exc).__name__}: {str(exc)[:200]}"
                found = []
            for job in found:
                job.source = "web"
                if not job.id or job.id in seen:
                    continue
                seen.add(job.id)
                jobs.append(job)
        return jobs, seen

    async def _search_links(self, terms: list[str], limit: int) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for term in terms:
            try:
                async with httpx.AsyncClient(
                    timeout=15.0,
                    headers={"User-Agent": USER_AGENT},
                    follow_redirects=True,
                ) as client:
                    response = await client.get(self._endpoint, params={"q": term})
            except (httpx.HTTPError, ValueError) as exc:
                self._last_error = f"search {term[:60]}: {type(exc).__name__}: {str(exc)[:200]}"
                continue
            if response.status_code != 200:
                self._last_error = f"search {term[:60]}: HTTP {response.status_code}"
                continue
            for target in self._decode_links(response.text):
                if target in seen:
                    continue
                seen.add(target)
                links.append(target)
            if len(links) >= limit:
                break
        return links[:limit]

    @classmethod
    def _decode_links(cls, html: str) -> list[str]:
        links: list[str] = []
        for href in _DDG_LINK_RE.findall(html):
            match = _UDDG_RE.search(href)
            target = unquote(match.group(1)) if match else href
            target = target.replace("&amp;", "&")
            if not target.startswith(("http://", "https://")):
                continue
            if "duckduckgo.com" in urlsplit(target).netloc.lower():
                continue
            if target not in links:
                links.append(target)
        return links

    @classmethod
    def _preferred_locations(cls, location: str, locations: list[str] | None) -> list[str]:
        preferred: list[str] = []
        for part in (locations or []):
            part = part.strip()
            if part and part not in preferred:
                preferred.append(part)
        if location:
            for part in (part.strip() for part in location.split(",")):
                if part and part not in preferred:
                    preferred.append(part)
        return preferred

    @classmethod
    def _query(cls, role: str, location: str) -> str:
        base = f"{role} jobs {location}".strip()
        hints = cls._site_hints(location)
        if hints:
            clause = " OR ".join([f"site:{hint}" for hint in hints] + ["careers"])
            return f"{base} ({clause})"
        return base

    @classmethod
    def _site_hints(cls, location: str) -> list[str]:
        token = (location or "").strip().lower()
        if not token:
            return []
        for key, hints in _LOCATION_HINTS.items():
            if key == token or key in token or token in key:
                return list(hints)
        return []

    def _summarize(
        self, jobs: list[JobPosting], links: list[str], companies: list[str] | None
    ) -> str:
        if jobs:
            where = []
            if links:
                where.append("keyless search")
            if companies:
                where.append("careers pages")
            return f"{len(jobs)} found via {' + '.join(where)}"
        if links:
            return "0 found via keyless search"
        if companies:
            return "0 found via careers pages"
        return "0 found (web search unavailable)"
