from __future__ import annotations

import uuid
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from hireflow.config import SETTINGS
from hireflow.domain import (
    Application,
    ApplicationStatus,
    JobPosting,
    Profile,
    WorkTypeClassifier,
)
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.job_source import JobSource


class HireflowTools:
    """ADK-registered tools plus the deterministic pipeline executor.

    All scoring / researching / drafting goes through ``GeminiClient`` (the only
    LLM entry point) — never a stub. A failed job source degrades to [] and is
    recorded in ``errors`` instead of crashing the run.
    """

    _WORK_MODE_VALUES = {"remote", "hybrid", "onsite"}

    def __init__(
        self,
        sources: list[JobSource],
        gemini: GeminiClient,
        caps: dict[str, int] | None = None,
    ) -> None:
        self._sources = sources
        self._gemini = gemini
        self._caps = caps or {
            "max_jobs": SETTINGS.pipeline_max_jobs,
            "max_score": SETTINGS.pipeline_max_score,
            "max_prep": SETTINGS.pipeline_max_prep,
            "max_research": SETTINGS.pipeline_max_research,
        }
        self.reset()

    def reset(self) -> None:
        self._state: dict[str, Any] = {}
        self._errors: list[str] = []

    @property
    def state(self) -> dict[str, Any]:
        return self._state

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    async def search_jobs(self, query: str, tool_context: ToolContext | None = None) -> list[dict[str, Any]]:
        """Search all configured job boards for postings matching `query`."""
        jobs: list[JobPosting] = []
        for source in self._sources:
            try:
                jobs.extend(await source.search(query=query))
            except Exception as exc:  # noqa: BLE001
                self._errors.append(f"{source.name}: {type(exc).__name__}: {str(exc)[:200]}")
        mappings = [job.to_mapping() for job in jobs]
        self._state["jobs"] = mappings
        if tool_context is not None:
            tool_context.state["jobs"] = mappings
        return mappings

    async def score_jobs(
        self,
        jobs: list[dict[str, Any]],
        profile: dict[str, Any],
        tool_context: ToolContext | None = None,
    ) -> list[dict[str, Any]]:
        """Score each job (0-100) against the profile across 5 dimensions."""
        profile_obj = Profile.from_mapping(profile)
        matches = []
        for job_map in jobs:
            job = JobPosting.from_mapping(job_map)
            score, reasons = await self._gemini.score_fit(job=job, profile=profile_obj)
            matches.append({"job": job_map, "score": score, "reasons": reasons})
        self._state["matches"] = matches
        if tool_context is not None:
            tool_context.state["matches"] = matches
        return matches

    async def research_company(
        self, company: str, tool_context: ToolContext | None = None
    ) -> dict[str, Any]:
        """Generate a company-fit research summary."""
        research = await self._gemini.research_company(company)
        self._state.setdefault("research", []).append(research)
        if tool_context is not None:
            tool_context.state.setdefault("research", []).append(research)
        return research

    async def prepare_application(
        self,
        profile: dict[str, Any],
        job: dict[str, Any],
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        """Draft, review, and revise a CV + cover letter for a job."""
        draft = await self._gemini.draft_application(
            profile=Profile.from_mapping(profile), job=JobPosting.from_mapping(job)
        )
        review = await self._gemini.review_application(draft=draft)
        revised = await self._gemini.revise_application(draft=draft, review=review)
        result = {"draft": draft, "review": review, "revised": revised}
        self._state.setdefault("applications", []).append(result)
        if tool_context is not None:
            tool_context.state.setdefault("applications", []).append(result)
        return result

    async def run_pipeline(self, profile: Profile) -> dict[str, Any]:
        self.reset()
        profile_data = profile.to_mapping()
        jobs = await self._discover_jobs(profile)
        matches = await self._score_jobs(jobs, profile)
        matches = await self._research_enrich(matches)
        drafts = await self._draft_top(matches, profile)
        applications = self._build_applications(matches, profile, drafts)

        self._state = {
            "profile": profile_data,
            "jobs_found": len(jobs),
            "jobs": jobs,
            "matches": matches,
            "drafts": drafts,
        }
        return {
            "jobs": jobs,
            "matches": matches,
            "drafts": drafts,
            "applications": [app.to_mapping() for app in applications],
            "errors": self._errors,
        }

    async def _discover_jobs(self, profile: Profile) -> list[dict[str, Any]]:
        query = " ".join(profile.target_roles).strip() or profile.resume_text[:300]
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        per_source = max(
            1, self._caps["max_jobs"] // max(1, len(self._sources))
        )
        for source in self._sources:
            try:
                found = await source.search(
                    query=query,
                    limit=per_source,
                    work_type=profile.work_type,
                    locations=profile.locations,
                )
            except Exception as exc:  # noqa: BLE001
                self._errors.append(f"{source.name}: {type(exc).__name__}: {str(exc)[:200]}")
                found = []
            if source.last_error:
                self._errors.append(f"{source.name}: {source.last_error}")
            for job in found:
                if not job.id or job.id in seen:
                    continue
                if not self._passes_work_gate(job, profile.work_type):
                    continue
                seen.add(job.id)
                jobs.append(job)
                if len(jobs) >= self._caps["max_jobs"]:
                    return [job.to_mapping() for job in jobs]
        return [job.to_mapping() for job in jobs]

    async def _score_jobs(
        self, jobs: list[dict[str, Any]], profile: Profile
    ) -> list[dict[str, Any]]:
        scored: list[dict[str, Any]] = []
        for job_map in jobs[: self._caps["max_score"]]:
            job = JobPosting.from_mapping(job_map)
            score, reasons = await self._gemini.score_fit(job=job, profile=profile)
            scored.append({"job": job_map, "score": score, "reasons": reasons})
        scored.sort(key=lambda match: match["score"], reverse=True)
        return scored

    async def _research_enrich(
        self, matches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        researched: dict[str, dict[str, Any]] = {}
        chosen = matches[: self._caps["max_research"]]
        for match in chosen:
            job = JobPosting.from_mapping(match["job"])
            company = job.company
            if not company:
                continue
            if company not in researched:
                try:
                    researched[company] = await self._gemini.research_company(company)
                except Exception as exc:  # noqa: BLE001
                    self._errors.append(f"research {company}: {type(exc).__name__}: {str(exc)[:200]}")
                    researched[company] = {"company": company, "summary": "", "error": str(exc)[:200]}
        for match in matches:
            job = JobPosting.from_mapping(match["job"])
            match["research"] = researched.get(job.company) or {}
        return matches

    async def _draft_top(
        self, matches: list[dict[str, Any]], profile: Profile
    ) -> dict[str, dict[str, Any]]:
        drafts: dict[str, dict[str, Any]] = {}
        prepared = 0
        for match in matches:
            if prepared >= self._caps["max_prep"]:
                break
            job = JobPosting.from_mapping(match["job"])
            try:
                draft = await self._gemini.draft_application(profile=profile, job=job)
                review = await self._gemini.review_application(draft=draft)
                revised = await self._gemini.revise_application(draft=draft, review=review)
            except Exception as exc:  # noqa: BLE001
                self._errors.append(f"prepare {job.id}: {type(exc).__name__}: {str(exc)[:200]}")
                continue
            drafts[job.id] = {"draft": draft, "review": review, "revised": revised}
            prepared += 1
        return drafts

    def _build_applications(
        self,
        matches: list[dict[str, Any]],
        profile: Profile,
        drafts: dict[str, dict[str, Any]],
    ) -> list[Application]:
        applications: list[Application] = []
        for match in matches:
            score = int(match.get("score", 0))
            if score < SETTINGS.approve_threshold_draft:
                continue
            job = JobPosting.from_mapping(match["job"])
            status = (
                ApplicationStatus.DRAFTED
                if score >= SETTINGS.approve_threshold_auto
                else ApplicationStatus.ROUTED
            )
            if job.id not in drafts:
                status = ApplicationStatus.MATCHED
            applications.append(
                Application(
                    id=str(uuid.uuid4()),
                    job=job,
                    profile_id=profile.id,
                    status=status,
                    score=score,
                    human_handoff=self._needs_human(job, profile),
                )
            )
        return applications

    def _passes_work_gate(self, job: JobPosting, work_type: str) -> bool:
        preference = (work_type or "any").strip().lower()
        if preference == "any":
            return True
        declared = str(job.raw_data.get("work_mode", "") or "").strip().lower()
        actual = declared if declared in self._WORK_MODE_VALUES else self._infer_work_type(job)
        if actual == "any":
            return True
        return preference == actual

    def _infer_work_type(self, job: JobPosting) -> str:
        description = job.raw_data.get("description", "") if isinstance(job.raw_data, dict) else ""
        return WorkTypeClassifier.classify(f"{job.title} {job.location} {description}")

    @staticmethod
    def _needs_human(job: JobPosting, profile: Profile) -> bool:
        if not profile.salary_floor:
            return False
        raw = job.raw_data if isinstance(job.raw_data, dict) else {}
        enrichment = raw.get("enrichment") if isinstance(raw.get("enrichment"), dict) else {}
        salary_max = enrichment.get("salary_max")
        try:
            if salary_max is not None and int(salary_max) < int(profile.salary_floor):
                return True
        except (TypeError, ValueError):
            return False
        return False


class HireflowAgent:
    """Builds the ADK agent graph and runs it through the ADK Runner."""

    def __init__(self, tools: HireflowTools) -> None:
        self._tools = tools
        self.agent = LlmAgent(
            name="hireflow_router",
            model=Gemini(model=SETTINGS.gemini_model),
            instruction=(
                "You are Hireflow, an autonomous job-search agent. Execute the pipeline in order: "
                "search jobs, score them against the profile, research the top companies, and prepare "
                "tailored applications. Then stop and hand off for human approval. Never submit without approval."
            ),
            tools=[
                FunctionTool(self._tools.search_jobs),
                FunctionTool(self._tools.score_jobs),
                FunctionTool(self._tools.research_company),
                FunctionTool(self._tools.prepare_application),
            ],
        )
        self._session_service = InMemorySessionService()
        self._runner = Runner(
            agent=self.agent, app_name="hireflow", session_service=self._session_service
        )

    @property
    def tools(self) -> HireflowTools:
        return self._tools

    async def run(self, user_id: str, session_id: str, profile: dict[str, Any]) -> str:
        message = f"Run the pipeline for this profile: {profile}"
        content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        final_parts: list[str] = []
        async for event in self._runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            if event.is_final_response():
                for part in event.content.parts:
                    if part.text:
                        final_parts.append(part.text)
        return "\n".join(final_parts)

    async def run_pipeline(self, profile: dict[str, Any]) -> dict[str, Any]:
        profile_obj = Profile.from_mapping(profile)
        result = await self._tools.run_pipeline(profile_obj)

        matches = result["matches"]
        drafts = result["drafts"]
        applications = result["applications"]
        needs_human = []

        ranked = []
        for index, match in enumerate(matches[:10], start=1):
            job = JobPosting.from_mapping(match["job"])
            ranked.append(
                {
                    "rank": index,
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "source": job.source,
                    "post_url": job.post_url,
                    "location": job.location,
                    "score": match["score"],
                    "reasons": match.get("reasons", []),
                    "research": match.get("research", {}),
                }
            )

        app_summary = []
        for application_map in applications:
            application = Application.from_mapping(application_map)
            if application.job is None:
                continue
            entry = {
                "id": application.id,
                "job_id": application.job.id,
                "title": application.job.title,
                "company": application.job.company,
                "status": application.status.value,
                "score": application.score,
                "human_handoff": application.human_handoff,
                "drafted": application.job.id in drafts,
            }
            app_summary.append(entry)
            if application.human_handoff:
                needs_human.append(
                    {
                        "application_id": application.id,
                        "title": application.job.title,
                        "company": application.job.company,
                        "reason": "salary range may fall below your floor — negotiate",
                    }
                )

        return {
            "profile_id": profile.get("id", ""),
            "jobs_found": len(result["jobs"]),
            "matches": ranked,
            "applications": app_summary,
            "drafts": {
                job_id: {
                    "cv": package.get("revised", {}).get("cv") or package.get("draft", {}).get("cv", ""),
                    "cover_letter": package.get("revised", {}).get("cover_letter")
                    or package.get("draft", {}).get("cover_letter", ""),
                }
                for job_id, package in drafts.items()
            },
            "needs_human": needs_human,
            "errors": result["errors"],
        }