from __future__ import annotations

from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource


class RemoteOKSource(JobSource):
    """Keyless RemoteOK job API. https://remoteok.com/api"""

    name = "remoteok"
    _url = "https://remoteok.com/api"

    def _parse_row(self, row: dict) -> JobPosting:
        return JobPosting(
            id=str(row.get("id", "")),
            source=self.name,
            title=str(row.get("position", "") or ""),
            company=str(row.get("company", "") or ""),
            location="Remote",
            post_url=str(row.get("url", "") or ""),
            posted_at=self._parse_iso(row.get("date")),
            raw_data=row,
        )
