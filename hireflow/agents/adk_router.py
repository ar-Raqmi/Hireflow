from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool, ToolContext
from google.genai import types

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting, Profile
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.job_source import JobSource


class HireflowTools:
    """ADK tools exposing the pipeline steps to the router agent."""

    def __init__(self, sources: list[JobSource], gemini: GeminiClient) -> None:
        self._sources = sources
        self._gemini = gemini

    async def search_jobs(self, query: str, tool_context: ToolContext) -> list[dict[str, Any]]:
        """Search all configured job boards for postings matching `query`."""
        jobs: list[JobPosting] = []
        for source in self._sources:
            jobs.extend(await source.search(query=query))
        mappings = [job.to_mapping() for job in jobs]
        tool_context.state["jobs"] = mappings
        return mappings

    async def score_jobs(
        self, jobs: list[dict[str, Any]], profile: dict[str, Any], tool_context: ToolContext
    ) -> list[dict[str, Any]]:
        """Score each job (0-100) against the profile across 5 dimensions."""
        profile_obj = Profile.from_mapping(profile)
        matches = []
        for job_map in jobs:
            job = JobPosting.from_mapping(job_map)
            score, reasons = await self._gemini.score_fit(job=job, profile=profile_obj)
            matches.append({"job": job_map, "score": score, "reasons": reasons})
        tool_context.state["matches"] = matches
        return matches

    async def research_company(self, company: str, tool_context: ToolContext) -> dict[str, Any]:
        """Generate a company-fit research summary."""
        research = await self._gemini.research_company(company)
        tool_context.state.setdefault("research", []).append(research)
        return research

    async def prepare_application(
        self, profile: dict[str, Any], job: dict[str, Any], tool_context: ToolContext
    ) -> dict[str, Any]:
        """Draft, review, and revise a CV + cover letter for a job."""
        draft = await self._gemini.draft_application(profile=Profile.from_mapping(profile), job=JobPosting.from_mapping(job))
        review = await self._gemini.review_application(draft=draft)
        revised = await self._gemini.revise_application(draft=draft, review=review)
        result = {"draft": draft, "review": review, "revised": revised}
        tool_context.state.setdefault("applications", []).append(result)
        return result


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
                FunctionTool(tools.search_jobs),
                FunctionTool(tools.score_jobs),
                FunctionTool(tools.research_company),
                FunctionTool(tools.prepare_application),
            ],
        )
        self._session_service = InMemorySessionService()
        self._runner = Runner(agent=self.agent, app_name="hireflow", session_service=self._session_service)

    async def run(self, user_id: str, session_id: str, profile: dict[str, Any]) -> str:
        message = f"Run the pipeline for this profile: {profile}"
        content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        final_parts: list[str] = []
        async for event in self._runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response():
                for part in event.content.parts:
                    if part.text:
                        final_parts.append(part.text)
        return "\n".join(final_parts)
