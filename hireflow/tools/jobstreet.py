from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.geo import LocationMapper
from hireflow.tools.job_source import JobSource

_COUNTRY_SUBDOMAINS = {
    "my": "my.jobstreet.com",
    "sg": "sg.jobstreet.com",
    "id": "id.jobstreet.com",
    "ph": "ph.jobstreet.com",
    "th": "th.jobstreet.com",
    "vn": "vn.jobstreet.com",
}
_DEFAULT_SUBDOMAIN = _COUNTRY_SUBDOMAINS["my"]

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_JOB_ID_RE = re.compile(r"/job/(\d+)")
_UNIT_DAYS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TEN_DAYS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
_WORK_TYPES = frozenset({"remote", "hybrid", "onsite"})
_WORK_ALIASES = {"work from home": "remote", "on-site": "onsite", "on site": "onsite"}
_DURATION_WORDS = frozenset(
    {"day", "days", "week", "weeks", "month", "months", "ago", "and", "listed", "posted"}
)

_SALARY_PAIR_PATTERN = r"(RM\s?[\d,]+\s?[–—-]\s?RM\s?[\d,]+\s?per month)"
_SALARY_ANY_PATTERN = (
    r"((?:RM|SGD|S\$|MYR|IDR|PHP|THB|VND|Rp|₱)\s?[\d,.]+\s?"
    r"(?:[–—-]\s?(?:RM|SGD|S\$|MYR|IDR|PHP|THB|VND|Rp|₱)?\s?[\d,.]+\s?)?per month)"
)
_LISTED_SHORT_PATTERN = r"(\d+)\s*d\s+ago"
_LISTED_LONG_PATTERN = r"Listed\s+((?:[a-z0-9]+\s+){1,4}ago)"
_WORK_TYPE_PATTERN = r"\((hybrid|remote|onsite|on-site|on site|work from home)\)"

_EXTRACT_JS = (
    "elements => elements.map(card => {\n"
    "  const out = {title: '', url: '', company: '', location: '', work_type: '', salary: '', listed: ''};\n"
    "  const links = Array.from(card.querySelectorAll('a'));\n"
    "  const titleAnchor = card.querySelector('h3 a')\n"
    "    || links.find(a => (a.getAttribute('href') || '').startsWith('/job/'))\n"
    "    || null;\n"
    "  if (!titleAnchor) return out;\n"
    "  out.title = (titleAnchor.textContent || '').trim();\n"
    "  out.url = titleAnchor.getAttribute('href') || '';\n"
    "  const jobHref = out.url;\n"
    "  let companyHref = '';\n"
    "  for (const a of links) {\n"
    "    const h = a.getAttribute('href') || '';\n"
    "    if (h === jobHref || h.startsWith('/job/')) continue;\n"
    "    if (h.startsWith('/companies/')) { companyHref = h; out.company = (a.textContent || '').trim(); break; }\n"
    "  }\n"
    "  if (!out.company) {\n"
    "    for (const a of links) {\n"
    "      const h = a.getAttribute('href') || '';\n"
    "      if (h === jobHref || h.startsWith('/job/')) continue;\n"
    "      if (h.endsWith('-jobs') || h.endsWith('-jobs/')) { companyHref = h; out.company = (a.textContent || '').trim(); break; }\n"
    "    }\n"
    "  }\n"
    "  for (const a of links) {\n"
    "    const h = a.getAttribute('href') || '';\n"
    "    if (!h || h === jobHref || h === companyHref || h.startsWith('/job/')) continue;\n"
    "    if (h.indexOf('in-') !== -1) { out.location = (a.textContent || '').trim(); break; }\n"
    "  }\n"
    "  const text = card.innerText || '';\n"
    "  const wt = new RegExp(" + repr(_WORK_TYPE_PATTERN) + ", 'i').exec(text);\n"
    "  if (wt) out.work_type = wt[1].toLowerCase();\n"
    "  const salaryPair = new RegExp(" + repr(_SALARY_PAIR_PATTERN) + ", 'i').exec(text);\n"
    "  const salaryAny = new RegExp(" + repr(_SALARY_ANY_PATTERN) + ", 'i').exec(text);\n"
    "  out.salary = salaryPair ? salaryPair[1] : (salaryAny ? salaryAny[1] : '');\n"
    "  const listedShort = new RegExp(" + repr(_LISTED_SHORT_PATTERN) + ", 'i').exec(text);\n"
    "  const listedLong = new RegExp(" + repr(_LISTED_LONG_PATTERN) + ", 'i').exec(text);\n"
    "  out.listed = listedShort ? (listedShort[1] + 'd ago')\n"
    "    : (listedLong ? ('listed ' + listedLong[1].trim() + ' ago') : '');\n"
    "  return out;\n"
    "})"
)

_DISABLED_ERROR = (
    "JobStreet source disabled (set HIREFLOW_PLAYWRIGHT=1 with the Playwright base image)"
)


class JobStreetSource(JobSource):
    """Browser-rendered JobStreet search (Layer II, Cloudflare-guarded).

    JobStreet returns HTTP 403 to plain HTTP clients, so this source drives a
    real headless Chromium through ``playwright.async_api`` — the only path
    that matches what a human browser sees. URL shape:
    ``https://{cc}.jobstreet.com/{role-slug}-jobs/in-{location-slug}`` with a
    per-country subdomain (my/sg/id/ph/th/vn). Cards are ``article`` elements;
    title/company/location/work-type/salary/listed-age are read from the DOM
    via one ``eval_on_selector_all`` pass. ToS-respect: low volume, personal
    use — one page per run, hard-capped card count (``limit`` ≤20), no paging,
    no distributed crawling. Soft-fails everywhere (playwright missing,
    Chromium missing, 403/Cloudflare, timeout, no cards) by returning ``[]``
    with ``last_error`` set — never raises into a pipeline run.
    """

    name = "jobstreet"

    def __init__(self, limit: int = 20) -> None:
        super().__init__()
        self._cap = max(1, min(limit, 20))
        self._page_url = f"https://{_DEFAULT_SUBDOMAIN}/jobs"

    def _parse_row(self, row: dict) -> JobPosting:
        job = self._row_to_job(row, self._page_url)
        return job if job else JobPosting(id="", source=self.name)

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        if not SETTINGS.playwright_enabled:
            self._last_error = _DISABLED_ERROR
            return []
        try:
            from playwright.async_api import async_playwright  # local import
        except ImportError as exc:
            self._last_error = f"playwright not installed: {type(exc).__name__}: {str(exc)[:200]}"
            return []
        url = self._build_url(query, location, locations)
        self._page_url = url
        try:
            return await self._scrape(url, limit, locations)
        except Exception as exc:  # noqa: BLE001 - a dead page never sinks a run
            self._last_error = f"{url}: {type(exc).__name__}: {str(exc)[:300]}"
            return []

    async def _scrape(self, url: str, limit: int, locations: list[str] | None = None) -> list[JobPosting]:
        from playwright.async_api import async_playwright

        from hireflow.tools.browser_launcher import (
            apply_stealth,
            stealth_context_kwargs,
            stealth_launch_kwargs,
        )

        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(**stealth_launch_kwargs())
                try:
                    context = await browser.new_context(**stealth_context_kwargs(locations))
                    page = await context.new_page()
                    apply_stealth(page)
                    try:
                        return await self._extract(page, url, limit)
                    finally:
                        await context.close()
                finally:
                    await browser.close()
        except Exception as exc:  # noqa: BLE001 - Chromium missing/boot fail is non-fatal
            self._last_error = f"chromium failed: {type(exc).__name__}: {str(exc)[:200]}"
            return []

    async def _extract(
        self, page, url: str, limit: int
    ) -> list[JobPosting]:
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response is not None and response.status >= 400:
                self._last_error = f"{url}: HTTP {response.status} (Cloudflare block?)"
                return []
            try:
                await page.wait_for_selector("article", timeout=10000)
            except Exception as exc:  # noqa: BLE001 - hydrated cards never arriving
                self._last_error = f"{url}: no job cards ({type(exc).__name__})"
                return []
            await page.wait_for_timeout(1500)
            rows = await page.eval_on_selector_all("article", _EXTRACT_JS)
        except Exception as exc:  # noqa: BLE001 - a dead page never sinks a run
            self._last_error = f"{url}: {type(exc).__name__}: {str(exc)[:200]}"
            return []
        return self._rows_to_jobs(rows or [], url, limit)

    def _build_url(self, query: str, location: str, locations: list[str] | None) -> str:
        candidates = [loc.strip() for loc in (locations or []) if loc and loc.strip()]
        if not candidates and location and location.strip():
            candidates = [location.strip()]
        geo = LocationMapper.map(candidates)
        country = next(
            (code for code in geo.get("countries", []) if code in _COUNTRY_SUBDOMAINS),
            "my",
        )
        subdomain = _COUNTRY_SUBDOMAINS.get(country, _DEFAULT_SUBDOMAIN)
        role = self._slug(query)
        if not role:
            return f"https://{subdomain}/jobs"
        city = (LocationMapper.map_full(candidates).get("cities") or [""])[0]
        place = self._slug(city or (candidates[0] if candidates else ""))
        path = f"/{role}-jobs" + (f"/in-{place}" if place else "")
        return f"https://{subdomain}{path}"

    def _rows_to_jobs(
        self, rows: list[dict[str, Any]], page_url: str, limit: int
    ) -> list[JobPosting]:
        cap = min(max(1, limit), self._cap)
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        for row in rows:
            job = self._row_to_job(row, page_url)
            if job is None or job.id in seen:
                continue
            seen.add(job.id)
            jobs.append(job)
            if len(jobs) >= cap:
                break
        if not jobs and not self._last_error:
            self._last_error = f"{page_url}: 0 parseable cards"
        return jobs

    def _row_to_job(self, row: dict[str, Any], page_url: str) -> JobPosting | None:
        title = str(row.get("title", "") or "").strip()
        href = str(row.get("url", "") or "").strip()
        if not title or not href:
            return None
        match = _JOB_ID_RE.search(href)
        if not match:
            return None
        location = str(row.get("location", "") or "").strip()
        work_type = self._normalize_work_type(str(row.get("work_type", "") or ""))
        display_location = f"{location} · {work_type}" if location and work_type else (
            location or work_type
        )
        raw: dict[str, Any] = {
            "salary": str(row.get("salary", "") or ""),
            "listed": str(row.get("listed", "") or ""),
        }
        if work_type:
            raw["work_mode"] = work_type
        return JobPosting(
            id=f"jobstreet-{match.group(1)}",
            source=self.name,
            title=title,
            company=str(row.get("company", "") or "").strip(),
            location=display_location,
            post_url=urllib.parse.urljoin(page_url, href),
            posted_at=self._posted_at(row.get("listed")),
            raw_data=raw,
        )

    @staticmethod
    def _slug(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", (text or "").lower().strip()).strip("-")

    @staticmethod
    def _normalize_work_type(value: str) -> str:
        lowered = value.strip().lower()
        lowered = _WORK_ALIASES.get(lowered, lowered)
        return lowered if lowered in _WORK_TYPES else ""

    @classmethod
    def _posted_at(cls, listed: Any) -> datetime | None:
        days = cls._parse_listed_days(str(listed or ""))
        if days is None:
            return None
        return datetime.now(timezone.utc) - timedelta(days=days)

    @classmethod
    def _parse_listed_days(cls, listed: str) -> int | None:
        text = (listed or "").lower().strip()
        if not text:
            return None
        if any(
            marker in text
            for marker in ("today", "moment", "just now", "hour", "minute", "second")
        ):
            return 0
        short = re.search(r"(\d+)\s*d\b", text)
        if short:
            return int(short.group(1))
        if "yesterday" in text:
            return 1
        phrase_match = re.search(r"listed\s+(.+?)\s+ago\b", text)
        phrase = phrase_match.group(1) if phrase_match else text
        digits = re.search(r"(\d+)", phrase)
        if digits:
            count = int(digits.group(1))
        elif phrase.strip().startswith(("a ", "an ")):
            count = 1
        else:
            count = cls._words_to_number(
                [
                    word
                    for word in re.findall(r"[a-z]+", phrase)
                    if word not in _DURATION_WORDS
                ]
            )
        if count is None:
            return None
        if "month" in phrase:
            return count * 30
        if "week" in phrase:
            return count * 7
        return count

    @staticmethod
    def _words_to_number(words: list[str]) -> int | None:
        if not words:
            return None
        if len(words) == 1:
            return _UNIT_DAYS.get(words[0], _TEN_DAYS.get(words[0]))
        if len(words) == 2:
            tens = _TEN_DAYS.get(words[0])
            units = _UNIT_DAYS.get(words[1])
            if tens is not None and units is not None:
                return tens + units
        return None
