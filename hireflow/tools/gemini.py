from __future__ import annotations

import json
from typing import Any

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting, Profile, ResumeFinding


class GeminiClient:
    """Wrapper around Gemini via Vertex AI or the Gemini API."""

    def __init__(self, model: str | None = None) -> None:
        from google import genai

        self._model = model or SETTINGS.gemini_model
        use_vertex = SETTINGS.gemini_use_vertex and bool(SETTINGS.project_id)
        if use_vertex:
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

    async def parse_resume(self, text: str) -> dict[str, Any]:
        prompt = self._profile_prompt(text[:24000])
        return await self._generate_json(prompt)

    async def parse_resume_vision(
        self, pages_bytes: list[bytes], text_hint: str = ""
    ) -> dict[str, Any]:
        from google.genai import types

        parts: list[types.Part] = []
        for data in pages_bytes:
            parts.append(types.Part.from_bytes(data=data, mime_type="image/png"))
        if text_hint:
            parts.append(types.Part.from_text(text=text_hint))
        instruction = self._profile_prompt("")
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=instruction), *parts])]
        response = await self._async_client.models.generate_content(
            model=self._model, contents=contents
        )
        return self._extract_profile(response.text)

    @staticmethod
    def _profile_prompt(text: str) -> str:
        return (
            "Parse this resume into a structured profile. "
            "Residence means where the person lives (city, state/country) - not where they want to work. "
            'Return ONLY JSON: {"name": str, "headline": str, "residence": str, "email": str, '
            '"skills": [str], "experience": [{"role": str, "company": str, "range": str}], '
            '"education": [{"degree": str, "school": str, "range": str}], "certs": [str], '
            '"target_roles": [str], "years_experience": float, "culture_keywords": [str]}\n'
            f"RESUME:\n{text[:24000]}"
        )

    @staticmethod
    def _extract_profile(text: str) -> dict[str, Any]:
        try:
            return json.loads(text[text.find("{") : text.rfind("}") + 1])
        except (ValueError, json.JSONDecodeError):
            return {"raw": text}

    async def audit_resume(self, text: str, profile: Profile) -> dict[str, Any]:
        parsed = profile.to_mapping()
        parsed.pop("resume_text", None)
        prompt = (
            "Audit this resume for ATS health. Parsed profile so far: "
            f"{json.dumps(parsed)}\n"
            "Score overall health 0-100. Each finding: sev=error|warn|tip; type=fix (you can repair it - "
            "give before/after text) or input (you need a value from the user - give field + placeholder); "
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

    async def assess_resume(self, text: str) -> dict[str, Any]:
        """Classify whether the uploaded text is actually a professional résumé.

        The resume parser only checks file extensions, so a random PDF, notes
        file, or article could otherwise sail through to the pipeline. This
        asks the model whether the content looks like a CV. The default is
        conservative: on any LLM failure (or low confidence) we assume it IS a
        resume so a real upload is never blocked by a flaky call.
        """
        if not text or not "".join(text.split()).strip():
            return {"is_resume": False, "confidence": 0.0, "reason": "Empty document - no text to read."}
        prompt = (
            "Decide whether the text below is a professional resume/CV. A resume/CV "
            "represents a person's professional identity: it typically lists a name, "
            "contact info (email/phone), work experience, education, skills, and/or "
            "projects. It is NOT an article, email, chat log, notes, essay, recipe, "
            "contract, invoice, or some other random document. "
            'Return ONLY JSON: {"is_resume": bool, "confidence": float (0-1), "reason": str}\n'
            f"TEXT:\n{text[:8000]}"
        )
        try:
            payload = await self._generate_json(prompt)
        except Exception:
            return {"is_resume": True, "confidence": 0.5, "reason": "could not verify - assuming résumé"}
        is_resume = bool(payload.get("is_resume", True))
        try:
            confidence = float(payload.get("confidence", 0.5) or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        if not is_resume and confidence < 0.6:
            is_resume = True
        return {
            "is_resume": is_resume,
            "confidence": confidence,
            "reason": str(payload.get("reason", "") or ""),
        }

    async def embed(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]] | None:
        """Embed texts via Vertex (real call). Returns None on any failure - never fakes.

        Uses ``SETTINGS.embedding_model`` (default ``gemini-embedding-001``)
        with a ``text-embedding-005`` retry, since availability varies per
        project. Any failure degrades to ``None`` so callers keep their
        existing ordering instead of crashing.
        """
        if not texts:
            return []
        preferred = model or SETTINGS.embedding_model
        candidates = [preferred]
        if preferred.lower() != "text-embedding-005":
            candidates.append("text-embedding-005")
        for candidate in candidates:
            vectors = await self._embed_content(candidate, texts)
            if vectors:
                return vectors
        return None

    async def _embed_content(self, model: str, texts: list[str]) -> list[list[float]] | None:
        response = await self._async_client.models.embed_content(model=model, contents=texts)
        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            return None
        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = getattr(embedding, "values", None)
            if not values:
                return None
            vectors.append([float(value) for value in values])
        return vectors or None

    async def grounded_search(self, query: str) -> list[dict[str, str]]:
        """Google Search grounded retrieval - returns [{title, uri, domain}] for a query.

        Uses Vertex (or Gemini API) Google Search grounding via the
        ``google_search`` tool so the model returns real, current
        source URLs (no fragile scraping). Raises on failure so the caller can
        surface the reason; returns [] only if grounding genuinely returned no
        sources.
        """
        from google.genai import types

        tool = types.Tool(google_search=types.GoogleSearch())
        response = await self._async_client.models.generate_content(
            model=self._model,
            contents=query,
            config=types.GenerateContentConfig(tools=[tool]),
        )
        candidate = response.candidates[0] if response.candidates else None
        metadata = candidate.grounding_metadata if candidate else None
        chunks = metadata.grounding_chunks if metadata else None
        results: list[dict[str, str]] = []
        for chunk in chunks or []:
            web = chunk.web
            if web and web.uri:
                results.append(
                    {
                        "title": web.title or "",
                        "uri": web.uri,
                        "domain": web.domain or "",
                    }
                )
        if not results and response.text:
            results = self._extract_urls(response.text)
        return results

    @staticmethod
    def _extract_urls(text: str) -> list[dict[str, str]]:
        import re

        found: list[dict[str, str]] = []
        seen: set[str] = set()
        for m in re.finditer(r"https?://[^\s)\]>\"']+", text or ""):
            url = m.group(0).rstrip(".,;")
            if url in seen:
                continue
            seen.add(url)
            found.append({"title": "", "uri": url, "domain": ""})
        return found

    async def expand_query(self, roles: list[str], skills: list[str] | None = None) -> list[str]:
        if not roles:
            return []
        prompt = (
            "You are expanding a job search into broader role synonyms so a job "
            "agent retrieves more matches. Return ONLY a JSON array of strings. "
            "For each role, give the original plus 2-4 closely-related role "
            "titles a recruiter would actually post. Be concrete (e.g. "
            "'Machine Learning Engineer'), not abstract. Do not add seniority "
            "tiers or locations.\n"
            f"ROLES: {json.dumps(roles)}\n"
            f"SKILLS: {json.dumps(skills or [])}\n"
            'Return ONLY JSON: ["related role 1", "related role 2", ...]'
        )
        try:
            payload = await self._generate_json(prompt)
        except Exception:
            return list(roles)
        terms: list[str] = []
        if isinstance(payload, list):
            terms = [str(item).strip() for item in payload if str(item).strip()]
        elif isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list):
                    terms.extend(str(item).strip() for item in value if str(item).strip())
        return terms or list(roles)

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
