from __future__ import annotations

from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource


class WantedlySource(JobSource):
    """Keyless Wantedly (JP) project feed.

    ``https://wantedly.com/api/v1/projects?search=...`` returns a JSON list
    under ``data`` with title, company, location, ``published_at`` and a full
    description. Keyless, no auth. Verified live (2026-08-23): 200 + structured
    rows. ``source="wantedly"``.
    """

    name = "wantedly"
    _url = "https://wantedly.com/api/v1/projects"
    _rows_path = ("data",)

    def _params(
        self,
        query: str,
        location: str,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> dict[str, str] | None:
        return {"search": query, "limit": "25"} if query else None

    def _parse_row(self, row: dict) -> JobPosting:
        company = row.get("company") or {}
        if isinstance(company, dict):
            company_name = str(company.get("name", "") or "")
        else:
            company_name = str(company or "")
        project_id = str(row.get("id", "") or "")
        url = f"https://wantedly.com/ja/projects/{project_id}" if project_id else ""
        return JobPosting(
            id=project_id,
            source=self.name,
            title=str(row.get("title", "") or ""),
            company=company_name,
            location=str(row.get("location", "") or ""),
            post_url=url,
            posted_at=self._parse_iso(row.get("published_at")),
            raw_data={"description": str(row.get("description", "") or "")},
        )
