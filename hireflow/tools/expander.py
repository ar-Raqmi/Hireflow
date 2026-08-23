from __future__ import annotations

from typing import Any

from hireflow.config import SETTINGS
from hireflow.tools.gemini import GeminiClient


class QueryExpander:
    """Expands target roles into related role synonyms for broader search.

    Wraps ``GeminiClient.expand_query`` (the real LLM) with an in-memory cache
    and a deterministic fallback synonym map so search still varies (and never
    ices a run) even if the LLM call fails or is disabled.
    """

    _SYNONYMS: dict[str, list[str]] = {
        "ml": [
            "Machine Learning Engineer",
            "ML Engineer",
            "AI Engineer",
            "Deep Learning Engineer",
            "MLOps Engineer",
        ],
        "machine learning": [
            "Machine Learning Engineer",
            "ML Engineer",
            "AI Engineer",
            "Deep Learning Engineer",
        ],
        "data scientist": [
            "Data Scientist",
            "Data Analyst",
            "Machine Learning Engineer",
            "Analytics Engineer",
        ],
        "data": [
            "Data Engineer",
            "Data Scientist",
            "Data Analyst",
            "Analytics Engineer",
        ],
        "software engineer": [
            "Software Engineer",
            "Backend Engineer",
            "Full-Stack Developer",
            "Application Engineer",
        ],
        "backend": [
            "Backend Engineer",
            "Backend Developer",
            "Software Engineer",
        ],
        "frontend": [
            "Frontend Engineer",
            "Frontend Developer",
            "Web Developer",
        ],
        "full stack": [
            "Full-Stack Engineer",
            "Full-Stack Developer",
            "Web Engineer",
        ],
        "devops": [
            "DevOps Engineer",
            "Cloud Engineer",
            "Infrastructure Engineer",
            "Site Reliability Engineer",
        ],
        "sre": [
            "Site Reliability Engineer",
            "DevOps Engineer",
            "Cloud Engineer",
        ],
        "cloud": [
            "Cloud Engineer",
            "DevOps Engineer",
            "Cloud Architect",
        ],
        "security": [
            "Security Engineer",
            "Cybersecurity Engineer",
            "Application Security Engineer",
        ],
        "mobile": [
            "Mobile Engineer",
            "iOS Engineer",
            "Android Engineer",
        ],
        "product manager": [
            "Product Manager",
            "Product Owner",
            "Technical Program Manager",
        ],
        "qa": [
            "QA Engineer",
            "Test Engineer",
            "Quality Engineer",
        ],
    }

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self._gemini = gemini
        self._cache: dict[tuple[tuple[str, ...], tuple[str, ...]], list[str]] = {}

    async def expand(
        self,
        roles: list[str],
        skills: list[str] | None = None,
        limit: int | None = None,
    ) -> list[str]:
        skills = skills or []
        key = (tuple(roles), tuple(skills))
        if key in self._cache:
            terms = self._cache[key]
        else:
            terms = await self._llm_expand(roles, skills) or self._fallback(roles)
            terms = self._dedupe([term for term in terms if term and term.strip()]) or list(roles)
            self._cache[key] = terms
        cap = limit if limit and limit > 0 else len(terms)
        return terms[:cap]

    async def _llm_expand(self, roles: list[str], skills: list[str]) -> list[str]:
        if self._gemini is None or not SETTINGS.query_expansion:
            return []
        try:
            return await self._gemini.expand_query(roles, skills)
        except Exception:
            return []

    def _fallback(self, roles: list[str]) -> list[str]:
        expanded: list[str] = []
        for role in roles:
            lowered = role.strip().lower()
            added = False
            for key, synonyms in self._SYNONYMS.items():
                if key in lowered or lowered in key:
                    expanded.extend(synonyms)
                    added = True
                    break
            if not added:
                expanded.append(role)
        return expanded

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: list[str] = []
        for value in values:
            if value not in seen:
                seen.append(value)
        return seen

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state.pop("_gemini", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._gemini = None