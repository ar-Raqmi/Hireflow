from __future__ import annotations

from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource


class FreehireSource(JobSource):
    """Keyless freehire.me aggregator API. Tech-focused, structured results."""

    name = "freehire"
    _url = "https://freehire.me/api/v1/jobs"
    _rows_path = ("jobs",)

    def _params(self, query: str, location: str) -> dict[str, str] | None:
        params: dict[str, str] = {}
        if query:
            params["q"] = query
        if location:
            params["location"] = location
        return params or None

    def _parse_row(self, row: dict) -> JobPosting:
        return JobPosting(
            id=str(row.get("id", "")),
            source=self.name,
            title=str(row.get("title", "") or ""),
            company=str(row.get("company", "") or ""),
            location=str(row.get("location", "") or ""),
            post_url=str(row.get("url", "") or ""),
            raw_data=row,
        )
