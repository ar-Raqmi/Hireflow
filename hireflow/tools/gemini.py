from __future__ import annotations

import json
import os
from typing import Any

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting, Profile, ResumeFinding


class GeminiClient:
    """Wrapper around Gemini via Vertex AI or the Gemini API."""

    def __init__(self, model: str | None = None) -> None:
        from google import genai

        self._model = model or SETTINGS.gemini_model
        use_vertex = (
            SETTINGS.gemini_use_vertex
            and bool(SETTINGS.project_id)
            and bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        )
        if use_vertex:
            if SETTINGS.vertex_location == "global":
                os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "True"
            self._client = genai.Client(
                vertexai=True,
                project=SETTINGS.project_id,
                location=SETTINGS.vertex_location,
            )
        else:
            if not SETTINGS.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is not set (and Vertex AI credentials are missing)")
            self._client = genai.Client(api_key=SETTINGS.gemini_api_key)
        self._async_client = self._client.aio

    async def generate(self, prompt: str) -> str:
        response = await self._async_client.models.generate_content(model=self._model, contents=prompt)
        return response.text

# Todo: recheck the prompt engineering.

    async def parse_resume(self, text: str) -> dict[str, Any]:
        prompt = (
            "Parse this resume into a structured profile. "
            "Residence means where the person lives (city, state/country) — not where they want to work. "
            'Return ONLY JSON: {"name": str, "headline": str, "residence": str, "email": str, '
            '"skills": [str], "experience": [{"role": str, "company": str, "range": str}], '
            '"education": [{"degree": str, "school": str, "range": str}], "certs": [str], '
            '"target_roles": [str], "years_experience": float, "culture_keywords": [str]}\n'
            f"RESUME:\n{text[:24000]}"
        )
        return await self._generate_json(prompt)

    async def audit_resume(self, text: str, profile: Profile) -> dict[str, Any]:
        parsed = profile.to_mapping()
        parsed.pop("resume_text", None)
        prompt = (
            "Audit this resume for ATS health. Parsed profile so far: "
            f"{json.dumps(parsed)}\n"
            "Score overall health 0-100. Each finding: sev=error|warn|tip; type=fix (you can repair it — "
            "give before/after text) or input (you need a value from the user — give field + placeholder); "
            "delta = health points recovered when resolved. "
            'Return ONLY JSON: {"health": int, "findings": [{"id": str, "sev": str, "type": str, '
            '"title": str, "area": str, "detail": str, "delta": int, "before": str|null, "after": str|null, '
            '"field": str|null, "placeholder": str|null}]}\n'
            f"RESUME:\n{text[:24000]}"
        )
        payload = await self._generate_json(prompt)
        return {
            "health": self._clamp_health(payload.get("health")),
            "findings": [
                ResumeFinding.from_mapping(finding)
                for finding in payload.get("findings", [])
                if isinstance(finding, dict)
            ],
        }

    @staticmethod
    def _clamp_health(value: Any) -> int:
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return 0


    async def score_fit(self, job: JobPosting, profile: Profile) -> tuple[int, list[str]]:
        prompt = (
            "Score fit (0-100) between this job and this profile across "
            "five dimensions: skills, experience, location, salary, culture.\n"
            f"JOB: {job.title} @ {job.company} ({job.location})\n"
            f"PROFILE SKILLS: {profile.skills}\n"
            f"PROFILE EXPERIENCE (years): {profile.years_experience}\n"
            f"PROFILE PREFERRED LOCATIONS: {profile.locations or 'any'}\n"
            f"PROFILE SALARY FLOOR: {profile.salary_floor or 'not set'}\n"
            f"PROFILE CULTURE KEYWORDS: {profile.culture_keywords or 'not set'}\n"
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
