from __future__ import annotations

from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource


class FreehireSource(JobSource):
    """Keyless freehire.me aggregator API. Tech-focused, structured results."""

    name = "freehire"
    _url = "https://freehire.me/api/v1/jobs"
    _rows_path = ("data",)

    def _params(self, query: str, location: str) -> dict[str, str] | None:
        params: dict[str, str] = {}
        if query:
            params["q"] = query
        if location:
            params["location"] = location
        return params or None

    def _parse_row(self, row: dict) -> JobPosting:
        location = str(row.get("location", "") or "")
        work_mode = str(row.get("work_mode", "") or "").strip()
        if work_mode and work_mode.lower() not in location.lower():
            location = f"{location} · {work_mode}".strip(" ·")
        return JobPosting(
            id=str(row.get("public_slug", "") or row.get("external_id", "") or ""),
            source=self.name,
            title=str(row.get("title", "") or ""),
            company=str(row.get("company", "") or ""),
            location=location,
            post_url=str(row.get("url", "") or ""),
            raw_data=row,
        )
