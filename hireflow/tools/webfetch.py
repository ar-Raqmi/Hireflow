from __future__ import annotations

import hashlib
import html as html_module
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.ats import AtsBoardSource
from hireflow.tools.jsonld import JsonLdSource

_LD_SCRIPT_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S
)
_ANCHOR_RE = re.compile(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.I | re.S)
_CARD_RE = re.compile(
    r"<(article|li|div)\b[^>]*\b(?:class|data-qa)=\"[^\"]*(?:job[-_]?(?:card|result|listing|post))[^\"]*\"[^>]*>(.*?)</\1>",
    re.I | re.S,
)
_HEADING_RE = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.I | re.S)
_RELATIVE_DATE_RE = re.compile(
    r"(\d+)\s*(minute|hour|day|week|month|year)s?\s+ago", re.I
)
_MONTH_DAY_RE = re.compile(
    r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I
)
_DAY_MONTH_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", re.I
)
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_ATS_API = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{name}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{name}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{name}",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{name}",
}
_ATS_HOSTS = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
    "apply.workable.com": "workable",
}
_COMPANY_STOPWORDS = {
    "apply", "apply now", "view job", "view", "see all jobs", "see jobs",
    "learn more", "more jobs", "similar jobs", "jobs", "all jobs", "open jobs",
    "search jobs", "browse jobs", "read more", "share", "save", "bookmark",
    "hide this job", "hide", "saved", "company", "the company",
}


class WebFetchSource:
    """Universal URL extractor — any URL becomes jobs, no domain whitelist.

    Given any company/job page URL, tries, in order: schema.org ``JobPosting``
    JSON-LD (reusing ``JsonLdSource``), ATS board detection (Greenhouse / Lever /
    Ashby / Workable via their public unauthenticated APIs), then a tolerant
    generic HTML card parse (title / detail links / meta). Every step soft-fails
    to ``[]`` with ``last_error`` set — a page that yields nothing never raises
    and never sinks a run. ``source`` is ``webfetch`` (plus ``raw_data
    ["webfetch_via"]`` = ``jsonld`` | ``ats:<kind>`` | ``html`` | ``none``).
    """

    name = "webfetch"

    def __init__(self, timeout: float | None = None) -> None:
        self._timeout = timeout if timeout is not None else SETTINGS.web_fetch_timeout
        self._last_error: str | None = None
        self._last_via: str = "none"

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def last_via(self) -> str:
        return self._last_via

    async def fetch_url(self, url: str, query_hint: str = "") -> list[JobPosting]:
        if not SETTINGS.web_fetch_enabled:
            self._last_error = "webfetch disabled (set WEB_FETCH=1 to enable)"
            self._last_via = "none"
            return []
        self._last_error = None
        try:
            html = await self._fetch_html(url)
        except Exception as exc:  # noqa: BLE001 - a blocked page must never raise
            self._last_error = f"{url}: {type(exc).__name__}: {str(exc)[:200]}"
            self._last_via = "none"
            return []
        return await self._extract(url, html, query_hint)

    async def webfetch_company(
        self,
        company_name: str,
        locations: list[str] | None = None,
        query: str = "",
        tries: int = 4,
    ) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        for url in self._company_candidates(company_name)[:tries]:
            for job in await self.fetch_url(url, query_hint=query):
                if not job.id or job.id in seen:
                    continue
                seen.add(job.id)
                jobs.append(job)
        return jobs

    async def _fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": _USER_AGENT}
        ) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        return response.text

    def _company_candidates(self, company_name: str) -> list[str]:
        slug = re.sub(r"[^a-z0-9]+", "-", (company_name or "").strip().lower()).strip("-")
        if not slug:
            return []
        return [
            f"https://{slug}.com/careers",
            f"https://www.{slug}.com/careers",
            f"https://boards.greenhouse.io/{slug}",
            f"https://jobs.ashbyhq.com/{slug}",
            f"https://apply.workable.com/{slug}",
            f"https://jobs.lever.co/{slug}",
        ]

    async def _extract(self, url: str, html: str, query: str) -> list[JobPosting]:
        postings: list[JobPosting] = []
        for raw in JsonLdSource._extract_postings(html):
            job = JsonLdSource._parse_posting(raw)
            if job and job.title:
                postings.append(self._normalize(job, "jsonld"))
        if postings:
            self._last_via = "jsonld"
            return postings
        ats = self._detect_ats(url)
        if ats is not None:
            kind, name = ats
            postings = await self._fetch_ats(kind, name)
            if postings:
                self._last_via = f"ats:{kind}"
                return postings
        postings = self._parse_html(url, html, query)
        self._last_via = "html" if postings else "none"
        return postings

    def _normalize(self, job: JobPosting, via: str) -> JobPosting:
        job.source = "webfetch"
        if not job.id:
            job.id = self._derive_id(job.post_url or "", job.title)
        if not job.post_url:
            job.post_url = job.id if job.id.startswith("http") else ""
        raw = dict(job.raw_data or {})
        raw["webfetch_via"] = via
        job.raw_data = raw
        return job

    @staticmethod
    def _detect_ats(url: str) -> tuple[str, str] | None:
        parts = urlsplit(url)
        host = (parts.netloc or "").lower()
        kind: str | None = None
        for suffix, ats_kind in _ATS_HOSTS.items():
            if host == suffix or host.endswith("." + suffix):
                kind = ats_kind
                break
        if kind is None:
            return None
        segments = [segment for segment in parts.path.split("/") if segment]
        if not segments:
            return None
        first = segments[0].lower()
        if first in {"api", "widget", "j", "jobs", "careers", "posting-api"}:
            return None
        return (kind, segments[0])

    async def _fetch_ats(self, kind: str, name: str) -> list[JobPosting]:
        try:
            url = _ATS_API[kind].format(name=name)
            async with httpx.AsyncClient(
                timeout=self._timeout, headers={"User-Agent": _USER_AGENT}
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self._last_error = f"{kind}:{name}: {type(exc).__name__}: {str(exc)[:200]}"
            return []
        parser = AtsBoardSource()
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        for row in self._ats_rows(kind, payload):
            job = parser._parse(kind, row)
            if not job or not job.id or job.id in seen:
                continue
            seen.add(job.id)
            jobs.append(self._normalize(job, f"ats:{kind}"))
        return jobs

    @staticmethod
    def _ats_rows(kind: str, payload: Any) -> list[Any]:
        if isinstance(payload, dict):
            rows = payload.get("jobs", [])
            return rows if isinstance(rows, list) else []
        if kind == "lever" and isinstance(payload, list):
            return payload
        return []

    def _parse_html(self, url: str, html: str, query: str) -> list[JobPosting]:
        postings: list[JobPosting] = []
        for match in _CARD_RE.finditer(html):
            job = self._parse_card(url, match.group(2), query)
            if job is not None:
                postings.append(job)
        postings = self._dedupe(postings)
        if postings:
            return postings
        meta = self._parse_meta(url, html)
        return [meta] if meta is not None else []

    def _parse_card(self, url: str, body: str, query: str) -> JobPosting | None:
        anchors = [
            (href.replace("&amp;", "&"), self._clean_text(text))
            for href, text in _ANCHOR_RE.findall(body)
        ]
        title = ""
        detail = ""
        marked = re.search(r'data-qa="job-card-title"[^>]*>(.*?)<', body, re.S | re.I)
        if marked:
            title = self._clean_text(marked.group(1))
        for href, text in anchors:
            if self._is_job_detail(href):
                if not detail:
                    detail = urljoin(url, href)
                if not title and text:
                    title = text
        if not title:
            for href, text in anchors:
                if self._is_job_href(href) and not title and text:
                    title = text
        if not title:
            heading = _HEADING_RE.search(body)
            if heading:
                title = self._clean_text(heading.group(1))
        if not title:
            return None
        return JobPosting(
            id=detail or self._derive_id(url, title),
            source="webfetch",
            title=title[:180],
            company=self._parse_company(body, title) or "",
            location=self._parse_location(body) or "",
            post_url=detail or url,
            posted_at=self._parse_posted_at(body),
            raw_data={
                "description": self._clean_text(re.sub(r"<[^>]+>", " ", body))[:600],
                "webfetch_via": "html",
            },
        )

    def _parse_company(self, body: str, title: str) -> str | None:
        for pattern in (
            r'data-qa="[^"]*company[^"]*"[^>]*>(.*?)</(?:li|div|span|p|article|a)>',
            r'data-qa="job-posted-by[^"]*"[^>]*>(.*?)</(?:li|div|span|p|article)>',
            r'class="[^"]*company[^"]*"[^>]*>(.*?)</(?:li|div|span|p|article)>',
            r'class="[^"]*org[^"]*"[^>]*>(.*?)</(?:li|div|span|p|article)>',
        ):
            match = re.search(pattern, body, re.I | re.S)
            if not match:
                continue
            captured = match.group(1)
            anchor = re.search(r'<a\b[^>]*>(.*?)</a>', captured, re.S | re.I)
            text = self._clean_text(anchor.group(1) if anchor else captured)
            text = re.sub(r"^(?:posted|by|at)\s*:?\s*", "", text, flags=re.I).strip()
            if text:
                return text[:80]
        title_lower = title.strip().lower()
        fallback: str | None = None
        for href, text in _ANCHOR_RE.findall(body):
            text = self._clean_text(text)
            if not text or len(text) > 48:
                continue
            lowered = text.lower()
            if lowered == title_lower or lowered in _COMPANY_STOPWORDS:
                continue
            if any(marker in lowered for marker in ("job", "hide", "view", "share", "save")):
                continue
            if self._is_job_detail(href):
                continue
            fallback = text
            break
        if fallback:
            return fallback[:80]
        match = re.search(r"\b(?:by|at)\s+([A-Z][A-Za-z0-9&.'-]{1,39})", self._clean_text(body))
        if match and match.group(1).lower() not in title_lower:
            return match.group(1)
        return None

    def _parse_location(self, body: str) -> str | None:
        for pattern in (
            r'data-qa="[^"]*location[^"]*"[^>]*>(.*?)</(?:li|div|span|p|article|td)>',
            r'class="[^"]*location[^"]*"[^>]*>(.*?)</(?:li|div|span|p|article|td)>',
        ):
            match = re.search(pattern, body, re.I | re.S)
            if match:
                text = self._clean_text(match.group(1))
                if text:
                    return text[:120]
        return None

    def _parse_posted_at(self, body: str) -> datetime | None:
        lowered = body.lower()
        if "today" in lowered:
            return self._utcnow()
        if "yesterday" in lowered:
            return self._utcnow() - timedelta(days=1)
        match = _RELATIVE_DATE_RE.search(lowered)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            return self._utcnow() - self._delta(unit, amount)
        match = _MONTH_DAY_RE.search(lowered)
        if match:
            return self._month_day(int(match.group(1)), _MONTHS_SHORT[match.group(2)])
        match = _DAY_MONTH_RE.search(lowered)
        if match:
            return self._month_day(int(match.group(2)), _MONTHS_SHORT[match.group(1)])
        return None

    def _parse_meta(self, url: str, html: str) -> JobPosting | None:
        title = self._meta(html, "og:title") or self._meta(html, "twitter:title")
        if not title:
            return None
        detail = self._meta(html, "og:url") or url
        if not (self._is_job_detail(detail) or self._is_job_detail(url)):
            return None
        description = self._meta(html, "og:description") or self._meta(html, "twitter:description")
        return JobPosting(
            id=detail,
            source="webfetch",
            title=title[:180],
            company=self._meta(html, "og:site_name") or "",
            location="",
            post_url=detail,
            raw_data={
                "description": description[:600],
                "webfetch_via": "html",
            },
        )

    @staticmethod
    def _meta(html: str, key: str) -> str:
        for pattern in (
            r'<meta\b[^>]*?(?:property|name)=["\']%s["\'][^>]*?(?:content|value)=["\']([^"\']*)["\']'
            % re.escape(key),
            r'<meta\b[^>]*?(?:content|value)=["\']([^"\']*)["\'][^>]*?(?:property|name)=["\']%s["\']'
            % re.escape(key),
        ):
            match = re.search(pattern, html, re.I)
            if match:
                return html_module.unescape(match.group(1)).strip()
        return ""

    @staticmethod
    def _is_job_href(href: str) -> bool:
        lowered = href.lower().split("?")[0].rstrip("/")
        return bool(re.search(r"/(?:jobs|job|positions?|careers)/", lowered)) or lowered.endswith(
            ("/jobs", "/job", "/positions", "/careers")
        )

    @staticmethod
    def _is_job_detail(href: str) -> bool:
        lowered = href.lower().split("?")[0].rstrip("/")
        if not re.search(r"/(?:jobs|job|positions?|careers)/", lowered):
            return False
        last = lowered.rsplit("/", 1)[-1]
        return bool(last) and last.isdigit()

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(re.sub(r"<[^>]+>", " ", value or "").split())

    @staticmethod
    def _derive_id(url: str, title: str = "") -> str:
        material = f"{url}|{title}".encode("utf-8", "ignore")
        return hashlib.sha1(material).hexdigest()[:16]

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _delta(unit: str, amount: int) -> timedelta:
        return {
            "minute": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "month": timedelta(days=30 * amount),
            "year": timedelta(days=365 * amount),
        }.get(unit, timedelta(0))

    @staticmethod
    def _month_day(day: int, month: int) -> datetime | None:
        now = datetime.now(timezone.utc)
        try:
            when = datetime(now.year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
        if when > now:
            when = when.replace(year=now.year - 1)
        return when

    @staticmethod
    def _dedupe(jobs: list[JobPosting]) -> list[JobPosting]:
        seen: set[str] = set()
        unique: list[JobPosting] = []
        for job in jobs:
            if not job.id or job.id in seen:
                continue
            seen.add(job.id)
            unique.append(job)
        return unique


_MONTHS_SHORT = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}