from __future__ import annotations

from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource


class RemotiveSource(JobSource):
    """Keyless Remotive remote-jobs API. https://remotive.com/api/remote-jobs"""

    name = "remotive"
    _url = "https://remotive.com/api/remote-jobs"
    _rows_path = ("jobs",)

    def _params(
        self,
        query: str,
        location: str,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> dict[str, str] | None:
        return {"search": query} if query else None

    def _parse_row(self, row: dict) -> JobPosting:
        return JobPosting(
            id=str(row.get("id", "")),
            source=self.name,
            title=str(row.get("title", "") or ""),
            company=str(row.get("company_name", "") or ""),
            location=str(row.get("candidate_required_location", "") or ""),
            post_url=str(row.get("url", "") or ""),
            posted_at=self._parse_iso(row.get("publication_date")),
            raw_data=row,
        )
