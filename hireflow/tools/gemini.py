from __future__ import annotations

import json
from typing import Any

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting, Profile


class GeminiClient:
    """Wrapper around Gemini via Vertex AI or the Gemini API."""

    def __init__(self, model: str | None = None) -> None:
        from google import genai

        self._model = model or SETTINGS.gemini_model
        if SETTINGS.gemini_use_vertex:
            self._client = genai.Client(
                vertexai=True,
                project=SETTINGS.project_id,
                location=SETTINGS.vertex_location,
            )
        else:
            self._client = genai.Client(api_key=SETTINGS.gemini_api_key)

    async def generate(self, prompt: str) -> str:
        response = await self._client.models.generate_content(model=self._model, contents=prompt)
        return response.text

    async def score_fit(self, job: JobPosting, profile: Profile) -> tuple[int, list[str]]:
        prompt = (
            f"Score fit (0-100) between this job and this profile across "
            f"skills, experience, location, salary, culture.\n"
            f"JOB: {job.title} @ {job.company} ({job.location})\n"
            f"PROFILE SKILLS: {profile.skills}\n"
            f"Return JSON: {{\"score\": int, \"reasons\": [str]}}"
        )
        payload = await self._generate_json(prompt)
        return int(payload.get("score", 0)), list(payload.get("reasons", []))

    async def research_company(self, company: str) -> dict[str, Any]:
        prompt = f"Research {company}: summary, product, culture keywords, why a candidate might fit."
        text = await self.generate(prompt)
        return {"company": company, "summary": text}

    async def draft_application(self, profile: Profile, job: JobPosting) -> dict[str, str]:
        prompt = (
            f"Draft a tailored CV summary + cover letter for this job using ONLY the profile.\n"
            f"JOB: {job.title} @ {job.company}\n"
            f"PROFILE: {profile.resume_text}\n"
            f"Return JSON: {{\"cv\": str, \"cover_letter\": str}}"
        )
        return self._stringify(await self._generate_json(prompt))

    async def review_application(self, draft: dict[str, str]) -> dict[str, str]:
        prompt = f"Critique this application draft:\n{draft}"
        return {"critique": await self.generate(prompt)}

    async def revise_application(self, draft: dict[str, str], review: dict[str, str]) -> dict[str, str]:
        prompt = f"Revise this draft based on the review.\nDRAFT: {draft}\nREVIEW: {review}"
        return self._stringify(await self._generate_json(prompt))

    async def _generate_json(self, prompt: str) -> dict[str, Any]:
        text = await self.generate(prompt)
        try:
            return json.loads(text[text.find("{") : text.rfind("}") + 1])
        except (ValueError, json.JSONDecodeError):
            return {"raw": text}

    @staticmethod
    def _stringify(payload: dict[str, Any]) -> dict[str, str]:
        return {str(key): str(value) for key, value in payload.items()}
