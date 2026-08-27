from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from hireflow.agents.adk_router import HireflowAgent
from hireflow.agents.router import RouterAgent
from hireflow.agents.runlog import RunLog
from hireflow.config import JSONLD_COMPANY_URLS, SETTINGS
from hireflow.domain import Application, ApplicationStatus, JobPosting, Profile
from hireflow.storage.factory import StorageFactory
from hireflow.tools.ats import AtsBoardSource
from hireflow.tools.browser import PlaywrightSource
from hireflow.tools.discovery import WebDiscoverySource
from hireflow.tools.freehire import FreehireSource
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.japan_dev import JapanDevSource
from hireflow.tools.jsonld import JsonLdSource
from hireflow.tools.jobstreet import JobStreetSource
from hireflow.tools.linkedin import LinkedInSource
from hireflow.tools.remoteok import RemoteOKSource
from hireflow.tools.remotive import RemotiveSource
from hireflow.tools.resume_parser import ResumeParser
from hireflow.tools.wantedly import WantedlySource


class AtsSandbox:
    """In-memory sandbox ATS - the demo's real submit destination.

    Records every approved submission with the exact payload a real ATS would
    receive (drafted CV + cover letter + job/profile) and returns a
    confirmation code. Kept in memory plus a best-effort JSON file on the
    instance's ephemeral disk (a redeploy starts empty). No real employer is
    ever contacted - this is the honest "the agent sent the right info to the
    right place" proof for the demo.
    """

    def __init__(self, file_path: str | None = None) -> None:
        self._file_path = file_path or SETTINGS.sandbox_ats_file
        self._submissions: list[dict] = []
        self._load()

    def submit(self, application: Application) -> dict:
        now = datetime.now(timezone.utc)
        record = {
            "application_id": application.id,
            "profile_id": application.profile_id,
            "job": application.job.to_mapping() if application.job else None,
            "cv": application.drafts.get("cv", ""),
            "cover_letter": application.drafts.get("cover_letter", ""),
            "submitted_at": now.isoformat(),
            "ats_confirmation": f"HFS-{uuid.uuid4().hex[:8].upper()}",
        }
        self._submissions.append(record)
        self._save()
        return record

    def list_all(self) -> list[dict]:
        return list(self._submissions)

    def _load(self) -> None:
        try:
            with open(self._file_path, encoding="utf-8") as handle:
                data = json.loads(handle.read() or "[]")
            if isinstance(data, list):
                self._submissions = data
        except (OSError, ValueError):
            self._submissions = []

    def _save(self) -> None:
        try:
            with open(self._file_path, "w", encoding="utf-8") as handle:
                json.dump(self._submissions, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass


class FreehireRegionalSource(FreehireSource):
    """Freehire sub-source pass (``source=seek`` / ``source=mycareersfuture``).

    Same FreehireSource, different server-side ``source`` facet. ``seek`` is a
    JobStreet APAC engine (MY/ID/SG/AU/NZ); ``mycareersfuture`` is the SG
    government board. Lives here (app layer) so ``freehire.py`` stays a shared
    source file owned by the parallel agent. Source is named
    ``freehire:<source>`` for SSE attribution.
    """

    def __init__(self, source: str) -> None:
        super().__init__()
        self._region_source = source
        self.name = f"freehire:{source}"

    def _params(
        self,
        query: str,
        location: str,
        work_type: str = "any",
        locations: list[str] | None = None,
    ) -> dict[str, str]:
        params = super()._params(query, location, work_type=work_type, locations=locations)
        if self._region_source:
            params["source"] = self._region_source
            if self._region_source == "seek":
                params.pop("countries", None)
                params["regions"] = "apac"
        return params


async def _execute_run(
    runlog: RunLog,
    agent: HireflowAgent,
    storage: StorageFactory,
    run_id: str,
    profile: Profile,
    seed: int = 0,
    seen_jobs: list[str] | None = None,
) -> None:
    async def progress(stage: str, detail: str) -> None:
        await runlog.emit(run_id, stage, detail)

    await runlog.start(run_id)
    try:
        result = await agent.run_pipeline(profile, progress=progress, seed=seed, seen_jobs=seen_jobs)
        for job_map in result.get("jobs", []):
            await storage.jobs().put(JobPosting.from_mapping(job_map))
        drafts = result.get("drafts", {}) or {}
        for app_map in result.get("application_records", []):
            application = Application.from_mapping(app_map)
            job_id = ""
            if isinstance(app_map.get("job"), dict):
                job_id = str(app_map["job"].get("id", "") or "")
            if job_id:
                package = drafts.get(job_id)
                if isinstance(package, dict):
                    application.drafts = {
                        "cv": str(package.get("cv", "") or ""),
                        "cover_letter": str(package.get("cover_letter", "") or ""),
                    }
            await storage.applications().put(application)
        result["status"] = "completed"
        result["run_id"] = run_id
        await runlog.finish(run_id, result)
    except asyncio.CancelledError:
        await runlog.finish(run_id, {"run_id": run_id, "status": "cancelled", "errors": []})
        raise
    except Exception as exc:
        await runlog.finish(
            run_id,
            {
                "profile_id": profile.id,
                "run_id": run_id,
                "status": "error",
                "detail": f"{type(exc).__name__}: {str(exc)[:400]}",
                "errors": [f"{type(exc).__name__}: {str(exc)[:200]}"],
            },
        )


async def _sse_events(runlog: RunLog, run_id: str, last_seq: int = 0):
    yield f"event: started\nid: 0\ndata: {json.dumps({'run_id': run_id, 'status': 'started'})}\n\n"
    for _ in range(20):
        if await runlog.exists(run_id):
            break
        await asyncio.sleep(0.5)
    while True:
        for event in await runlog.events_since(run_id, last_seq):
            last_seq = event["seq"]
            yield f"id: {last_seq}\ndata: {json.dumps(event)}\n\n"
        if await runlog.is_done(run_id):
            result = await runlog.result(run_id)
            yield f"event: done\nid: {last_seq}\ndata: {json.dumps(result)}\n\n"
            return
        await asyncio.sleep(0.5)


def _build_default_agent() -> HireflowAgent:
    gemini = GeminiClient()
    sources = [
        LinkedInSource(detail=False),
        FreehireSource(),
        *[FreehireRegionalSource(source) for source in SETTINGS.freehire_sources],
        RemoteOKSource(),
        RemotiveSource(),
        JsonLdSource(urls=JSONLD_COMPANY_URLS),
        AtsBoardSource(),
    ]
    if SETTINGS.web_discovery_enabled:
        sources.append(
            WebDiscoverySource(
                max_links=SETTINGS.web_discovery_max_links,
                companies=SETTINGS.web_discovery_companies,
                timeout=SETTINGS.web_fetch_timeout,
            )
        )
    if SETTINGS.use_unverified_sources:
        sources.append(WantedlySource())
        sources.append(JapanDevSource())
    if SETTINGS.playwright_enabled:
        sources.append(PlaywrightSource())
        if SETTINGS.jobstreet_enabled:
            sources.append(JobStreetSource())
    router = RouterAgent(sources=sources, gemini=gemini)
    return HireflowAgent(router=router)


def create_app(
    storage: StorageFactory | None = None, agent: HireflowAgent | None = None
) -> FastAPI:
    """App factory - injectable storage/agent; defaults to real ones."""
    api = FastAPI(title="Hireflow API", version="0.3.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://hireflow-pi-five.vercel.app",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5175",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.state.storage = storage or StorageFactory()
    api.state.agent = agent or _build_default_agent()
    api.state.parser = ResumeParser()
    api.state.runlog = RunLog()
    api.state.run_tasks: dict[str, asyncio.Task] = {}
    api.state.ats = AtsSandbox()

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/upload")
    async def upload_resume(
        file: UploadFile = File(...),
        work_type: str = Form("any"),
        locations: str = Form(""),
        target_roles: str = Form(""),
        salary_floor: str = Form(""),
    ) -> dict:
        parser = api.state.parser
        try:
            parser.validate(file.filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        normalized_work_type = work_type.strip().lower()
        if normalized_work_type not in {"remote", "hybrid", "onsite", "any"}:
            raise HTTPException(
                status_code=400,
                detail="work_type must be one of remote|hybrid|onsite|any",
            )
        content = await file.read()
        try:
            text, pages = parser.parse_bytes(file.filename or "resume", content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        salary_parsed = _parse_salary_floor(salary_floor)
        profile = Profile(
            id=str(uuid.uuid4()),
            resume_text=text,
            work_type=normalized_work_type,
            target_roles=_split_csv(target_roles),
            locations=_split_csv(locations),
            salary_floor=salary_parsed,
        )
        parsed, parse_errors = await _enrich_profile(
            api.state.agent.gemini, api.state.parser, profile, file.filename, content
        )
        if not profile.target_roles:
            profile.target_roles = parsed.get("target_roles", [])
        profile.skills = parsed.get("skills", [])
        profile.years_experience = float(parsed.get("years_experience", 0.0) or 0.0)
        profile.culture_keywords = parsed.get("culture_keywords", [])
        profile.residence = str(parsed.get("residence", "") or "")
        profile.parsed_at = datetime.now()
        await api.state.storage.profiles().put(profile)
        return {
            "id": profile.id,
            "filename": file.filename,
            "status": "parsed_and_stored",
            "pages": pages,
            "work_type": profile.work_type,
            "locations": profile.locations,
            "target_roles": profile.target_roles,
            "salary_floor": profile.salary_floor,
            "skills": profile.skills,
            "years_experience": profile.years_experience,
            "residence": profile.residence,
            "culture_keywords": profile.culture_keywords,
            "parse_errors": parse_errors,
        }

    @api.get("/dashboard")
    async def dashboard() -> dict:
        applications = await api.state.storage.applications().list_all()
        jobs = await api.state.storage.jobs().list_all()
        profiles = await api.state.storage.profiles().list_all()
        status_counts = Counter(app.status.value for app in applications)
        return {
            "pipeline": "Find -> Analyze -> Rank -> Research -> Prepare -> Approve -> Track",
            "profiles": len(profiles),
            "jobs_found": len(jobs),
            "applications": len(applications),
            "by_status": dict(status_counts),
        }

    @api.get("/jobs")
    async def jobs() -> list[dict]:
        return [job.to_mapping() for job in await api.state.storage.jobs().list_all()]

    @api.get("/applications")
    async def applications() -> list[dict]:
        return [app.to_mapping() for app in await api.state.storage.applications().list_all()]

    @api.post("/approve")
    async def approve(application_id: str) -> dict:
        repository = api.state.storage.applications()
        application = await repository.get(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="application not found")
        submission = api.state.ats.submit(application)
        application.status = ApplicationStatus.SUBMITTED
        application.ats_confirmation = submission["ats_confirmation"]
        try:
            application.submitted_at = datetime.fromisoformat(submission["submitted_at"])
        except ValueError:
            application.submitted_at = None
        await repository.put(application)
        return {
            "id": application.id,
            "status": ApplicationStatus.SUBMITTED.value,
            "submitted_at": submission["submitted_at"],
            "ats_confirmation": submission["ats_confirmation"],
        }

    @api.post("/sandbox/ats/apply")
    async def sandbox_ats_apply(payload: dict) -> dict:
        job = (
            JobPosting.from_mapping(payload["job"])
            if isinstance(payload.get("job"), dict)
            else None
        )
        application = Application(
            id=str(payload.get("application_id", "") or uuid.uuid4()),
            profile_id=str(payload.get("profile_id", "") or ""),
            job=job,
            drafts={
                "cv": str(payload.get("cv", "") or ""),
                "cover_letter": str(payload.get("cover_letter", "") or ""),
            },
        )
        return api.state.ats.submit(application)

    @api.get("/sandbox/ats/submissions")
    async def sandbox_ats_submissions() -> list[dict]:
        return api.state.ats.list_all()

    @api.post("/pipeline/run")
    async def run_pipeline(profile_id: str, seed: int = 0, seen: str = "") -> dict:
        profile = await api.state.storage.profiles().get(profile_id)
        if profile is None:
            return {"profile_id": profile_id, "status": "profile_not_found"}
        run_id = str(uuid.uuid4())
        seen_jobs = _split_csv(seen)
        task = asyncio.create_task(
            _execute_run(
                api.state.runlog,
                api.state.agent,
                api.state.storage,
                run_id,
                profile,
                seed=seed,
                seen_jobs=seen_jobs,
            )
        )
        api.state.run_tasks[run_id] = task
        task.add_done_callback(lambda t: api.state.run_tasks.pop(run_id, None))
        return {"run_id": run_id, "profile_id": profile_id, "status": "started"}

    @api.get("/pipeline/run/{run_id}")
    async def pipeline_status(run_id: str) -> dict:
        if not await api.state.runlog.exists(run_id):
            return {"run_id": run_id, "exists": False, "done": False}
        result = await api.state.runlog.result(run_id)
        done = result is not None
        return {
            "run_id": run_id,
            "exists": True,
            "done": done,
            "status": (result or {}).get("status", "running"),
            "result": result,
        }

    @api.post("/pipeline/run/{run_id}/cancel")
    async def cancel_pipeline(run_id: str) -> dict:
        task = api.state.run_tasks.get(run_id)
        if task is None:
            return {"run_id": run_id, "status": "not_found"}
        if task.done():
            return {"run_id": run_id, "status": "already_finished"}
        task.cancel()
        return {"run_id": run_id, "status": "cancelling"}

    @api.get("/pipeline/run/{run_id}/events")
    async def pipeline_events(
        run_id: str,
        request: Request,
        last_event_id: int = 0,
    ) -> StreamingResponse:
        resume = last_event_id
        if resume <= 0:
            last = request.headers.get("Last-Event-ID")
            if last and last.isdigit():
                resume = int(last)
        return StreamingResponse(
            _sse_events(api.state.runlog, run_id, last_seq=resume),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return api


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


async def _enrich_profile(
    gemini: GeminiClient,
    parser: ResumeParser,
    profile: Profile,
    filename: str | None,
    content: bytes,
) -> tuple[dict, list[str]]:
    mode = SETTINGS.resume_parse_mode
    is_pdf = (filename or "").lower().endswith(".pdf")
    thin = len("".join(profile.resume_text.split())) < 200
    use_vision = mode == "vision" or (mode == "hybrid" and is_pdf and thin)
    errors: list[str] = []
    parsed: dict = {}
    if profile.resume_text:
        if use_vision:
            try:
                pages = parser.pdf_page_images(content)
                parsed = await gemini.parse_resume_vision(pages, text_hint=profile.resume_text[:2000])
            except Exception as exc:
                errors.append(f"vision parse: {type(exc).__name__}: {str(exc)[:200]}")
                parsed = {}
        if not parsed:
            try:
                parsed = await gemini.parse_resume(profile.resume_text)
            except Exception as exc:
                errors.append(f"text parse: {type(exc).__name__}: {str(exc)[:200]}")
                parsed = {}
    return parsed, errors


def _parse_salary_floor(value: str) -> int | None:
    if not value or not value.strip():
        return None
    try:
        return int(value.strip().replace(",", ""))
    except ValueError:
        return None


app = create_app()
