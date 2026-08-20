from __future__ import annotations

from hireflow.agents.base_agent import BaseAgent
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.job_source import JobSource


class SearchAgent(BaseAgent):
    """Discovers new job postings from configured keyless job sources."""

    name = "search"

    def __init__(self, sources: list[JobSource]) -> None:
        self._sources = sources

    async def run(self, context: dict) -> dict:
        profile = context.get("profile")
        query = self._build_query(profile) if profile else context.get("query", "")
        jobs = []
        for source in self._sources:
            jobs.extend(await source.search(query=query))
        return {"jobs": jobs}

    def _build_query(self, profile) -> str:
        roles = " ".join(profile.target_roles)
        location = " ".join(profile.locations)
        return f"{roles} {location}".strip()


class MatchAgent(BaseAgent):
    """Scores jobs against a profile using Gemini reasoning."""

    name = "match"

    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    async def run(self, context: dict) -> dict:
        profile = context.get("profile")
        jobs = context.get("jobs", [])
        matches = []
        for job in jobs:
            score, reasons = await self._gemini.score_fit(job=job, profile=profile)
            matches.append({"job": job, "score": score, "reasons": reasons})
        return {"matches": matches}


class ResearchAgent(BaseAgent):
    """Enriches top matches with company research (AI-generated)."""

    name = "research"

    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    async def run(self, context: dict) -> dict:
        matches = context.get("matches", [])
        enriched = []
        for match in matches:
            research = await self._gemini.research_company(match["job"].company)
            enriched.append({**match, "research": research})
        return {"matches": enriched}


class PrepareAgent(BaseAgent):
    """Drafter -> Reviewer -> Revise pipeline for CV + cover letter."""

    name = "prepare"

    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    async def run(self, context: dict) -> dict:
        profile = context.get("profile")
        match = context.get("match")
        draft = await self._gemini.draft_application(profile=profile, job=match["job"])
        review = await self._gemini.review_application(draft=draft)
        revised = await self._gemini.revise_application(draft=draft, review=review)
        return {"draft": draft, "review": review, "revised": revised}


class RouterAgent(BaseAgent):
    """Orchestrates sub-agents based on the incoming event."""

    name = "router"

    def __init__(self, search: SearchAgent, match: MatchAgent, research: ResearchAgent, prepare: PrepareAgent) -> None:
        self._search = search
        self._match = match
        self._research = research
        self._prepare = prepare

    async def run(self, context: dict) -> dict:
        event = context.get("event", "search")
        if event == "search":
            return await self._search.run(context)
        if event == "match":
            return await self._match.run(context)
        if event == "prepare":
            return await self._prepare.run(context)
        return {"matches": await self._research.run(context)}