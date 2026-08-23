from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from hireflow.agents.router import RouterAgent
from hireflow.agents.runlog import RunLog
from hireflow.config import JSONLD_COMPANY_URLS, SETTINGS
from hireflow.domain import Application, ApplicationStatus, JobPosting, Profile
from hireflow.storage.factory import StorageFactory
from hireflow.tools.ats import AtsBoardSource
from hireflow.tools.freehire import FreehireSource
from hireflow.tools.gemini import GeminiClient
from hireflow.tools.jsonld import JsonLdSource
from hireflow.tools.linkedin import LinkedInSource
from hireflow.tools.remoteok import RemoteOKSource
from hireflow.tools.remotive import RemotiveSource
from hireflow.tools.resume_parser import ResumeParser


async def _execute_run(
    runlog: RunLog,
    agent: RouterAgent,
    storage: StorageFactory,
    run_id: str,
    profile: Profile,
) -> None:
    async def progress(stage: str, detail: str) -> None:
        await runlog.emit(run_id, stage, detail)

    await runlog.start(run_id)
    try:
        result = await agent.run_pipeline(profile, progress=progress)
        for job_map in result.get("jobs", []):
            await storage.jobs().put(JobPosting.from_mapping(job_map))
        for app_map in result.get("application_records", []):
            await storage.applications().put(Application.from_mapping(app_map))
        result["status"] = "completed"
        result["run_id"] = run_id
        await runlog.finish(run_id, result)
    except Exception as exc:  # noqa: BLE001 - surface agent failure as a status, not a 500
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


async def _sse_events(runlog: RunLog, run_id: str):
    yield f"event: started\ndata: {json.dumps({'run_id': run_id, 'status': 'started'})}\n\n"
    for _ in range(20):
        if await runlog.exists(run_id):
            break
        await asyncio.sleep(0.5)
    last_seq = 0
    while True:
        for event in await runlog.events_since(run_id, last_seq):
            yield f"data: {json.dumps(event)}\n\n"
            last_seq = event["seq"]
        if await runlog.is_done(run_id):
            result = await runlog.result(run_id)
            yield f"event: done\ndata: {json.dumps(result)}\n\n"
            return
        await asyncio.sleep(0.5)


def _build_default_agent() -> RouterAgent:
    gemini = GeminiClient()
    sources = [
        FreehireSource(),
        RemoteOKSource(),
        RemotiveSource(),
        LinkedInSource(),
        AtsBoardSource(),
        JsonLdSource(urls=JSONLD_COMPANY_URLS),
    ]
    return RouterAgent(sources=sources, gemini=gemini)


def create_app(
    storage: StorageFactory | None = None, agent: RouterAgent | None = None
) -> FastAPI:
    """App factory — injectable storage/agent; defaults to real ones."""
    api = FastAPI(title="Hireflow API", version="0.3.0")
    api.state.storage = storage or StorageFactory()
    api.state.agent = agent or _build_default_agent()
    api.state.parser = ResumeParser()
    api.state.runlog = RunLog()

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
    async def approve(application_id: str) -> dict[str, str]:
        repository = api.state.storage.applications()
        application = await repository.get(application_id) or Application(id=application_id)
        application.status = ApplicationStatus.APPROVED
        await repository.put(application)
        return {"id": application_id, "status": ApplicationStatus.APPROVED.value}

    @api.post("/pipeline/run")
    async def run_pipeline(profile_id: str) -> dict:
        profile = await api.state.storage.profiles().get(profile_id)
        if profile is None:
            return {"profile_id": profile_id, "status": "profile_not_found"}
        run_id = str(uuid.uuid4())
        asyncio.create_task(
            _execute_run(api.state.runlog, api.state.agent, api.state.storage, run_id, profile)
        )
        return {"run_id": run_id, "profile_id": profile_id, "status": "started"}

    @api.get("/pipeline/run/{run_id}/events")
    async def pipeline_events(run_id: str) -> StreamingResponse:
        return StreamingResponse(
            _sse_events(api.state.runlog, run_id),
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
            except Exception as exc:  # noqa: BLE001 - degrade to text-only, never a 500
                errors.append(f"vision parse: {type(exc).__name__}: {str(exc)[:200]}")
                parsed = {}
        if not parsed:
            try:
                parsed = await gemini.parse_resume(profile.resume_text)
            except Exception as exc:  # noqa: BLE001
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