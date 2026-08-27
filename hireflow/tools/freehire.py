from __future__ import annotations

import os

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.geo import LocationMapper
from hireflow.tools.job_source import JobSource

FREEHIRE_API_URL = os.getenv(
    "FREEHIRE_API_URL", "https://freehire.me/api/v1/agent/jobs/search"
)


class FreehireSource(JobSource):
    """Keyless freehire.me aggregator (covers 193 countries).

    Uses the live agent search endpoint with server-side country/region,
    work-mode and recency filters; fails soft (returns []) if the board is down.
    """

    name = "freehire"
    _url = FREEHIRE_API_URL
    _rows_path = ("data",)

    def __init__(self) -> None:
        super().__init__()
        self._mapper = LocationMapper()

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
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            return []
        jobs = [self._parse_row(row) for row in self._extract_rows(data)]
        jobs = [job for job in jobs if self._matches(job, query, "")]
        return jobs[:limit]

    def _params(
        self,
        query: str,
        location: str,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> dict[str, str]:
        params: dict[str, str] = {
            "q": query or "software engineer",
            "posted_within_days": str(SETTINGS.freehire_posted_within_days),
            "include_description": "true",
            "limit": "25",
            "offset": "0",
        }
        geo = self._mapper.map(locations or [])
        if geo["countries"]:
            params["countries"] = ",".join(geo["countries"])
        elif geo["regions"]:
            params["regions"] = ",".join(geo["regions"])
        if work_type != "any":
            params["work_mode"] = work_type
        return params

    def _parse_row(self, row: dict) -> JobPosting:
        location = str(row.get("location", "") or "")
        work_mode = str(row.get("work_mode", "") or "").strip()
        if work_mode and work_mode.lower() not in location.lower():
            location = f"{location} · {work_mode}".strip(" ·")
        return JobPosting(
            id=str(row.get("public_slug", "") or row.get("external_id", "") or ""),
            source=self.name,
            title=str(row.get("title", "") or "").strip(),
            company=str(row.get("company", "") or ""),
            location=location,
            post_url=str(row.get("url", "") or ""),
            posted_at=self._parse_iso(row.get("posted_at")),
            raw_data=row,
        )
