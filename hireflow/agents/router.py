from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

from hireflow.agents.base_agent import BaseAgent
from hireflow.config import SETTINGS
from hireflow.domain import Application, ApplicationStatus, JobPosting, Profile, WorkTypeClassifier
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.job_source import JobSource

_WORK_MODE_VALUES = {"remote", "hybrid", "onsite"}


def _default_caps() -> dict[str, int]:
    return {
        "max_jobs": SETTINGS.pipeline_max_jobs,
        "max_score": SETTINGS.pipeline_max_score,
        "max_prep": SETTINGS.pipeline_max_prep,
        "max_research": SETTINGS.pipeline_max_research,
    }


class SearchAgent(BaseAgent):
    """Discovers and de-duplicates jobs from the keyless source registry.

    Prompt-engineering lives in ``_build_query``: target roles first, falling
    back to the resume's opening text when no roles are declared. A source that
    is down degrades to ``[]`` and is recorded in ``context["errors"]``.
    """

    name = "search"

    def __init__(self, sources: list[JobSource], caps: dict[str, int] | None = None) -> None:
        self._sources = sources
        self._caps = caps or _default_caps()

    async def run(self, context: dict) -> dict:
        profile: Profile = context["profile"]
        errors: list[str] = context["errors"]
        query = self._build_query(profile)
        jobs: list[JobPosting] = []
        seen: set[str] = set()
        per_source = max(1, self._caps["max_jobs"] // max(1, len(self._sources)))
        for source in self._sources:
            try:
                found = await source.search(
                    query=query,
                    limit=per_source,
                    work_type=profile.work_type,
                    locations=profile.locations,
                )
            except Exception as exc:  # noqa: BLE001 - a down source is non-fatal
                errors.append(f"{source.name}: {type(exc).__name__}: {str(exc)[:200]}")
                found = []
            if source.last_error:
                errors.append(f"{source.name}: {source.last_error}")
            label = source.name
            if source.name == "freehire" and profile.locations:
                label = f"freehire({','.join(profile.locations)})"
            await self._emit("search", f"{label}: {len(found)} found")
            for job in found:
                if not job.id or job.id in seen:
                    continue
                if not self._passes_work_gate(job, profile.work_type):
                    continue
                seen.add(job.id)
                jobs.append(job)
                if len(jobs) >= self._caps["max_jobs"]:
                    return {"jobs": [job.to_mapping() for job in jobs]}
        return {"jobs": [job.to_mapping() for job in jobs]}

    def _build_query(self, profile: Profile) -> str:
        query = " ".join(profile.target_roles).strip()
        return query or profile.resume_text[:300]

    def _passes_work_gate(self, job: JobPosting, work_type: str) -> bool:
        preference = (work_type or "any").strip().lower()
        if preference == "any":
            return True
        declared = str(job.raw_data.get("work_mode", "") or "").strip().lower()
        actual = declared if declared in _WORK_MODE_VALUES else self._infer_work_type(job)
        if actual == "any":
            return True
        return preference == actual

    def _infer_work_type(self, job: JobPosting) -> str:
        description = job.raw_data.get("description", "") if isinstance(job.raw_data, dict) else ""
        return WorkTypeClassifier.classify(f"{job.title} {job.location} {description}")


class MatchAgent(BaseAgent):
    """Scores jobs (0-100) against the profile across the five dimensions.

    Uses ``GeminiClient.score_fit`` — the 5-dimension scoring prompt (skills,
    experience, location, salary, culture). Emits per-job ``match`` progress.
    """

    name = "match"

    def __init__(self, gemini: GeminiClient, caps: dict[str, int] | None = None) -> None:
        self._gemini = gemini
        self._caps = caps or _default_caps()

    async def run(self, context: dict) -> dict:
        profile: Profile = context["profile"]
        jobs: list[dict[str, Any]] = context["jobs"]
        errors: list[str] = context["errors"]
        scored: list[dict[str, Any]] = []
        total = min(len(jobs), self._caps["max_score"])
        best: tuple[int, str, str] | None = None
        for index, job_map in enumerate(jobs[: self._caps["max_score"]], start=1):
            job = JobPosting.from_mapping(job_map)
            try:
                score, reasons = await self._gemini.score_fit(job=job, profile=profile)
            except Exception as exc:  # noqa: BLE001 - keep scoring going past a bad call
                errors.append(f"match {job.id}: {type(exc).__name__}: {str(exc)[:200]}")
                continue
            scored.append({"job": job_map, "score": score, "reasons": reasons})
            if best is None or score > best[0]:
                best = (score, job.company, job.title)
            detail = f"scoring {total} jobs… {index}/{total} done"
            if best is not None:
                detail += f" (best so far: {best[0]} {best[1]} · {best[2]})"
            await self._emit("match", detail)
        scored.sort(key=lambda match: match["score"], reverse=True)
        return {"matches": scored}


class ResearchAgent(BaseAgent):
    """Enriches top matches with company research.

    Uses ``GeminiClient.research_company``. Companies are de-duplicated so a
    shared employer is researched once. Emits per-company ``research`` progress.
    """

    name = "research"

    def __init__(self, gemini: GeminiClient, caps: dict[str, int] | None = None) -> None:
        self._gemini = gemini
        self._caps = caps or _default_caps()

    async def run(self, context: dict) -> dict:
        matches: list[dict[str, Any]] = context["matches"]
        errors: list[str] = context["errors"]
        researched: dict[str, dict[str, Any]] = {}
        chosen = matches[: self._caps["max_research"]]
        companies = [
            JobPosting.from_mapping(match["job"]).company
            for match in chosen
            if JobPosting.from_mapping(match["job"]).company
        ]
        total = len(dict.fromkeys(companies))
        done = 0
        for match in chosen:
            job = JobPosting.from_mapping(match["job"])
            company = job.company
            if not company:
                continue
            if company not in researched:
                done += 1
                try:
                    researched[company] = await self._gemini.research_company(company)
                except Exception as exc:  # noqa: BLE001 - non-fatal
                    errors.append(f"research {company}: {type(exc).__name__}: {str(exc)[:200]}")
                    researched[company] = {"company": company, "summary": "", "error": str(exc)[:200]}
                await self._emit(
                    "research",
                    f"researching {total} companies… {done}/{total} done ({company})",
                )
        for match in matches:
            job = JobPosting.from_mapping(match["job"])
            match["research"] = researched.get(job.company) or {}
        return {"matches": matches}


class PrepareAgent(BaseAgent):
    """Drafter -> Reviewer -> Revise for CV + cover letter.

    Uses ``GeminiClient.draft_application`` / ``review_application`` /
    ``revise_application``. Emits per-application ``prepare`` progress.
    """

    name = "prepare"

    def __init__(self, gemini: GeminiClient, caps: dict[str, int] | None = None) -> None:
        self._gemini = gemini
        self._caps = caps or _default_caps()

    async def run(self, context: dict) -> dict:
        profile: Profile = context["profile"]
        matches: list[dict[str, Any]] = context["matches"]
        errors: list[str] = context["errors"]
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
            except Exception as exc:  # noqa: BLE001 - non-fatal
                errors.append(f"prepare {job.id}: {type(exc).__name__}: {str(exc)[:200]}")
                continue
            drafts[job.id] = {"draft": draft, "review": review, "revised": revised}
            prepared += 1
            await self._emit(
                "prepare",
                f"drafting CV + cover letter… {prepared}/{self._caps['max_prep']} done "
                f"({job.company} · {job.title})",
            )
        return {"drafts": drafts}


class RouterAgent(BaseAgent):
    """Orchestrates Search -> Match -> Research -> Prepare as one pipeline.

    The server-side executor behind ``/pipeline/run`` (SSE). Runs the five
    agents in order (parse -> audit -> search -> score -> research -> prepare ->
    approve-gate), threading a ``progress`` callback so the SSE stream can tag
    which agent is working. Keeps the same result shape the CLI/SSE expect.
    """

    name = "router"

    def __init__(
        self,
        sources: list[JobSource],
        gemini: GeminiClient,
        caps: dict[str, int] | None = None,
        progress: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        self._gemini = gemini
        self._caps = caps or _default_caps()
        self._search = SearchAgent(sources=sources, caps=self._caps)
        self._match = MatchAgent(gemini=gemini, caps=self._caps)
        self._research = ResearchAgent(gemini=gemini, caps=self._caps)
        self._prepare = PrepareAgent(gemini=gemini, caps=self._caps)
        for agent in (self._search, self._match, self._research, self._prepare):
            agent.progress = progress
        self._progress = progress

    @property
    def gemini(self) -> GeminiClient:
        return self._gemini

    @property
    def sources(self) -> list[JobSource]:
        return self._search._sources

    async def run(self, context: dict) -> dict:
        return await self.run_pipeline(context["profile"])

    async def run_pipeline(
        self,
        profile: Profile,
        progress: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        if progress is not None:
            for agent in (self._search, self._match, self._research, self._prepare):
                agent.progress = progress
            self._progress = progress
        errors: list[str] = []
        context: dict[str, Any] = {"profile": profile, "errors": errors}

        await self._emit(
            "parse",
            f"resume ready — {len(profile.skills)} skills · "
            f"{profile.years_experience} yrs · roles {profile.target_roles or 'inferred'}",
        )
        await self._audit(profile, errors)

        search = await self._search.run(context)
        context["jobs"] = search["jobs"]
        match = await self._match.run(context)
        context["matches"] = match["matches"]
        research = await self._research.run(context)
        context["matches"] = research["matches"]
        prepare = await self._prepare.run(context)
        drafts = prepare["drafts"]

        applications = self._build_applications(context["matches"], profile, drafts)
        await self._emit_approve(applications)
        return self._shape_result(profile, search["jobs"], context["matches"], applications, drafts, errors)

    async def _emit(self, stage: str, detail: str) -> None:
        if self._progress is not None:
            await self._progress(stage, detail)

    async def _audit(self, profile: Profile, errors: list[str]) -> None:
        if not profile.resume_text:
            await self._emit("audit", "no resume text to audit — skipping ATS check")
            return
        try:
            audit = await self._gemini.audit_resume(profile.resume_text, profile)
            health = int(audit.get("health", 0) or 0)
            findings = audit.get("findings", [])
            await self._emit("audit", f"ATS health {health}/100 · {len(findings)} findings")
        except Exception as exc:  # noqa: BLE001 - non-fatal
            errors.append(f"audit: {type(exc).__name__}: {str(exc)[:200]}")

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

    async def _emit_approve(self, applications: list[Application]) -> None:
        drafted = sum(1 for app in applications if app.status == ApplicationStatus.DRAFTED)
        routed = sum(1 for app in applications if app.status == ApplicationStatus.ROUTED)
        matched = sum(1 for app in applications if app.status == ApplicationStatus.MATCHED)
        handoff = sum(1 for app in applications if app.human_handoff)
        await self._emit(
            "approve",
            f"{drafted} drafted · {routed} routed · {matched} matched · {handoff} needs human",
        )

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

    def _shape_result(
        self,
        profile: Profile,
        jobs: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        applications: list[Application],
        drafts: dict[str, dict[str, Any]],
        errors: list[str],
    ) -> dict[str, Any]:
        needs_human: list[dict[str, Any]] = []
        ranked: list[dict[str, Any]] = []
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

        app_summary: list[dict[str, Any]] = []
        for application in applications:
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
            "profile_id": profile.id,
            "jobs_found": len(jobs),
            "jobs": jobs,
            "matches": ranked,
            "applications": app_summary,
            "application_records": [app.to_mapping() for app in applications],
            "drafts": {
                job_id: {
                    "cv": package.get("revised", {}).get("cv") or package.get("draft", {}).get("cv", ""),
                    "cover_letter": package.get("revised", {}).get("cover_letter")
                    or package.get("draft", {}).get("cover_letter", ""),
                }
                for job_id, package in drafts.items()
            },
            "needs_human": needs_human,
            "errors": errors,
        }