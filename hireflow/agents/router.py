from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from hireflow.agents.base_agent import BaseAgent
from hireflow.agents.career_source import CareerSourceAgent
from hireflow.config import SETTINGS
from hireflow.domain import Application, ApplicationStatus, JobPosting, Profile, WorkTypeClassifier
from hireflow.tools.embeddings import EmbeddingRanker
from hireflow.tools.expander import QueryExpander
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.geo import LocationMapper
from hireflow.tools.job_source import JobSource
from hireflow.tools.webfetch import WebFetchSource

_WORK_MODE_VALUES = {"remote", "hybrid", "onsite"}
_REMOTEISH_MARKERS = ("remote", "worldwide", "anywhere", "distributed")
_GEO_CAPABLE = {"freehire", "freehire:seek", "freehire:mycareersfuture"}
_DEEP_QUERY_SOURCES = {"gemini_web"}
_SPAM_DOMAINS = ("whatjobs.com",)
_REMOTE_RESTRICTED_RE = re.compile(
    r"\b(us|usa|u\.s\.|united states|america|canada|mexico|brazil|uk|united kingdom|"
    r"england|europe|eu|germany|france|netherlands|spain|poland|portugal|ireland|"
    r"israel|india|singapore|indonesia|philippines|vietnam|thailand|japan|china|"
    r"hong kong|taiwan|australia|new zealand|emea|latam)\b"
)


def _default_caps() -> dict[str, int]:
    return {
        "max_jobs": SETTINGS.pipeline_max_jobs,
        "max_score": SETTINGS.pipeline_max_score,
        "max_prep": SETTINGS.pipeline_max_prep,
        "max_research": SETTINGS.pipeline_max_research,
    }


class SearchAgent(BaseAgent):
    """Discovers jobs from the keyless source registry as a search agent, not a keyword fetcher.

    Uses ``QueryExpander`` (Gemini) to turn target roles into many related role
    queries, issues multiple query variants against geo-capable sources so
    results vary run-to-run, then gate-then-caps: work-type gate -> location
    gate -> recency filter -> cross-run seen-job dedup -> per-company diversity
    -> cap. A source that is down degrades to ``[]`` and is recorded in
    ``context["errors"]``.
    """

    name = "search"

    def __init__(
        self,
        sources: list[JobSource],
        caps: dict[str, int] | None = None,
        expander: QueryExpander | None = None,
    ) -> None:
        self._sources = sources
        self._caps = caps or _default_caps()
        self._expander = expander if expander is not None else QueryExpander(gemini=None)
        self._mapper = LocationMapper()

    async def run(self, context: dict) -> dict:
        profile: Profile = context["profile"]
        errors: list[str] = context["errors"]
        seed = int(context.get("seed", 0) or 0)
        offset = int(context.get("offset", 0) or 0)
        seen: set[str] = set(context.get("seen_jobs") or [])

        base = self._build_query(profile)
        if SETTINGS.query_expansion:
            queries = await self._expander.expand(base, profile.skills, limit=SETTINGS.expansion_terms)
        else:
            queries = base
        queries = self._rotate(queries, seed) if queries else base
        await self._emit(
            "search",
            f"reading your profile: {len(base)} target role(s) expanded into {len(queries)} live search angles · {len(seen)} roles seen on previous checks",
        )

        per_source = self._per_source_cap()
        fresh: list[JobPosting] = []
        repeat: list[JobPosting] = []
        for source in self._rotate(self._sources, seed):
            if source.name in _DEEP_QUERY_SOURCES and queries:
                angles = ", ".join(q[:48] for q in queries[: SETTINGS.web_discovery_max_calls])
                await self._emit(
                    "search",
                    f"deep web hunt: grounding {min(len(queries), SETTINGS.web_discovery_max_calls)} Google angles ({angles})…",
                )
                source_jobs = await self._collect_deep(
                    source, queries, per_source, profile, errors
                )
            else:
                variants = queries if source.name in _GEO_CAPABLE else queries[:1]
                source_jobs: list[JobPosting] = []
                for query in variants:
                    source_jobs.extend(
                        await self._collect(source, query, per_source, profile, offset, errors)
                    )
            source_jobs = self._dedupe(
                self._cap_company(source_jobs, SETTINGS.diversity_max_same_company)
            )
            kept = [job for job in source_jobs if job.id not in seen]
            fresh.extend(kept)
            repeat.extend([job for job in source_jobs if job.id in seen])
            summary = getattr(source, "last_summary", "")
            label = self._source_label(source, profile)
            if summary:
                detail = f"{source.name}: {summary}"
            elif kept:
                detail = f"{label}: {len(kept)} new · {len(source_jobs) - len(kept)} seen"
            else:
                first_role = next((r for r in profile.target_roles if r), None)
                detail = (
                    f"{label}: no matching {first_role or 'role'} postings right now - moving on"
                )
            await self._emit("search", detail)

        fresh = self._dedupe(self._cap_company(fresh, SETTINGS.diversity_max_same_company))
        repeat = self._dedupe(self._cap_company(repeat, SETTINGS.diversity_max_same_company))
        jobs = fresh + repeat
        jobs = self._rotate(jobs, seed)[: self._caps["max_jobs"]]
        return {
            "jobs": [job.to_mapping() for job in jobs],
            "fresh": len(fresh),
            "new_jobs": len(jobs),
        }

    async def _collect_deep(
        self,
        source: Any,
        queries: list[str],
        limit: int,
        profile: Profile,
        errors: list[str],
    ) -> list[JobPosting]:
        try:
            found = await source.search(
                query=queries[0] if queries else "",
                limit=limit,
                work_type=profile.work_type,
                locations=profile.locations,
                queries=queries,
            )
        except Exception as exc:
            errors.append(f"{source.name}: {type(exc).__name__}: {str(exc)[:200]}")
            found = []
        if source.last_error:
            errors.append(f"{source.name}: {source.last_error}")
        return [
            job
            for job in found
            if job.id
            and not self._is_spam(job)
            and self._passes_work_gate(job, profile.work_type)
            and self._passes_location(job, profile)
            and not self._is_stale(job)
        ]

    async def _collect(
        self,
        source: JobSource,
        query: str,
        limit: int,
        profile: Profile,
        offset: int,
        errors: list[str],
    ) -> list[JobPosting]:
        kwargs = {
            "query": query,
            "limit": limit,
            "work_type": profile.work_type,
            "locations": profile.locations,
        }
        if source.name in _GEO_CAPABLE:
            kwargs["offset"] = offset
        try:
            found = await source.search(**kwargs)
        except Exception as exc:
            errors.append(f"{source.name}: {type(exc).__name__}: {str(exc)[:200]}")
            found = []
        if source.last_error:
            errors.append(f"{source.name}: {source.last_error}")
        return [
            job
            for job in found
            if job.id
            and not self._is_spam(job)
            and self._passes_work_gate(job, profile.work_type)
            and self._passes_location(job, profile)
            and not self._is_stale(job)
        ]

    @staticmethod
    def _is_spam(job: JobPosting) -> bool:
        url = (job.post_url or "").lower()
        return any(domain in url for domain in _SPAM_DOMAINS)

    def _build_query(self, profile: Profile) -> list[str]:
        roles = [role for role in profile.target_roles if role]
        if roles:
            return roles
        text = (profile.resume_text or "").strip()
        if text:
            return [text[:120]]
        return ["software engineer"]

    def _per_source_cap(self) -> int:
        divisor = max(1, len(self._sources))
        return max(4, math.ceil(self._caps["max_jobs"] / divisor) * 2)

    def _source_label(self, source: JobSource, profile: Profile) -> str:
        if source.name == "freehire" and profile.locations:
            return f"freehire({','.join(profile.locations)})"
        return source.name

    def _passes_location(self, job: JobPosting, profile: Profile) -> bool:
        if profile.work_type == "remote":
            return True
        location = (job.location or "").strip()
        if not location:
            return True
        lowered = location.lower()
        remoteish = any(marker in lowered for marker in _REMOTEISH_MARKERS)
        if not remoteish:
            if not profile.locations:
                return True
            tokens = self._location_tokens(profile)
            return any(token and token in lowered for token in tokens)
        remainder = lowered
        for marker in _REMOTEISH_MARKERS:
            remainder = remainder.replace(marker, " ")
        remainder = re.sub(r"[^a-z, ]+", " ", remainder).strip(" ,")
        if not remainder:
            return True
        tokens = self._location_tokens(profile)
        if any(token and token in remainder for token in tokens):
            return True
        return not _REMOTE_RESTRICTED_RE.search(remainder)

    def _location_tokens(self, profile: Profile) -> list[str]:
        tokens: list[str] = []
        for loc in profile.locations:
            token = loc.strip().lower()
            if token and token not in tokens:
                tokens.append(token)
        geo = self._mapper.map(profile.locations)
        for code in geo["countries"]:
            name = self._mapper.country_name(code)
            if name and name not in tokens:
                tokens.append(name)
        return tokens

    def _is_stale(self, job: JobPosting) -> bool:
        if not job.posted_at or SETTINGS.job_recency_days <= 0:
            return False
        age = self._utcnow() - self._as_utc(job.posted_at)
        return age.days > SETTINGS.job_recency_days

    def _dedupe(self, jobs: list[JobPosting]) -> list[JobPosting]:
        seen: set[str] = set()
        unique: list[JobPosting] = []
        for job in jobs:
            if not job.id or job.id in seen:
                continue
            seen.add(job.id)
            unique.append(job)
        return unique

    def _cap_company(self, jobs: list[JobPosting], max_per_company: int) -> list[JobPosting]:
        if max_per_company <= 0:
            return jobs
        counts: dict[str, int] = {}
        capped: list[JobPosting] = []
        for job in jobs:
            company = (job.company or "").strip().lower()
            if not company:
                capped.append(job)
                continue
            if counts.get(company, 0) >= max_per_company:
                continue
            counts[company] = counts.get(company, 0) + 1
            capped.append(job)
        return capped

    @staticmethod
    def _rotate(items: list[Any], seed: int) -> list[Any]:
        if not items:
            return items
        offset = seed % len(items)
        return items[offset:] + items[:offset]

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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

    Uses ``GeminiClient.score_fit`` - the 5-dimension scoring prompt (skills,
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
            except Exception as exc:
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
        await self._semantic_rerank(profile, scored, errors)
        return {"matches": scored}

    async def _semantic_rerank(
        self, profile: Profile, scored: list[dict[str, Any]], errors: list[str]
    ) -> None:
        if not SETTINGS.semantic_search or not scored:
            await self._emit("match", "semantic re-rank off (SEMANTIC_SEARCH disabled)")
            return
        jobs = [JobPosting.from_mapping(match["job"]) for match in scored]
        try:
            ranker = EmbeddingRanker(self._gemini)
            ranked = await ranker.rank(jobs, self._rerank_query(profile))
        except Exception as exc:
            errors.append(f"semantic re-rank: {type(exc).__name__}: {str(exc)[:200]}")
            ranked = None
        if ranked is None:
            await self._emit(
                "match", "semantic re-rank off (embeddings unavailable - Gemini scores kept)"
            )
            return
        order = {job.id: index for index, job in enumerate(ranked)}
        scored.sort(
            key=lambda match: (
                -int(match.get("score", 0)),
                order.get(match["job"].get("id", ""), len(order)),
            )
        )
        await self._emit("match", "semantic re-rank on (cosine tie-break on scored jobs)")

    @staticmethod
    def _rerank_query(profile: Profile) -> str:
        parts = [
            part
            for part in (
                *(profile.target_roles or []),
                *(profile.skills or []),
                *(profile.locations or []),
            )
            if part
        ]
        return " ".join(parts).strip() or "software engineer"


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
            job.company
            for match in chosen
            if (job := JobPosting.from_mapping(match["job"])).company
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
                except Exception as exc:
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
            except Exception as exc:
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
        self._search = SearchAgent(
            sources=sources,
            caps=self._caps,
            expander=QueryExpander(gemini=gemini),
        )
        self._match = MatchAgent(gemini=gemini, caps=self._caps)
        self._career = CareerSourceAgent(fetcher=WebFetchSource())
        self._research = ResearchAgent(gemini=gemini, caps=self._caps)
        self._prepare = PrepareAgent(gemini=gemini, caps=self._caps)
        for agent in (self._search, self._match, self._career, self._research, self._prepare):
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
        seed: int = 0,
        seen_jobs: list[str] | None = None,
    ) -> dict[str, Any]:
        if progress is not None:
            for agent in (self._search, self._match, self._career, self._research, self._prepare):
                agent.progress = progress
            self._progress = progress
        errors: list[str] = []
        context: dict[str, Any] = {
            "profile": profile,
            "errors": errors,
            "seed": seed,
            "seen_jobs": seen_jobs or [],
        }

        await self._emit(
            "parse",
            f"resume ready - {len(profile.skills)} skills · "
            f"{profile.years_experience} yrs · roles {profile.target_roles or 'inferred'}",
        )
        await self._audit(profile, errors)

        jobs, matches = await self._discover(context, profile, seed, errors)
        context["jobs"] = jobs
        context["matches"] = matches

        context["career_urls"] = await self._discover_companies(context, profile, errors)
        career = await self._career.run(context)
        career_jobs = career["jobs"]
        if career_jobs:
            existing = {str(job_map.get("id", "")) for job_map in context["jobs"]}
            fresh = [job_map for job_map in career_jobs if str(job_map.get("id", "")) not in existing]
            context["jobs"].extend(fresh)
            extra_ctx = dict(context)
            extra_ctx["jobs"] = fresh
            extra = await self._match.run(extra_ctx)
            context["matches"].extend(extra["matches"])
            context["matches"].sort(key=lambda m: int(m.get("score", 0)), reverse=True)

        research = await self._research.run(context)
        context["matches"] = research["matches"]
        prepare = await self._prepare.run(context)
        drafts = prepare["drafts"]

        applications = self._build_applications(context["matches"], profile, drafts)
        await self._emit_approve(applications)
        return self._shape_result(profile, context["jobs"], context["matches"], applications, drafts, errors)

    async def _emit(self, stage: str, detail: str) -> None:
        if self._progress is not None:
            await self._progress(stage, detail)

    async def _discover(
        self,
        context: dict[str, Any],
        profile: Profile,
        seed: int,
        errors: list[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        min_matches = SETTINGS.pipeline_min_matches
        min_strong = SETTINGS.pipeline_min_strong
        min_companies = SETTINGS.pipeline_min_companies
        batch = SETTINGS.pipeline_score_batch
        sweeps = SETTINGS.pipeline_max_search_sweeps
        jobs: list[dict[str, Any]] = []
        scored: list[dict[str, Any]] = []
        known: set[str] = set()

        for sweep in range(sweeps):
            search_ctx = dict(context)
            search_ctx["offset"] = sweep * batch
            search_ctx["seed"] = seed + sweep * 13
            search_ctx.pop("jobs", None)
            search_ctx.pop("matches", None)
            if sweep > 0:
                strong, companies = self._strength(scored)
                await self._emit(
                    "search",
                    f"deep sweep {sweep + 1}: bar not met yet "
                    f"({strong} strong of {min_strong} needed across {companies} companies) "
                    f"- widening the hunt with fresh angles…",
                )
            result = await self._search.run(search_ctx)
            pool = [job for job in result["jobs"] if job.get("id") and job["id"] not in known]
            if not pool:
                await self._emit(
                    "search",
                    f"deep sweep {sweep + 1}: sources exhausted - every posting already reviewed",
                )
                break
            for job in pool:
                known.add(job["id"])
            jobs.extend(pool)
            remaining = pool
            while remaining and len(scored) < min_matches:
                match_ctx = dict(context)
                match_ctx["jobs"] = remaining[:batch]
                match_ctx.pop("matches", None)
                remaining = remaining[batch:]
                scored.extend((await self._match.run(match_ctx))["matches"])
            strong, companies = self._strength(scored)
            if len(scored) >= min_matches:
                if strong >= min_strong and companies >= min_companies:
                    await self._emit(
                        "search",
                        f"deep sweep {sweep + 1}: quality bar met - {strong} strong matches "
                        f"across {companies} companies from {len(jobs)} postings",
                    )
                    break
                if sweep + 1 < sweeps:
                    continue
            if len(scored) >= min_matches:
                await self._emit(
                    "search",
                    f"deep sweep {sweep + 1}: best available - {strong} strong across "
                    f"{companies} companies (search budget reached)",
                )
                break

        scored = self._dedupe_matches(scored)
        scored.sort(key=lambda match: int(match.get("score", 0) or 0), reverse=True)
        return jobs, scored

    @staticmethod
    def _strength(scored: list[dict[str, Any]]) -> tuple[int, int]:
        strong = sum(
            1
            for match in scored
            if int(match.get("score", 0) or 0) >= SETTINGS.approve_threshold_auto
        )
        companies = {
            str((match.get("job") or {}).get("company", "")).strip().lower()
            for match in scored
            if isinstance(match, dict)
        }
        companies.discard("")
        return strong, len(companies)

    @staticmethod
    def _dedupe_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for match in matches:
            job = match.get("job")
            job_id = str(job.get("id", "") or "") if isinstance(job, dict) else ""
            if not job_id:
                by_id[f"__noid__{id(match)}"] = match
                continue
            current = by_id.get(job_id)
            if current is None or int(match.get("score", 0) or 0) > int(current.get("score", 0) or 0):
                by_id[job_id] = match
        return list(by_id.values())

    async def _audit(self, profile: Profile, errors: list[str]) -> None:
        if not profile.resume_text:
            await self._emit("audit", "no resume text to audit - skipping ATS check")
            return
        try:
            audit = await self._gemini.audit_resume(profile.resume_text, profile)
            health = int(audit.get("health", 0) or 0)
            findings = audit.get("findings", [])
            await self._emit("audit", f"ATS health {health}/100 · {len(findings)} findings")
        except Exception as exc:
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

    async def _discover_companies(
        self,
        context: dict[str, Any],
        profile: Profile,
        errors: list[str],
    ) -> list[tuple[str, str]]:
        if not SETTINGS.deep_search:
            return []
        role = ", ".join(role for role in profile.target_roles[:2] if role) or "engineer"
        loc = ", ".join(loc for loc in profile.locations[:2] if loc)
        query = f"companies currently hiring {role} in {loc}".strip()
        await self._emit(
            "career",
            f"company hunt: searching Google for who is hiring {role} in {loc or 'anywhere'} right now…",
        )
        try:
            found = await self._gemini.grounded_companies(query)
        except Exception as exc:
            errors.append(f"company discovery: {type(exc).__name__}: {str(exc)[:200]}")
            await self._emit(
                "career",
                "company hunt: grounding unavailable - falling back to careers-page probes",
            )
            return []
        clean: list[tuple[str, str]] = []
        seen: set[str] = set()
        for row in found:
            company = str(row.get("company") or "").strip()
            url = str(row.get("careers_url") or "").strip()
            if not company or not url.startswith(("http://", "https://")):
                continue
            key = company.lower()
            if key in seen:
                continue
            seen.add(key)
            clean.append((company, url))
        clean = clean[: SETTINGS.career_source_max_companies]
        if clean:
            names = ", ".join(company for company, _ in clean)
            await self._emit(
                "career",
                f"company hunt: {len(clean)} companies hiring now - probing their live careers pages ({names})",
            )
        else:
            await self._emit(
                "career",
                "company hunt: no companies with readable careers pages surfaced - using matched-company probes",
            )
        return clean

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
        for index, match in enumerate(matches, start=1):
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
                    "posted_at": job.posted_at.isoformat() if job.posted_at else None,
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
                        "reason": "salary range may fall below your floor - negotiate",
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
