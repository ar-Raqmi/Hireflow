from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx

from hireflow.domain import JobPosting

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class JobSource(ABC):
    """Contract for keyless job-board sources.

    Subclasses configure the request and row-shape; the shared template in
    :meth:`search` handles fetch, parse, filter, truncate, and failure
    tolerance. A source that is down must degrade to ``[]``, never raise.
    """

    name: str = "base"
    _url: str = ""
    _rows_path: tuple[str, ...] = ()
    _QUERY_STOPWORDS = {"remote", "onsite", "hybrid", "any", "worldwide", "anywhere"}
    _REMOTEISH_MARKERS = ("remote", "worldwide", "anywhere", "distributed")

    def __init__(self) -> None:
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        return self._last_error

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
            data = await self._fetch_json(self._url, params)
        except (httpx.HTTPError, ValueError) as exc:
            self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            return []
        jobs = [self._parse_row(row) for row in self._extract_rows(data)]
        jobs = [job for job in jobs if self._matches(job, query, location)]
        return jobs[:limit]

    async def _fetch_json(self, url: str, params: dict[str, str] | None) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        return response.json()

    def _params(
        self,
        query: str,
        location: str,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> dict[str, str] | None:
        if query:
            return {"q": query}
        return None

    def _extract_rows(self, data: Any) -> list[dict]:
        for key in self._rows_path:
            if isinstance(data, dict):
                data = data.get(key, [])
        if isinstance(data, dict):
            data = [data]
        return [row for row in data if isinstance(row, dict)]

    @abstractmethod
    def _parse_row(self, row: dict) -> JobPosting: ...

    def _matches(self, job: JobPosting, query: str, location: str) -> bool:
        if not job.title:
            return False
        if query:
            tokens = [
                token for token in query.lower().split()
                if len(token) > 2 and token not in self._QUERY_STOPWORDS
            ]
            if tokens and not any(token in job.title.lower() for token in tokens):
                return False
        if location:
            preferred = [part.strip().lower() for part in location.split(",") if part.strip()]
            job_location = (job.location or "").lower()
            if job_location and not any(marker in job_location for marker in self._REMOTEISH_MARKERS):
                if not any(pref in job_location for pref in preferred):
                    return False
        return True

    @staticmethod
    def _parse_iso(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        normalized = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None