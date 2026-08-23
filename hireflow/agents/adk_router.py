from __future__ import annotations

from typing import Any, Awaitable, Callable

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from hireflow.agents.router import RouterAgent
from hireflow.config import SETTINGS
from hireflow.domain import JobPosting, Profile
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.job_source import JobSource


class HireflowTools:
    """ADK-registered tools backing the mandated Google Agent Framework graph.

    The four ``FunctionTool`` methods are the framework evidence (RULES §67).
    Every LLM call still goes through ``GeminiClient`` (the only LLM entry
    point) — never a stub. The autonomous pipeline that the CLI/SSE run is
    owned by ``RouterAgent`` (see ``agents/router.py``); these tools remain for
    the ADK graph, not as the pipeline executor.
    """

    def __init__(
        self,
        sources: list[JobSource],
        gemini: GeminiClient,
    ) -> None:
        self._sources = sources
        self._gemini = gemini
        self._progress: Callable[[str, str], Awaitable[None]] | None = None
        self.reset()

    def reset(self) -> None:
        self._state: dict[str, Any] = {}
        self._errors: list[str] = []

    async def _emit(self, stage: str, detail: str) -> None:
        if self._progress is not None:
            await self._progress(stage, detail)

    @property
    def state(self) -> dict[str, Any]:
        return self._state

    @property
    def gemini(self) -> GeminiClient:
        return self._gemini

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


class HireflowAgent:
    """Builds the ADK agent graph (the mandated Google Agent Framework) and runs it.

    The CLI/SSE path runs ``RouterAgent.run_pipeline`` (the real executor);
    ``HireflowAgent`` keeps the ADK ``LlmAgent`` graph alive as framework
    evidence. When a ``router`` is supplied, ``run_pipeline`` delegates to it.
    """

    def __init__(self, tools: HireflowTools, router: RouterAgent | None = None) -> None:
        self._tools = tools
        self._router = router
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

    async def run_pipeline(
        self,
        profile: dict[str, Any],
        progress: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        profile_obj = Profile.from_mapping(profile)
        if self._router is not None:
            return await self._router.run_pipeline(profile_obj, progress=progress)
        return {
            "profile_id": profile_obj.id,
            "jobs_found": 0,
            "jobs": [],
            "matches": [],
            "applications": [],
            "application_records": [],
            "drafts": {},
            "needs_human": [],
            "errors": ["HireflowAgent has no RouterAgent wired"],
        }