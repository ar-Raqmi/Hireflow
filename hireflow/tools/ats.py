from __future__ import annotations

from typing import Any

import httpx

from hireflow.config import ATS_BOARDS
from hireflow.domain import JobPosting
from hireflow.tools.job_source import JobSource


class AtsBoardSource(JobSource):
    """Keyless ATS job boards (Greenhouse / Lever / Ashby / Workable).

    Unifies public, unauthenticated ATS posting APIs behind the shared
    ``JobSource`` contract. Each board type has its own endpoint builder,
    row-extraction path and row-shape, so a failing board degrades to ``[]``
    (``last_error``) and never sinks a run. ``source`` is ``ats:<board>`` so
    results stay attributable per board.

    Config owns which boards are polled (``hireflow.config.ATS_BOARDS``). Only
    boards confirmed by a live ``curl`` are enabled in that dict; a 404/empty
    board is dropped from the registry, not silently claimed.
    """

    name = "ats"

    def __init__(self, boards: dict[str, list[str]] | None = None) -> None:
        super().__init__()
        self._boards = boards if boards is not None else ATS_BOARDS

    def _parse_row(self, row: dict) -> JobPosting:
        return JobPosting(source=self.name, raw_data=row)

    async def search(
        self,
        query: str = "",
        location: str = "",
        limit: int = 25,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        for kind, names in self._boards.items():
            for name in names:
                try:
                    url = self._url_for(kind, name)
                    payload = await self._fetch_json(url, None)
                except (httpx.HTTPError, ValueError) as exc:
                    self._last_error = f"{kind}:{name}: {type(exc).__name__}: {str(exc)[:200]}"
                    continue
                rows = self._rows_for(kind, payload)
                for row in rows:
                    job = self._parse(kind, row)
                    if not job or not job.id or job.id in seen:
                        continue
                    if not self._matches(job, query, ""):
                        continue
                    seen.add(job.id)
                    jobs.append(job)
        return jobs[:limit]

    @staticmethod
    def _url_for(kind: str, name: str) -> str:
        if kind == "greenhouse":
            return f"https://boards-api.greenhouse.io/v1/boards/{name}/jobs?content=true"
        if kind == "lever":
            return f"https://api.lever.co/v0/postings/{name}?mode=json"
        if kind == "ashby":
            return f"https://api.ashbyhq.com/posting-api/job-board/{name}"
        if kind == "workable":
            return f"https://apply.workable.com/api/v1/widget/accounts/{name}"
        raise ValueError(f"unknown board type: {kind}")

    @staticmethod
    def _rows_for(kind: str, payload: Any) -> list[Any]:
        if kind in {"greenhouse", "ashby"}:
            if isinstance(payload, dict):
                rows = payload.get("jobs", [])
                return rows if isinstance(rows, list) else []
        if kind == "lever":
            return payload if isinstance(payload, list) else []
        if kind == "workable":
            if isinstance(payload, dict):
                rows = payload.get("jobs", [])
                return rows if isinstance(rows, list) else []
        return []

    def _parse(self, kind: str, row: Any) -> JobPosting | None:
        if not isinstance(row, dict):
            return None
        if kind == "greenhouse":
            return self._parse_greenhouse(row)
        if kind == "lever":
            return self._parse_lever(row)
        if kind == "ashby":
            return self._parse_ashby(row)
        if kind == "workable":
            return self._parse_workable(row)
        return None

    def _parse_greenhouse(self, row: dict) -> JobPosting:
        location = row.get("location") or {}
        if isinstance(location, dict):
            location = location.get("name", "")
        return JobPosting(
            id=str(row.get("id", "") or row.get("requisition_id", "")),
            source="ats:greenhouse",
            title=str(row.get("title", "") or ""),
            company=str(row.get("company_name", "") or ""),
            location=str(location or ""),
            post_url=str(row.get("absolute_url", "") or ""),
            posted_at=self._parse_iso(row.get("first_published")),
            raw_data={"description": self._strip_html(row.get("content", ""))},
        )

    def _parse_lever(self, row: dict) -> JobPosting:
        categories = row.get("categories") or {}
        if isinstance(categories, dict):
            location = categories.get("location", "")
            commitment = categories.get("commitment", "")
        else:
            location = ""
            commitment = ""
        parts = [part for part in (str(location), str(commitment)) if part]
        return JobPosting(
            id=str(row.get("id", "") or ""),
            source="ats:lever",
            title=str(row.get("text", "") or ""),
            company=str(row.get("company", "") or ""),
            location=" · ".join(parts),
            post_url=str(row.get("hostedUrl", "") or row.get("applyUrl", "") or ""),
            raw_data={"description": self._strip_html(str(row.get("description", "") or ""))},
        )

    def _parse_ashby(self, row: dict) -> JobPosting:
        return JobPosting(
            id=str(row.get("id", "") or ""),
            source="ats:ashby",
            title=str(row.get("title", "") or ""),
            company="",
            location=str(row.get("location", "") or ""),
            post_url=str(row.get("jobUrl", "") or ""),
            posted_at=self._parse_iso(row.get("publishedAt")),
            raw_data={"description": self._strip_html(str(row.get("descriptionHtml", "") or ""))},
        )

    def _parse_workable(self, row: dict) -> JobPosting:
        return JobPosting(
            id=str(row.get("shortcode", "") or row.get("id", "") or ""),
            source="ats:workable",
            title=str(row.get("title", "") or ""),
            company=str(row.get("company", "") or ""),
            location=", ".join(
                part
                for part in (
                    str(row.get("city", "") or ""),
                    str(row.get("country", "") or ""),
                )
                if part
            ),
            post_url=str(row.get("url", "") or ""),
            raw_data={"description": self._strip_html(str(row.get("description", "") or ""))},
        )

    @staticmethod
    def _strip_html(value: str) -> str:
        text = value.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        while "<" in text:
            start = text.find("<")
            end = text.find(">", start)
            if end == -1:
                break
            text = text[:start] + " " + text[end + 1:]
        return " ".join(text.split())