from __future__ import annotations

from typing import Any

from hireflow.agents.base_agent import BaseAgent
from hireflow.config import SETTINGS
from hireflow.domain import JobPosting, Profile
from hireflow.tools.webfetch import WebFetchSource


class CareerSourceAgent(BaseAgent):
    """Probes the top matched companies' career pages for jobs absent from boards.

    Runs after matching: takes the distinct companies of the scored matches
    (capped by ``CAREER_SOURCE_MAX_COMPANIES``), reads each company's
    ``/careers`` page and ATS boards via ``WebFetchSource.webfetch_company``,
    and returns the new jobs that were not already on the pipeline's job list.
    These are merged back into the pipeline so they compete with board jobs in
    scoring/preparation. A company with no parseable careers page contributes 0
    jobs plus a source note — it never breaks a run. Jobs carry ``source``
    ``webfetch`` (with ``raw_data["webfetch_via"]`` = jsonld | ats | html).
    """

    name = "career"

    def __init__(self, fetcher: WebFetchSource | None = None) -> None:
        self._fetcher = fetcher if fetcher is not None else WebFetchSource()

    async def run(self, context: dict) -> dict:
        if not SETTINGS.career_source_enabled:
            await self._emit("career", "career-page sourcing off (CAREER_SOURCE_ENABLED disabled)")
            return {"jobs": [], "new_jobs": 0, "companies": []}
        if not SETTINGS.web_fetch_enabled:
            await self._emit("career", "career-page sourcing off (WEB_FETCH disabled)")
            return {"jobs": [], "new_jobs": 0, "companies": []}
        profile: Profile = context["profile"]
        errors: list[str] = context["errors"]
        companies = self._top_companies(context.get("matches", []), SETTINGS.career_source_max_companies)
        if not companies:
            await self._emit("career", "no matched companies to probe for career-page jobs")
            return {"jobs": [], "new_jobs": 0, "companies": []}
        names = ", ".join(companies)
        await self._emit("career", f"probing careers pages for {len(companies)} companies ({names})…")
        role_query = self._role_query(profile)
        seen = {
            str(job_map.get("id", ""))
            for job_map in context.get("jobs", [])
            if isinstance(job_map, dict)
        }
        new_jobs: list[JobPosting] = []
        for company in companies:
            try:
                found = await self._fetcher.webfetch_company(
                    company, profile.locations, role_query
                )
            except Exception as exc:  # noqa: BLE001 - a blocked careers page is non-fatal
                errors.append(f"career {company}: {type(exc).__name__}: {str(exc)[:200]}")
                found = []
            if not found:
                note = getattr(self._fetcher, "last_error", None) or "no parseable jobs"
                errors.append(f"career {company}: {note}")
                continue
            added = 0
            for job in found:
                if not job.id or job.id in seen:
                    continue
                seen.add(job.id)
                new_jobs.append(job)
                added += 1
                if added >= SETTINGS.career_source_max_per_company:
                    break
        await self._emit(
            "career",
            f"career pages: {len(new_jobs)} new job(s) from {len(companies)} companies ({names})",
        )
        return {
            "jobs": [job.to_mapping() for job in new_jobs],
            "new_jobs": len(new_jobs),
            "companies": companies,
        }

    @staticmethod
    def _top_companies(matches: list[dict[str, Any]], cap: int) -> list[str]:
        companies: list[str] = []
        seen: set[str] = set()
        for match in matches:
            job_map = match.get("job") if isinstance(match, dict) else None
            if not isinstance(job_map, dict):
                continue
            job = JobPosting.from_mapping(job_map)
            company = (job.company or "").strip()
            if not company or company.lower() in seen:
                continue
            seen.add(company.lower())
            companies.append(company)
            if len(companies) >= cap:
                break
        return companies

    @staticmethod
    def _role_query(profile: Profile) -> str:
        parts = [role for role in profile.target_roles if role]
        parts = parts or [skill for skill in profile.skills if skill]
        return " ".join(parts).strip() or "software engineer"