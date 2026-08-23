from __future__ import annotations

import math

from hireflow.config import SETTINGS
from hireflow.domain import JobPosting
from hireflow.tools.gemini import GeminiClient


class EmbeddingRanker:
    """Semantic tie-break on already-scored jobs (cosine over real embeddings).

    The 5-dimension Gemini ``score_fit`` order stays the primary ranking; this
    re-ranks only jobs that tie, using cosine similarity between the profile
    query and each job's title/description embedded via ``GeminiClient.embed``.
    If embeddings are unavailable (model not enabled, quota, error) it returns
    ``None`` so the caller keeps the existing order — never fakes a vector.
    """

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self._gemini = gemini
        self._model = SETTINGS.embedding_model

    async def rank(
        self, jobs: list[JobPosting], query: str
    ) -> list[JobPosting] | None:
        if not jobs or not query or self._gemini is None:
            return None
        texts = [self._job_text(job) for job in jobs]
        vectors = await self._gemini.embed([query, *texts], model=self._model)
        if vectors is None or len(vectors) != len(jobs) + 1:
            return None
        query_vector = vectors[0]
        ranked: list[tuple[float, int]] = []
        for index, job_vector in enumerate(vectors[1:], start=1):
            cosine = self._cosine(query_vector, job_vector)
            if cosine is None:
                return None
            ranked.append((cosine, index - 1))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [jobs[index] for _, index in ranked]

    @staticmethod
    def _job_text(job: JobPosting) -> str:
        raw = job.raw_data if isinstance(job.raw_data, dict) else {}
        description = str(raw.get("description", "") or "")[:1200]
        return " ".join(
            part for part in (job.title, job.company, job.location, description) if part
        ).strip()

    @staticmethod
    def _cosine(first: list[float], second: list[float]) -> float | None:
        if not first or len(first) != len(second):
            return None
        dot = sum(a * b for a, b in zip(first, second))
        norm_first = math.sqrt(sum(a * a for a in first))
        norm_second = math.sqrt(sum(b * b for b in second))
        if not norm_first or not norm_second:
            return None
        return dot / (norm_first * norm_second)