from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from hireflow.domain import JobPosting


class JobSource(ABC):
    """Contract for keyless job-board sources.

    Subclasses configure the request and row-shape; the shared template in
    :meth:`search` handles fetch, parse, filter, and truncate.
    """

    name: str = "base"
    _url: str = ""
    _rows_path: tuple[str, ...] = ()

    async def search(self, query: str = "", location: str = "", limit: int = 25) -> list[JobPosting]:
        data = await self._fetch_json(self._url, self._params(query, location))
        jobs = [self._parse_row(row) for row in self._extract_rows(data)]
        jobs = [job for job in jobs if self._matches(job, query, location)]
        return jobs[:limit]

    async def _fetch_json(self, url: str, params: dict[str, str] | None) -> Any:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        return response.json()

    def _params(self, query: str, location: str) -> dict[str, str] | None:
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
        if query and query.lower() not in job.title.lower():
            return False
        if location and location.lower() not in job.location.lower():
            return False
        return True
